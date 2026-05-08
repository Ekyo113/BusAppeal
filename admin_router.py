from fastapi import APIRouter, Header, HTTPException, Body
from database import Database
from config import Config
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)
from datetime import datetime, timedelta
import pytz
from fastapi.responses import StreamingResponse
from export_service import ExportService

router = APIRouter(prefix="/admin")

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
    if token != Config.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.get("/reports")
async def get_reports(token: str = Header(None)):
    verify_token(token)
    response = Database.get_all_reports()
    return response.data

@router.patch("/reports/{report_id}")
async def update_status(report_id: str, data: dict = Body(...), token: str = Header(None)):
    verify_token(token)
    status = data.get("status")
    mileage = data.get("mileage")
    Database.update_report_status(report_id, status, mileage)
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
    
    # Get report details
    client = Database.get_client()
    report = client.table("reports").select("*").eq("id", report_id).execute().data[0]
    
    driver_id = report["driver_line_user_id"]
    car_number = report["car_number"]
    
    # Push message to driver
    configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        msg = f"🔧 維修進度通知\n\n您通報的車輛 {car_number} 已維修完成！\n感謝您的回報。"
        line_bot_api.push_message(PushMessageRequest(to=driver_id, messages=[TextMessage(text=msg)]))
        
        # Also notify Admin Notify Group(s)
        admin_msg = f"✅ 【維修完成】\n車號：{car_number}\n該單據已標記為已完成。"
        notify_ids = [id.strip() for id in Config.LINE_NOTIFY_ID.split(",") if id.strip()]
        for notify_id in notify_ids:
            try:
                line_bot_api.push_message(PushMessageRequest(to=notify_id, messages=[TextMessage(text=admin_msg)]))
            except Exception as e:
                print(f"Push completion to {notify_id} failed: {e}")
    
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
