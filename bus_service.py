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
from dateutil.parser import parse as parse_date
import gc
from database import Database
from config import Config
from utils import haversine_meters
from ai_service import AIService


# ─────────────────────────────────────────
# TDX OAuth2 Token 管理
# ─────────────────────────────────────────

_tdx_token: Optional[str] = None
_tdx_token_expiry: float = 0.0  # Unix timestamp (秒)
_status_cache: dict = {}  # {city_code: {"data": payload, "cached_at": datetime}}

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
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 0
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
            oldest_dt = parse_date(oldest["recorded_at"])
            if oldest_dt.tzinfo is None:
                oldest_dt = oldest_dt.replace(tzinfo=timezone.utc)
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

def fetch_bus_status(city_code: str, force_a2: bool = False, bypass_cache: bool = False) -> dict:
    """
    整合 TDX 即時公車動態 + Supabase 品情通報，
    回傳該城市所有受監控車輛的狀態清單。
    """
    global _status_cache
    now_dt = datetime.now(timezone.utc)

    # 檢查記憶體快取 (在非強刷且 10 分鐘內時)
    if not bypass_cache and not force_a2 and city_code in _status_cache:
        cache_entry = _status_cache[city_code]
        elapsed = (now_dt - cache_entry["cached_at"]).total_seconds()
        if elapsed < 600:
            res_data = cache_entry["data"].copy()
            res_data["cache_remaining_seconds"] = max(0, int(600 - elapsed))
            return res_data

    client = Database.get_client()

    # 1. 取得受監控車輛清單
    monitored_rows = (
        client.table("monitored_buses")
        .select("id, plate_number, route_name, vendor_name, last_lat, last_lon, last_gps_time, last_stop_name")
        .eq("city_code", city_code)
        .eq("is_active", True)
        .execute()
        .data
    )
    monitored_plates = {row["plate_number"]: row for row in monitored_rows}

    if not monitored_plates:
        return {"city_code": city_code, "updated_at": _now_iso(), "buses": [], "cache_remaining_seconds": 600}

    # 2. 取得未處理品情通報（依車牌 index）
    reports_rows = (
        client.table("reports")
        .select("car_number, description, id, created_at")
        .neq("status", "已完成")
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
    # 限制更新時間：僅在 08:00 ~ 23:00 之間更新
    tz_taipei = timezone(timedelta(hours=8))
    now = datetime.now(tz_taipei)
    if 8 <= now.hour < 23:
        tdx_data = _fetch_tdx_realtime(city_code)
        # 節省 TDX token，只有在 force_a2 為 True 時才呼叫 A2 API
        if force_a2:
            tdx_nearstop = _fetch_tdx_nearstop(city_code)
        else:
            tdx_nearstop = []
    else:
        tdx_data = []
        tdx_nearstop = []

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
    updates = []
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
            speed = (tdx_rec or {}).get("Speed", 0)

            # 站點資訊從 A2 (RealTimeNearStop) 或是 A1 (如果有的話) 取
            cur_stop = ""
            rec_for_stop = ns_rec or tdx_rec or {}
            stop_name_raw = rec_for_stop.get("StopName")
            if isinstance(stop_name_raw, dict):
                cur_stop = stop_name_raw.get("Zh_tw", "")
            elif isinstance(stop_name_raw, str):
                cur_stop = stop_name_raw

            # 如果目前沒抓到站點（例如公車在站間或未更新 A2），則沿用資料庫中的最後紀錄
            stop_name = cur_stop or meta.get("last_stop_name") or ""
            
            stop_seq  = (ns_rec or tdx_rec or {}).get("StopSequence") or 0
            
            # 從 TDX 取得原始 BusStatus (0: 正常, 100: 營運中, 90: 非營運...)
            raw_status = (tdx_rec or ns_rec or {}).get("BusStatus", 0)

            # 暫以 StopSequence <= 1 做起始站判斷
            is_terminal = (stop_seq <= 1)
            is_operating = raw_status in [0, 100]

            # 寫入 GPS 快照
            if lat and lon:
                lat_float = float(lat)
                lon_float = float(lon)
                _save_gps_snapshot(city_code, plate, lat_float, lon_float,
                                   stop_name, stop_seq, is_terminal)
                bus_status, stalled_sec = _check_stall(
                    city_code, plate, lat_float, lon_float, stop_seq, is_terminal
                )
                if lat_float != 0 and lon_float != 0:
                    update_item = {
                        "id": meta["id"],
                        "city_code": city_code,
                        "plate_number": plate,
                        "last_lat": lat_float,
                        "last_lon": lon_float,
                        "last_gps_time": _now_iso()
                    }
                    if cur_stop:
                        update_item["last_stop_name"] = cur_stop
                    updates.append(update_item)
            else:
                bus_status, stalled_sec = "operating", 0
        else:
            lat = lon = None
            stop_name = ""
            stop_seq  = 0
            route_name_tdx = ""
            speed = 0
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
            "last_lat":             meta.get("last_lat"),
            "last_lon":             meta.get("last_lon"),
            "last_gps_time":        meta.get("last_gps_time"),
            "is_operating":         is_operating,
            "raw_status":           raw_status if (tdx_rec or ns_rec) else 255,
            "speed":                speed,
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

    # 7. 批次更新最後有效 GPS 到資料庫
    if updates:
        try:
            client.table("monitored_buses").upsert(updates).execute()
        except Exception as e:
            print(f"[BusService] Failed to upsert last GPS: {e}")

    res_payload = {
        "city_code":  city_code,
        "updated_at": _now_iso(),
        "buses":      buses,
    }

    # 更新記憶體快取
    _status_cache[city_code] = {
        "data": res_payload,
        "cached_at": now_dt
    }

    res_payload_with_time = res_payload.copy()
    res_payload_with_time["cache_remaining_seconds"] = 600
    return res_payload_with_time


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

def _fetch_tdx_schedules(city_code: str) -> list[dict]:
    """呼叫 TDX 公車時刻表 API。"""
    token = _get_tdx_token()
    url = f"{TDX_BASE_URL}/v2/Bus/Schedule/City/{city_code}"
    params = {
        "$format": "JSON",
    }
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[BusService Schedule] TDX fetch failed ({city_code}): {e}")
        return []

def sync_specific_route_schedules(city_code: str, route_name: str):
    """抓取單一特定路線的時刻表並存入快取。"""
    print(f"[BusService] Syncing specific route: {route_name} in {city_code}...")
    token = _get_tdx_token()
    url = f"{TDX_BASE_URL}/v2/Bus/Schedule/City/{city_code}/{route_name}"
    params = {"$format": "JSON"}
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=20)
        if resp.status_code == 404:
            print(f"[BusService] Route {route_name} not found in TDX.")
            return 0
        resp.raise_for_status()
        schedules = resp.json()
    except Exception as e:
        print(f"[BusService] Failed to fetch {route_name}: {e}")
        return 0

    records = []
    for route in schedules:
        direction = route.get("Direction", 0)
        timetables = route.get("Timetables", [])
        for entry in timetables:
            stop_times = entry.get("StopTimes", [])
            if stop_times:
                dept_time = stop_times[0].get("DepartureTime", "")
                if dept_time:
                    records.append({
                        "city_code": city_code,
                        "route_name": route_name,
                        "direction": direction,
                        "departure_time": dept_time
                    })

    if records:
        client = Database.get_client()
        # 刪除該路線舊資料
        client.table("bus_route_schedules").delete().eq("city_code", city_code).eq("route_name", route_name).execute()
        client.table("bus_route_schedules").insert(records).execute()
        print(f"[BusService] Saved {len(records)} schedule entries for {route_name}")
    
    return len(records)

def sync_route_schedules(city_code: str):
    """從 weekly_bus_gps_log 既有的路線中，更新該城市的路線時刻表。"""
    print(f"[BusService] Syncing schedules for {city_code} from weekly_bus_gps_log routes...")
    client = Database.get_client()
    
    # 1. 取得該城市所有監控車輛的車牌
    try:
        monitored_res = client.table("monitored_buses").select("plate_number").eq("city_code", city_code).execute()
        city_plates = [row["plate_number"] for row in monitored_res.data]
    except Exception as e:
        print(f"[BusService] Failed to fetch monitored buses for {city_code}: {e}")
        return 0
        
    if not city_plates:
        print(f"[BusService] No monitored buses found for {city_code}")
        return 0
        
    # 2. 取得 weekly_bus_gps_log 中屬於 these 車牌的唯一路線
    try:
        res = client.table("weekly_bus_gps_log").select("route_name").in_("plate_number", city_plates).execute()
    except Exception as e:
        print(f"[BusService] Failed to fetch weekly_bus_gps_log for route syncing: {e}")
        return 0
        
    routes = set()
    for row in res.data:
        route = row.get("route_name", "")
        if route:
            routes.add(route)
            
    routes = sorted(list(routes))
    print(f"[BusService] Unique routes found for {city_code}: {routes}")
    
    if not routes:
        print(f"[BusService] No routes found in weekly_bus_gps_log for {city_code}")
        return 0
        
    # 2. 清理該城市的 bus_route_schedules
    try:
        client.table("bus_route_schedules").delete().eq("city_code", city_code).in_("route_name", routes).execute()
    except Exception as e:
        print(f"[BusService] Failed to clean old schedules: {e}")
        
    # 3. 逐一同步這些路線
    total_count = 0
    for route in routes:
        try:
            count = sync_specific_route_schedules(city_code, route)
            total_count += count
            time.sleep(0.5)
        except Exception as e:
            print(f"[BusService] Error syncing route {route}: {e}")
            
    print(f"[BusService] Finished syncing schedules for {city_code}. Total {total_count} records saved.")
    return total_count

def _find_closest_schedule_time(route_name: str, target_dt: datetime, schedules: list, direction: str = "closest") -> tuple[Optional[datetime], Optional[str]]:
    route_schedules = [s for s in schedules if s["route_name"].strip() == route_name.strip()]
    if not route_schedules:
        return None, None

    # 第一階段：嘗試依據指定的 direction 篩選「當天」的候選時間
    closest_dt = None
    min_diff = None
    matched_time_str = None

    for s in route_schedules:
        dep_time_str = s["departure_time"] # 格式如 "05:55"
        try:
            dep_hour, dep_min = map(int, dep_time_str.split(":"))
            # 強制候選時間與 target_dt 在同一天
            cand = target_dt.replace(hour=dep_hour, minute=dep_min, second=0, microsecond=0)
            
            diff_sec = (target_dt - cand).total_seconds()
            
            # 檢查方向需求
            if direction == "before":
                if diff_sec < 0:
                    continue
            elif direction == "after":
                if diff_sec > 0:
                    continue
            
            diff = abs(diff_sec)
            if min_diff is None or diff < min_diff:
                min_diff = diff
                closest_dt = cand
                matched_time_str = dep_time_str
        except Exception:
            continue

    # 第二階段：如果在當天特定的方向限制下找不到班表（例如最後一筆 GPS 是 16:40，但當天該路線 16:40 以後完全沒有排班）
    # 則安全回退（Fallback）為「當天最接近的班表」（等同於當天的 direction="closest"），絕對不能跨日匹配到隔天早上！
    if closest_dt is None:
        min_diff = None
        for s in route_schedules:
            dep_time_str = s["departure_time"]
            try:
                dep_hour, dep_min = map(int, dep_time_str.split(":"))
                cand = target_dt.replace(hour=dep_hour, minute=dep_min, second=0, microsecond=0)
                
                diff = abs((target_dt - cand).total_seconds())
                if min_diff is None or diff < min_diff:
                    min_diff = diff
                    closest_dt = cand
                    matched_time_str = dep_time_str
            except Exception:
                continue

    return closest_dt, matched_time_str

async def generate_bus_plan(plate_number: str, date: str):
    """分析特定車號與日期的營運方案。"""
    print(f"[BusService] Generating plan for {plate_number} on {date}...")
    client = Database.get_client()
    
    # 1. 抓取 GPS 紀錄 (確保包括 is_operating 與 speed)
    start_time = f"{date}T00:00:00"
    end_time = f"{date}T23:59:59"
    
    gps_res = client.table("weekly_bus_gps_log")\
        .select("route_name, lat, lon, recorded_at, is_operating, speed")\
        .eq("plate_number", plate_number)\
        .gte("recorded_at", start_time)\
        .lte("recorded_at", end_time)\
        .order("recorded_at")\
        .execute()
    
    gps_data = []
    for row in gps_res.data:
        try:
            # 使用更強固的 dateutil.parser.parse，完美處理任何微秒位數 (如 5 位數等)
            utc_dt = parse_date(row["recorded_at"])
            if utc_dt.tzinfo is not None:
                utc_dt = utc_dt.astimezone(timezone.utc).replace(tzinfo=None)
            tw_dt = utc_dt + timedelta(hours=8)
            row["recorded_at_tw"] = tw_dt
            gps_data.append(row)
        except Exception as e:
            print(f"[BusService] Time parse error: {row.get('recorded_at')} -> {e}")
            
    if not gps_data:
        print(f"[BusService] No GPS logs found for {plate_number} on {date}")
        return None

    # [規則 1] 當日 gps 少於 15 筆不列入計算
    if len(gps_data) < 15:
        print(f"[BusService] Plate {plate_number} on {date} skipped: only {len(gps_data)} GPS records (min 15 required)")
        try:
            client.table("bus_operating_plans").delete().eq("plate_number", plate_number).eq("date", date).execute()
        except Exception as e:
            print(f"[BusService] Failed to clean up excluded plan for {plate_number} on {date}: {e}")
        return None

    # [規則 2] 當日 gps 時間最晚 - 最早少於 6 小時不列入計算
    earliest_time = gps_data[0]["recorded_at_tw"]
    latest_time = gps_data[-1]["recorded_at_tw"]
    span_seconds = (latest_time - earliest_time).total_seconds()
    span_hours = span_seconds / 3600.0
    if span_hours < 6.0:
        print(f"[BusService] Plate {plate_number} on {date} skipped: GPS span is {span_hours:.2f} hours (min 6.0 hours required)")
        try:
            client.table("bus_operating_plans").delete().eq("plate_number", plate_number).eq("date", date).execute()
        except Exception as e:
            print(f"[BusService] Failed to clean up excluded plan for {plate_number} on {date}: {e}")
        return None

    # 2. 篩選「原地中退」點 (與上一點位置差異極小)
    filtered_gps = []
    stationary_count = 0
    last_lat, last_lon = None, None
    for row in gps_data:
        curr_lat = row.get("lat")
        curr_lon = row.get("lon")
        if last_lat is not None and last_lon is not None:
            if abs(curr_lat - last_lat) < 0.0001 and abs(curr_lon - last_lon) < 0.0001:
                stationary_count += 1
                continue
        filtered_gps.append(row)
        last_lat, last_lon = curr_lat, curr_lon
    gps_data = filtered_gps

    # 計算總里程 (Haversine)
    total_dist_km = 0.0
    for i in range(1, len(gps_data)):
        prev = gps_data[i-1]
        curr = gps_data[i]
        try:
            if prev.get("lat") is not None and prev.get("lon") is not None and curr.get("lat") is not None and curr.get("lon") is not None:
                dist = _haversine_meters(float(prev["lat"]), float(prev["lon"]), float(curr["lat"]), float(curr["lon"]))
                total_dist_km += dist / 1000.0
        except Exception:
            continue
    total_mileage = round(total_dist_km, 2)

    # 3. 識別當天出現過的路線，並確保快取中有資料
    routes = sorted(list(set([r["route_name"] for r in gps_data if r.get("route_name")])))
    
    # 根據資料庫中受監控車輛判定正確的城市
    city_code = "Tainan"  # 預設
    try:
        bus_check = client.table("monitored_buses")\
            .select("city_code")\
            .eq("plate_number", plate_number)\
            .limit(1)\
            .execute()
        if bus_check.data:
            city_code = bus_check.data[0]["city_code"]
    except Exception as e:
        print(f"[BusService] Failed to check city_code for {plate_number}: {e}")

    for route in routes:
        cache_check = client.table("bus_route_schedules")\
            .select("id")\
            .eq("city_code", city_code)\
            .eq("route_name", route)\
            .limit(1)\
            .execute()
        
        if not cache_check.data:
            print(f"[BusService] Cache miss for {route}, syncing now...")
            sync_specific_route_schedules(city_code, route)

    # 4. 抓取快取的時刻表 (僅限相關路線)
    schedule_res = client.table("bus_route_schedules")\
        .select("route_name, departure_time")\
        .eq("city_code", city_code)\
        .in_("route_name", routes)\
        .execute()
    
    schedules = schedule_res.data

    # 5. 執行狀態移轉比對演算法
    prev_operating = False
    transitions = []

    for i, row in enumerate(gps_data):
        curr_operating = row.get("is_operating", False)
        route_name = row.get("route_name", "")
        tw_time = row["recorded_at_tw"]

        # 檢測時間間隔大於 30 分鐘的情況 (即使狀態沒變，也自動切分並視為中退)
        if i > 0:
            prev_row = gps_data[i-1]
            prev_tw_time = prev_row["recorded_at_tw"]
            gap_mins = (tw_time - prev_tw_time).total_seconds() / 60.0
            
            if gap_mins > 30.0:
                # 結束前一趟
                if prev_operating:
                    matched_dt, matched_str = _find_closest_schedule_time(
                        prev_row.get("route_name", ""), prev_tw_time, schedules, direction="closest"
                    )
                    transitions.append({
                        "type": "收班 (End)",
                        "gps_time": prev_tw_time,
                        "route": prev_row.get("route_name", ""),
                        "matched_time": matched_str or prev_tw_time.strftime("%H:%M"),
                        "matched_dt": matched_dt or prev_tw_time,
                        "lat": prev_row.get("lat"),
                        "lon": prev_row.get("lon")
                    })
                    prev_operating = False
                
                # 開始新一趟
                if curr_operating:
                    matched_dt, matched_str = _find_closest_schedule_time(
                        route_name, tw_time, schedules, direction="closest"
                    )
                    transitions.append({
                        "type": "開班 (Start)",
                        "gps_time": tw_time,
                        "route": route_name,
                        "matched_time": matched_str or tw_time.strftime("%H:%M"),
                        "matched_dt": matched_dt or tw_time,
                        "lat": row.get("lat"),
                        "lon": row.get("lon")
                    })
                    prev_operating = True
                
                # 已經處理好間隔移轉，繼續下一點
                continue

        # 檢測路線變更的情況 (即使狀態都是營運中，也自動切分)
        if i > 0 and prev_operating and curr_operating:
            prev_row = gps_data[i-1]
            prev_tw_time = prev_row["recorded_at_tw"]
            prev_route = prev_row.get("route_name", "").strip()
            curr_route = route_name.strip()
            
            if prev_route and curr_route and prev_route != curr_route:
                # 結束前一趟
                matched_dt, matched_str = _find_closest_schedule_time(
                    prev_route, prev_tw_time, schedules, direction="closest"
                )
                transitions.append({
                    "type": "收班 (End)",
                    "gps_time": prev_tw_time,
                    "route": prev_route,
                    "matched_time": matched_str or prev_tw_time.strftime("%H:%M"),
                    "matched_dt": matched_dt or prev_tw_time,
                    "lat": prev_row.get("lat"),
                    "lon": prev_row.get("lon")
                })
                
                # 開始新一趟
                matched_dt, matched_str = _find_closest_schedule_time(
                    curr_route, tw_time, schedules, direction="closest"
                )
                transitions.append({
                    "type": "開班 (Start)",
                    "gps_time": tw_time,
                    "route": curr_route,
                    "matched_time": matched_str or tw_time.strftime("%H:%M"),
                    "matched_dt": matched_dt or tw_time,
                    "lat": row.get("lat"),
                    "lon": row.get("lon")
                })
                
                prev_operating = True
                continue

        # 正常狀態移轉檢測
        if not prev_operating and curr_operating:
            # 如果是當日第一筆 GPS 資料就是營運中，採用 direction="before" (發車時間前推)
            dir_mode = "before" if i == 0 else "closest"
            matched_dt, matched_str = _find_closest_schedule_time(route_name, tw_time, schedules, direction=dir_mode)
            transitions.append({
                "type": "開班 (Start)",
                "gps_time": tw_time,
                "route": route_name,
                "matched_time": matched_str or tw_time.strftime("%H:%M"),
                "matched_dt": matched_dt or tw_time,
                "lat": row.get("lat"),
                "lon": row.get("lon")
            })
        elif prev_operating and not curr_operating:
            matched_dt, matched_str = _find_closest_schedule_time(route_name, tw_time, schedules, direction="closest")
            transitions.append({
                "type": "收班 (End)",
                "gps_time": tw_time,
                "route": route_name,
                "matched_time": matched_str or tw_time.strftime("%H:%M"),
                "matched_dt": matched_dt or tw_time,
                "lat": row.get("lat"),
                "lon": row.get("lon")
            })
        
        prev_operating = curr_operating

    # 處理最後一筆 GPS 資料如果是營運中，補上 "收班 (End)"，採用 direction="after" (收班時間後推)
    if prev_operating and len(gps_data) > 0:
        last_row = gps_data[-1]
        last_tw_time = last_row["recorded_at_tw"]
        last_route = last_row.get("route_name", "")
        matched_dt, matched_str = _find_closest_schedule_time(last_route, last_tw_time, schedules, direction="after")
        transitions.append({
            "type": "收班 (End)",
            "gps_time": last_tw_time,
            "route": last_route,
            "matched_time": matched_str or last_tw_time.strftime("%H:%M"),
            "matched_dt": matched_dt or last_tw_time,
            "lat": last_row.get("lat"),
            "lon": last_row.get("lon")
        })
        prev_operating = False

    ongoing_trip = None

    # 組合成 Trips
    trips = []
    current_trip = None
    for t in transitions:
        if t["type"] == "開班 (Start)":
            if current_trip is not None:
                trips.append(current_trip)
            current_trip = {"start": t, "end": None}
        elif t["type"] == "收班 (End)":
            if current_trip is not None:
                current_trip["end"] = t
                trips.append(current_trip)
                current_trip = None
            else:
                trips.append({"start": None, "end": t})

    # 轉為 route_details 格式
    route_details = []
    for trip in trips:
        start = trip["start"]
        end = trip["end"]
        route_str = start["route"] if start else (end["route"] if end else "未知")
        start_str = start["matched_time"] if start else "未知"
        end_str = end["matched_time"] if end else "未知"
        route_details.append({
            "route": route_str,
            "start_time": start_str,
            "end_time": end_str
        })
    
    if ongoing_trip:
        route_details.append({
            "route": ongoing_trip["route"],
            "start_time": ongoing_trip["matched_time"],
            "end_time": "未完結/營運中"
        })

    # 計算中退
    break_details = []
    for i in range(len(trips) - 1):
        prev_trip = trips[i]
        next_trip = trips[i+1]
        if prev_trip["end"] and next_trip["start"]:
            end_dt = prev_trip["end"]["matched_dt"]
            start_dt = next_trip["start"]["matched_dt"]
            if end_dt and start_dt:
                duration_mins = int((start_dt - end_dt).total_seconds() / 60)
                break_details.append({
                    "start_time": prev_trip["end"]["matched_time"],
                    "end_time": next_trip["start"]["matched_time"],
                    "location": "場站/路邊",
                    "duration_mins": duration_mins,
                    "lat": prev_trip["end"].get("lat"),
                    "lon": prev_trip["end"].get("lon")
                })

    if trips and trips[-1]["end"] and ongoing_trip:
        end_dt = trips[-1]["end"]["matched_dt"]
        start_dt = ongoing_trip["matched_dt"]
        if end_dt and start_dt:
            duration_mins = int((start_dt - end_dt).total_seconds() / 60)
            break_details.append({
                "start_time": trips[-1]["end"]["matched_time"],
                "end_time": ongoing_trip["matched_time"],
                "location": "場站/路邊",
                "duration_mins": duration_mins,
                "lat": trips[-1]["end"].get("lat"),
                "lon": trips[-1]["end"].get("lon")
            })

    # 組成 route_summary
    summary_routes = []
    for r_detail in route_details:
        summary_routes.append(r_detail["route"])
    route_summary = " -> ".join(summary_routes) if summary_routes else "無營運路線"

    # 6. 加入 GPS最後位置到 route_details (供前端獨立顯示最後紀錄位置)
    if gps_data:
        last_gps = gps_data[-1]
        try:
            last_time_str = last_gps["recorded_at_tw"].strftime("%H:%M:%S")
            route_details.append({
                "is_last_gps": True,
                "lat": float(last_gps.get("lat")) if last_gps.get("lat") is not None else None,
                "lon": float(last_gps.get("lon")) if last_gps.get("lon") is not None else None,
                "time": last_time_str
            })
        except Exception as e:
            print(f"[BusService] Failed to append last_gps to route_details: {e}")

    plan_data = {
        "plate_number": plate_number,
        "date": date,
        "plan_name": "營運方案一",
        "route_summary": route_summary,
        "total_mileage": total_mileage,
        "route_details": route_details,
        "break_details": break_details
    }

    # 5. 存入資料庫 (Upsert)
    client.table("bus_operating_plans").upsert(plan_data, on_conflict="plate_number, date").execute()
    
    return plan_data

def fetch_unique_plates():
    """獲取資料庫中現有的唯一車號。"""
    client = Database.get_client()
    res = client.table("weekly_bus_gps_log").select("plate_number").execute()
    plates = sorted(list(set(r["plate_number"] for r in res.data)))
    return plates


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


def clear_bus_status_cache():
    """手動清除公車狀態的記憶體快取（例如在品情通報變更時）。"""
    global _status_cache
    _status_cache.clear()
    print("[BusService] Bus status memory cache has been cleared.")
