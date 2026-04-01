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

router = APIRouter(prefix="/admin")

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
    Database.update_report_status(report_id, status)
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
    Database.update_report_solution(report_id, solution)
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
