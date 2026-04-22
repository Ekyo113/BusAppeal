"""
bus_service.py
==============
負責：
1. TDX API OAuth2 認證（Token 快取 24 小時）
2. 多城市公車動態拉取（/v2/Bus/RealTimeByFrequency/City/{city}）
3. GPS 靜止偵測（Haversine + gps_history）
4. 整合品情通報狀態
5. 定期清理 gps_history 過舊資料
"""

import math
import os
import time
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from database import Database
from config import Config


# ─────────────────────────────────────────
# TDX OAuth2 Token 管理
# ─────────────────────────────────────────

_tdx_token: Optional[str] = None
_tdx_token_expiry: float = 0.0  # Unix timestamp (秒)

TDX_AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TDX_BASE_URL = "https://tdx.transportdata.tw/api/basic"


def _get_tdx_token() -> str:
    """取得 TDX Access Token，有效期 24 小時，過期自動重新取得。"""
    global _tdx_token, _tdx_token_expiry

    if _tdx_token and time.time() < _tdx_token_expiry - 60:
        return _tdx_token

    client_id = Config.TDX_CLIENT_ID
    client_secret = Config.TDX_CLIENT_SECRET

    if not client_id or not client_secret:
        raise RuntimeError("TDX_CLIENT_ID / TDX_CLIENT_SECRET 未設定")

    resp = httpx.post(
        TDX_AUTH_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=10,
    )
    resp.raise_for_status()
    body = resp.json()

    _tdx_token = body["access_token"]
    _tdx_token_expiry = time.time() + body.get("expires_in", 86400)
    return _tdx_token


# ─────────────────────────────────────────
# Haversine 距離計算
# ─────────────────────────────────────────

def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """計算兩個 GPS 座標之間的距離（公尺）。"""
    R = 6_371_000  # 地球半徑（公尺）
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─────────────────────────────────────────
# GPS 靜止偵測
# ─────────────────────────────────────────

STALL_THRESHOLD_METERS = 5      # 5 公尺以內視為「未移動」
STALL_WINDOW_RECORDS   = 4      # 最近 4 筆（= 2 分鐘）


def _check_stall(city_code: str, plate: str,
                 cur_lat: float, cur_lon: float,
                 stop_seq: int, is_terminal: bool) -> tuple[str, int]:
    """
    比對最近 N 筆 GPS 歷史，判斷是否為靜止狀態。
    回傳 (status, stalled_seconds)
    status: 'operating' | 'attention'
    """
    if is_terminal or stop_seq <= 1:
        # 起始/終點站不觸發注意狀態
        return "operating", 0

    client = Database.get_client()
    rows = (
        client.table("gps_history")
        .select("lat, lon, recorded_at")
        .eq("city_code", city_code)
        .eq("plate_number", plate)
        .order("recorded_at", desc=True)
        .limit(STALL_WINDOW_RECORDS)
        .execute()
        .data
    )

    if len(rows) < STALL_WINDOW_RECORDS:
        # 資料不足，尚無法判斷
        return "operating", 0

    oldest = rows[-1]
    try:
        dist = _haversine_meters(
            float(oldest["lat"]), float(oldest["lon"]),
            cur_lat, cur_lon
        )
    except (TypeError, ValueError):
        return "operating", 0

    if dist < STALL_THRESHOLD_METERS:
        # 計算靜止秒數
        try:
            oldest_dt = datetime.fromisoformat(oldest["recorded_at"].replace("Z", "+00:00"))
            stalled_sec = int((datetime.now(timezone.utc) - oldest_dt).total_seconds())
        except Exception:
            stalled_sec = STALL_WINDOW_RECORDS * 30
        return "attention", stalled_sec

    return "operating", 0


# ─────────────────────────────────────────
# GPS 歷史寫入與清理
# ─────────────────────────────────────────

def _save_gps_snapshot(city_code: str, plate: str,
                       lat: float, lon: float,
                       stop_name: str, stop_seq: int, is_terminal: bool):
    """將本次 GPS 快照寫入 gps_history。"""
    client = Database.get_client()
    client.table("gps_history").insert({
        "city_code": city_code,
        "plate_number": plate,
        "lat": lat,
        "lon": lon,
        "stop_name": stop_name,
        "stop_sequence": stop_seq,
        "is_terminal": is_terminal,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def cleanup_old_gps_history():
    """
    清理 30 分鐘以前的 gps_history 資料。
    每次 /bus/status 被呼叫時觸發（輕量操作，30 分鐘才會有資料累積）。
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    client = Database.get_client()
    try:
        client.table("gps_history").delete().lt("recorded_at", cutoff).execute()
    except Exception as e:
        print(f"[BusService] GPS history cleanup failed: {e}")


# ─────────────────────────────────────────
# 主要資料拉取與整合
# ─────────────────────────────────────────

def fetch_bus_status(city_code: str) -> dict:
    """
    整合 TDX 即時公車動態 + Supabase 品情通報，
    回傳該城市所有受監控車輛的狀態清單。
    """
    client = Database.get_client()

    # 1. 取得受監控車輛清單
    monitored_rows = (
        client.table("monitored_buses")
        .select("plate_number, route_name, vendor_name")
        .eq("city_code", city_code)
        .eq("is_active", True)
        .execute()
        .data
    )
    monitored_plates = {row["plate_number"]: row for row in monitored_rows}

    if not monitored_plates:
        return {"city_code": city_code, "updated_at": _now_iso(), "buses": []}

    # 2. 取得未處理品情通報（依車牌 index）
    reports_rows = (
        client.table("reports")
        .select("car_number, description, id, created_at")
        .neq("status", "已處理")
        .execute()
        .data
    )
    # 同一車可能有多筆通報，取最新一筆
    incident_map: dict[str, dict] = {}
    for r in reports_rows:
        cn = r["car_number"]
        if cn not in incident_map:
            incident_map[cn] = r
        else:
            # 保留較新的通報
            if r["created_at"] > incident_map[cn]["created_at"]:
                incident_map[cn] = r

    # 3. 從 TDX 取得即時位置（A1 動態定時資料）與 站點資訊（A2 定點資料）
    tdx_data = _fetch_tdx_realtime(city_code)
    tdx_nearstop = _fetch_tdx_nearstop(city_code)

    # 建立 plate → TDX A1 record 的 mapping
    tdx_map: dict[str, dict] = {}
    for rec in tdx_data:
        plate = rec.get("PlateNumb", "").strip()
        if plate in monitored_plates:
            tdx_map[plate] = rec

    # 建立 plate → TDX A2 近站資訊 的 mapping
    nearstop_map: dict[str, dict] = {}
    for rec in tdx_nearstop:
        plate = rec.get("PlateNumb", "").strip()
        if plate in monitored_plates:
            nearstop_map[plate] = rec

    # 4. 整合每台車的狀態
    buses: list[dict] = []
    for plate, meta in monitored_plates.items():
        tdx_rec = tdx_map.get(plate)
        ns_rec = nearstop_map.get(plate)
        incident = incident_map.get(plate)

        if tdx_rec or ns_rec:
            # 優先使用 A1 位置
            pos = (tdx_rec or {}).get("BusPosition", {})
            lat = pos.get("PositionLat")
            lon = pos.get("PositionLon")
            route_name_tdx = ((tdx_rec or ns_rec).get("RouteName") or {}).get("Zh_tw", "")

            # 站點資訊從 A2 (RealTimeNearStop) 或是 A1 (如果有的話) 取
            stop_name = (ns_rec or tdx_rec or {}).get("StopName", {}).get("Zh_tw", "")
            stop_seq  = (ns_rec or tdx_rec or {}).get("StopSequence") or 0

            # 暫以 StopSequence <= 1 做起始站判斷
            is_terminal = (stop_seq <= 1)
            is_operating = True

            # 寫入 GPS 快照
            if lat and lon:
                _save_gps_snapshot(city_code, plate, float(lat), float(lon),
                                   stop_name, stop_seq, is_terminal)
                bus_status, stalled_sec = _check_stall(
                    city_code, plate, float(lat), float(lon), stop_seq, is_terminal
                )
            else:
                bus_status, stalled_sec = "operating", 0
        else:
            lat = lon = None
            stop_name = ""
            stop_seq  = 0
            route_name_tdx = ""
            is_operating = False
            bus_status = "not_operating"
            stalled_sec = 0

        # 品情通報優先
        if incident:
            bus_status = "incident"

        buses.append({
            "plate_number":         plate,
            "route_name":           route_name_tdx or meta.get("route_name", ""),
            "vendor_name":          meta.get("vendor_name", ""),
            "current_stop":         stop_name,
            "stop_sequence":        stop_seq,
            "lat":                  float(lat) if lat else None,
            "lon":                  float(lon) if lon else None,
            "is_operating":         is_operating,
            "status":               bus_status,          # operating | attention | not_operating | incident
            "stalled_seconds":      stalled_sec,
            "has_incident":         bool(incident),
            "incident_description": incident["description"] if incident else None,
            "incident_id":          incident["id"] if incident else None,
        })

    # 5. 排序：incident > attention > operating > not_operating
    priority = {"incident": 0, "attention": 1, "operating": 2, "not_operating": 3}
    buses.sort(key=lambda b: (priority.get(b["status"], 9), b["plate_number"]))

    # 6. 清理過舊 GPS 快照
    cleanup_old_gps_history()

    return {
        "city_code":  city_code,
        "updated_at": _now_iso(),
        "buses":      buses,
    }


def _fetch_tdx_realtime(city_code: str) -> list[dict]:
    """呼叫 TDX A1 公車動態定時資料 API。"""
    token = _get_tdx_token()
    url = f"{TDX_BASE_URL}/v2/Bus/RealTimeByFrequency/City/{city_code}"
    params = {
        "$format": "JSON",
    }
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        print(f"[BusService A1] TDX API error ({city_code}): {e.response.status_code}")
        return []
    except Exception as e:
        print(f"[BusService A1] TDX fetch failed ({city_code}): {e}")
        return []

def _fetch_tdx_nearstop(city_code: str) -> list[dict]:
    """呼叫 TDX A2 公車定點資料 API 取得目前站點名稱。"""
    token = _get_tdx_token()
    url = f"{TDX_BASE_URL}/v2/Bus/RealTimeNearStop/City/{city_code}"
    params = {
        "$format": "JSON",
    }
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        print(f"[BusService A2] TDX API error ({city_code}): {e.response.status_code}")
        return []
    except Exception as e:
        print(f"[BusService A2] TDX fetch failed ({city_code}): {e}")
        return []


def fetch_cities() -> list[dict]:
    """回傳所有啟用的城市清單（供前端下拉選單）。"""
    client = Database.get_client()
    rows = (
        client.table("cities")
        .select("city_code, city_name, center_lat, center_lon")
        .eq("is_active", True)
        .order("city_name")
        .execute()
        .data
    )
    return rows


def _now_iso() -> str:
    tz_taipei = timezone(timedelta(hours=8))
    return datetime.now(tz_taipei).isoformat()
