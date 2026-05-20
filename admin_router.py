from fastapi import APIRouter, Header, HTTPException, Body
import asyncio
from database import Database
from config import Config
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)
from notification_service import NotificationService
from datetime import datetime, timedelta
import pytz
from fastapi.responses import StreamingResponse
from export_service import ExportService
import bus_service

router = APIRouter(prefix="/admin")

# Concurrency flags to prevent multiple overlapping heavy jobs (B-04)
is_syncing = False
is_analyzing = False

@router.get("/weekly_gps_log")
async def get_weekly_gps_log(date: str = None, token: str = Header(None)):
    verify_token(token)
    if not date:
        tz = pytz.timezone('Asia/Taipei')
        date = datetime.now(tz).strftime('%Y-%m-%d')
        
    client = Database.get_client()
    
    start_time = f"{date}T00:00:00+08:00"
    end_time = f"{date}T23:59:59+08:00"
    
    response = client.table("weekly_bus_gps_log")\
        .select("*")\
        .gte("recorded_at", start_time)\
        .lte("recorded_at", end_time)\
        .order("plate_number")\
        .order("recorded_at")\
        .execute()
        
    return response.data

def verify_token(token: str):
    if not Config.ADMIN_SECRET_KEY or token != Config.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.get("/reports")
async def get_reports(token: str = Header(None)):
    verify_token(token)
    response = Database.get_all_reports()
    return response.data

@router.patch("/reports/{report_id}")
async def update_report(report_id: str, data: dict = Body(...), token: str = Header(None)):
    verify_token(token)
    status = data.get("status")
    mileage = data.get("mileage")
    
    # If it is a simple status transition (backward compatibility)
    if "status" in data and len(data) <= 2:
        Database.update_report_status(report_id, status, mileage)
    else:
        # Otherwise, general fields update
        if "solution" in data and data["solution"]:
            data["status"] = "已完成"
            data["solution_at"] = datetime.utcnow().isoformat()
            if "completed_at" not in data or not data["completed_at"]:
                data["completed_at"] = datetime.utcnow().isoformat()
        Database.update_report_fields(report_id, data)
    return {"status": "success"}

@router.delete("/reports/{report_id}")
async def delete_report(report_id: str, token: str = Header(None)):
    verify_token(token)
    Database.delete_report(report_id)
    return {"status": "success"}

@router.patch("/reports/{report_id}/solution")
async def update_solution(report_id: str, data: dict = Body(...), token: str = Header(None)):
    verify_token(token)
    solution = data.get("solution")
    mileage = data.get("mileage")
    Database.update_report_solution(report_id, solution, mileage)
    return {"status": "success"}

@router.post("/reports/{report_id}/notify")
async def notify_driver(report_id: str, token: str = Header(None)):
    verify_token(token)
    NotificationService.send_completion_notify(report_id)
    return {"status": "sent"}

@router.get("/export")
async def export_pdf(type: str, start: str, end: str, token: str = Header(None)):
    """
    導出 PDF 報表
    type: 'report' or 'replacement'
    start/end: YYYY-MM-DD
    """
    verify_token(token)
    
    # 從資料庫抓取資料
    reports = Database.get_reports_for_export(start, end, type)
    
    if not reports:
        raise HTTPException(status_code=404, detail="該日期範圍內無已完成紀錄")
    
    # 產生 PDF
    # 產生 PDF
    pdf_buffer = ExportService.generate_pdf(reports, type)
    filename = f"{'通報紀錄' if type == 'report' else '換件紀錄'}_{start}_to_{end}.pdf"
    
    # 處理中文字元檔名編碼
    from urllib.parse import quote
    encoded_filename = quote(filename)
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    )

@router.get("/bus_plans")
async def get_bus_plans(plate_number: str = None, date: str = None, token: str = Header(None)):
    verify_token(token)
    client = Database.get_client()
    query = client.table("bus_operating_plans").select("*")
    if plate_number:
        query = query.eq("plate_number", plate_number)
    if date:
        query = query.eq("date", date)
    
    res = query.order("date", desc=True).execute()
    return res.data

@router.get("/bus_plates")
async def get_bus_plates(token: str = Header(None)):
    verify_token(token)
    plates = bus_service.fetch_unique_plates()
    return {"plates": plates}

@router.post("/bus_plans/sync_schedules")
async def sync_schedules(city: str = "Kaohsiung", token: str = Header(None)):
    global is_syncing
    verify_token(token)
    if is_syncing:
        raise HTTPException(status_code=429, detail="同步時刻表任務正在進行中，請稍後再試。")
    is_syncing = True
    try:
        count = bus_service.sync_route_schedules(city)
        return {"status": "success", "count": count}
    finally:
        is_syncing = False

@router.post("/bus_plans/analyze_selected")
async def analyze_selected_vehicle(plate_number: str = Body(..., embed=True), token: str = Header(None)):
    global is_analyzing
    verify_token(token)
    if is_analyzing:
        raise HTTPException(status_code=429, detail="AI 分析任務正在進行中，請稍後再試。")
    is_analyzing = True
    try:
        client = Database.get_client()
        
        # 1. 找出該車號的所有日期
        res = client.table("weekly_bus_gps_log")\
            .select("recorded_at")\
            .eq("plate_number", plate_number)\
            .execute()
        
        unique_dates = sorted(list(set(row["recorded_at"].split("T")[0] for row in res.data)), reverse=True)
        
        results = []
        for date in unique_dates:
            # 檢查是否已分析過
            existing = client.table("bus_operating_plans")\
                .select("id")\
                .eq("plate_number", plate_number)\
                .eq("date", date)\
                .limit(1)\
                .execute()
            
            if existing.data:
                continue
                
            plan = await bus_service.generate_bus_plan(plate_number, date)
            if plan:
                results.append(plan)
                await asyncio.sleep(15)
                
        return {"status": "success", "analyzed_count": len(results)}
    finally:
        is_analyzing = False

@router.post("/bus_plans/analyze_all")
async def analyze_all_logs(token: str = Header(None)):
    global is_analyzing
    verify_token(token)
    if is_analyzing:
        raise HTTPException(status_code=429, detail="AI 分析任務正在進行中，請稍後再試。")
    is_analyzing = True
    try:
        client = Database.get_client()
        
        # 1. 找出所有已存在的方案，避免重複分析
        existing_plans_res = client.table("bus_operating_plans").select("plate_number, date").execute()
        existing_pairs = set()
        for row in existing_plans_res.data:
            existing_pairs.add((row["plate_number"], row["date"]))

        # 2. 找出所有有 GPS 紀錄的車號與日期 (僅抓取最近 30 天，且只取必要欄位)
        res = client.table("weekly_bus_gps_log")\
            .select("plate_number, recorded_at")\
            .execute()
        
        unique_pairs = set()
        for row in res.data:
            date = row["recorded_at"].split("T")[0]
            plate = row["plate_number"]
            
            # [測試模式] 目前僅分析 EAA-779
            if plate != "EAA-779":
                continue
                
            pair = (plate, date)
            if pair not in existing_pairs:
                unique_pairs.add(pair)
        
        if not unique_pairs:
            return {"status": "success", "message": "所有數據皆已分析完成，無須重複分析。", "analyzed_count": 0}

        results = []
        for plate, date in unique_pairs:
            plan = await bus_service.generate_bus_plan(plate, date)
            if plan:
                results.append(plan)
                
            # 配額保護：每 15 秒呼叫一次 (避免頻繁觸發 429)
            await asyncio.sleep(15)
                
        return {"status": "success", "analyzed_count": len(results)}
    finally:
        is_analyzing = False
