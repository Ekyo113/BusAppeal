from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)
from config import Config
from database import Database

class NotificationService:
    @staticmethod
    def send_completion_notify(report_id: str):
        """
        根據 report_id 發送維修完成通知給司機與管理群
        """
        try:
            # 取得通報詳情以獲取司機 ID 與車號
            client = Database.get_client()
            res = client.table("reports").select("*").eq("id", report_id).execute()
            if not res.data:
                return
            
            report = res.data[0]
            car_number = report.get("car_number", "-")
            driver_line_id = report.get("driver_line_user_id")

            configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)
            
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                
                # 1. 通知司機
                if driver_line_id:
                    try:
                        driver_msg = f"🔧 維修進度通知\n\n您通報的車輛 {car_number} 已維修完成！\n感謝您的回報。"
                        line_bot_api.push_message(PushMessageRequest(
                            to=driver_line_id, 
                            messages=[TextMessage(text=driver_msg)]
                        ))
                    except Exception as e:
                        print(f"Notify Driver {driver_line_id} failed: {e}")

                # 2. 通知管理群 (LINE_NOTIFY_ID)
                admin_msg = f"✅ 【維修完成】\n車號：{car_number}\n該單據已標記為已完成。"
                notify_ids = [id.strip() for id in Config.LINE_NOTIFY_ID.split(",") if id.strip()]
                for notify_id in notify_ids:
                    # 簡單檢查 ID 格式 (Messaging API 必須以 U, C, R 開頭)
                    if not any(notify_id.startswith(p) for p in ['U', 'C', 'R']):
                        print(f"NotificationService: Skip invalid notify_id: {notify_id}")
                        continue
                        
                    try:
                        line_bot_api.push_message(PushMessageRequest(
                            to=notify_id, 
                            messages=[TextMessage(text=admin_msg)]
                        ))
                    except Exception as e:
                        print(f"Notify Admin Group {notify_id} failed: {e}")
        except Exception as e:
            print(f"NotificationService Error: {e}")
