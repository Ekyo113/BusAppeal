from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage,
    QuickReply,
    QuickReplyItem,
    PostbackAction,
    PushMessageRequest
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, VideoMessageContent
import httpx
from config import Config
from database import Database
from ai_service import AIService
import uuid

configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
ai_service = AIService()

async def handle_callback(body: str, signature: str):
    handler.handle(body, signature)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    # Get current state
    state_data = Database.get_user_state(user_id)
    step = state_data["step"] if state_data else "START"
    temp_data = state_data["temp_data"] if state_data else {}

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        if text.lower() in ["取消", "退出", "reset"]:
            Database.clear_user_state(user_id)
            reply = "已取消目前通報流程。隨時可以再傳訊息開始新的通報。"
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        if step == "START":
            Database.update_user_state(user_id, "GET_CAR_NUMBER", {})
            reply = "您好！我是品情通報助手。🚌\n請輸入您的「車號」："
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

        elif step == "GET_CAR_NUMBER":
            temp_data["car_number"] = text
            Database.update_user_state(user_id, "GET_DESCRIPTION", temp_data)
            reply = f"好的，車號為 {text}。\n\n請描述您遇到的「問題點」：\n(您可以直接傳送文字，或是傳送圖片/影片)"
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

        elif step == "GET_DESCRIPTION":
            temp_data["description"] = text
            # AI analyze
            import asyncio
            ai_result = asyncio.run(ai_service.analyze_report(text))
            temp_data["ai_summary"] = ai_result["summary"]
            temp_data["missing_info"] = ai_result["missing_info"]
            temp_data["suggestion"] = ai_result["suggestion"]
            
            Database.update_user_state(user_id, "CONFIRM", temp_data)
            
            summary_text = f"🤖 AI 整理結果：\n\n🚌 車號：{temp_data['car_number']}\n⚠️ 問題：{ai_result['summary']}\n🛠️ 建議：{ai_result['suggestion']}\n"
            
            if ai_result["missing_info"]:
                summary_text += f"\n❓ 有個小問題請補充：\n{ai_result['missing_info']}"
            
            summary_text += "\n\n請確認是否「送出」？"
            
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=PostbackAction(label="是，確認送出", data="action=confirm", display_text="確認送出")),
                QuickReplyItem(action=PostbackAction(label="否，重新輸入", data="action=cancel", display_text="取消重填"))
            ])
            
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token, 
                messages=[TextMessage(text=summary_text, quick_reply=quick_reply)]
            ))

        elif step == "CONFIRM":
            if text == "確認送出":
                save_and_notify(user_id, temp_data, line_bot_api, event.reply_token)
            else:
                reply = "請使用下方按鈕確認，或輸入「取消」重來。"
                line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

@handler.add(MessageEvent, message=(ImageMessageContent, VideoMessageContent))
def handle_content_message(event):
    user_id = event.source.user_id
    
    state_data = Database.get_user_state(user_id)
    if not state_data or state_data["step"] != "GET_DESCRIPTION":
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token, 
                messages=[TextMessage(text="請先輸入車號後，再傳送圖片或影片。")]
            ))
        return

    temp_data = state_data["temp_data"]
    
    with ApiClient(configuration) as api_client:
        line_bot_blob_api = MessagingApiBlob(api_client)
        content = line_bot_blob_api.get_message_content(event.message.id)
        
        # Determine file extension and type
        ext = "jpg" if isinstance(event.message, ImageMessageContent) else "mp4"
        content_type = "image/jpeg" if ext == "jpg" else "video/mp4"
        file_name = f"{uuid.uuid4()}.{ext}"
        
        # Upload to Supabase Storage
        public_url = Database.upload_media(content, file_name, content_type)
        
        if "media_urls" not in temp_data:
            temp_data["media_urls"] = []
        temp_data["media_urls"].append(public_url)
        
        Database.update_user_state(user_id, "GET_DESCRIPTION", temp_data)
        
        line_bot_api = MessagingApi(api_client)
        reply = "已收到媒體檔案！如有其他圖片請繼續傳送，或輸入「描述文字」來完成通報。"
        line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

def save_and_notify(user_id, temp_data, line_bot_api, reply_token):
    # Save to database
    temp_data["user_id"] = user_id
    Database.save_report(temp_data)
    Database.clear_user_state(user_id)
    
    # Reply to driver
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=reply_token, 
        messages=[TextMessage(text="✅ 通報已成功送出！維修售後將會通知您。")]
    ))
    
    # Notify Admin Group
    msg = f"📣 【新通報】\n車號：{temp_data['car_number']}\n描述：{temp_data.get('description', '純媒體通報')}\n摘要：{temp_data['ai_summary']}\n\n請前往後台查看詳情。"
    try:
        line_bot_api.push_message(PushMessageRequest(to=Config.LINE_ADMIN_GROUP_ID, messages=[TextMessage(text=msg)]))
    except Exception as e:
        print(f"Push notification failed: {e}")
