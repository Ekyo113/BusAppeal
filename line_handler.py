from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    AsyncApiClient,
    AsyncMessagingApi,
    AsyncMessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage,
    QuickReply,
    QuickReplyItem,
    PostbackAction,
    PushMessageRequest
)
from linebot.v3.webhooks import (
    MessageEvent, 
    TextMessageContent, 
    ImageMessageContent, 
    VideoMessageContent,
    PostbackEvent
)
from linebot.v3.webhook import WebhookParser
import httpx
from config import Config
from database import Database
from ai_service import AIService
import uuid
import asyncio

configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(Config.LINE_CHANNEL_SECRET)
# ai_service = AIService() # AI Disabled as per user request

async def handle_callback(body: str, signature: str):
    try:
        events = parser.parse(body, signature)
        for event in events:
            if isinstance(event, MessageEvent):
                if isinstance(event.message, TextMessageContent):
                    await handle_text_message(event)
                elif isinstance(event.message, (ImageMessageContent, VideoMessageContent)):
                    await handle_content_message(event)
            elif isinstance(event, PostbackEvent):
                await handle_postback(event)
    except InvalidSignatureError:
        raise
    except Exception as e:
        print(f"Error in handle_callback: {e}")

async def handle_text_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    # Get current state
    state_data = Database.get_user_state(user_id)
    step = state_data["step"] if state_data else "START"
    temp_data = state_data["temp_data"] if state_data else {}

    async with AsyncApiClient(configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)
        
        if text.lower() in ["取消", "退出", "reset"]:
            Database.clear_user_state(user_id)
            reply = "已取消。隨時傳送訊息可開始新的通報。"
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        if step == "START":
            # Question 1: Car Number
            Database.update_user_state(user_id, "GET_CAR_NUMBER", {})
            reply = "您好！開始通報流程。🚌\nQ1：請輸入您的「車號」："
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

        elif step == "GET_CAR_NUMBER":
            # Question 2: Description
            temp_data["car_number"] = text
            Database.update_user_state(user_id, "GET_DESCRIPTION", temp_data)
            reply = f"好的，車號為 {text}。\n\nQ2：請輸入「問題描述」：\n(您可以直接打字，也可以傳照片或影片)"
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

        elif step == "GET_DESCRIPTION":
            # Question 3: Confirmation
            temp_data["description"] = text
            temp_data["ai_summary"] = text[:30] # Use part of description as summary since AI is off
            Database.update_user_state(user_id, "CONFIRM", temp_data)
            
            summary_text = f"📋 通報內容確認：\n\n🚌 車號：{temp_data['car_number']}\n⚠️ 問題：{text}\n"
            if temp_data.get("media_urls"):
                summary_text += f"📸 已上傳 {len(temp_data['media_urls'])} 個媒體檔\n"
            
            summary_text += "\n資料正確嗎？請點擊下方按鈕送出。"
            
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=PostbackAction(label="✅ 是，確認送出", data="action=confirm", display_text="確認送出")),
                QuickReplyItem(action=PostbackAction(label="❌ 否，取消重填", data="action=cancel", display_text="取消重填"))
            ])
            
            await line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token, 
                messages=[TextMessage(text=summary_text, quick_reply=quick_reply)]
            ))

        elif step == "CONFIRM":
            if text == "確認送出":
                await save_and_notify(user_id, temp_data, line_bot_api, event.reply_token)
            else:
                reply = "請點擊下方的按鈕「確認送出」，或是輸入「取消」重新開始。"
                await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

async def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    
    state_data = Database.get_user_state(user_id)
    if not state_data or state_data["step"] != "CONFIRM":
        return

    temp_data = state_data["temp_data"]
    async with AsyncApiClient(configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)
        
        if data == "action=confirm":
            await save_and_notify(user_id, temp_data, line_bot_api, event.reply_token)
        elif data == "action=cancel":
            Database.clear_user_state(user_id)
            reply = "已取消通報。您可以再次輸入訊息開始新的通報。"
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

async def handle_content_message(event):
    user_id = event.source.user_id
    state_data = Database.get_user_state(user_id)
    
    if not state_data or state_data["step"] != "GET_DESCRIPTION":
        async with AsyncApiClient(configuration) as api_client:
            line_bot_api = AsyncMessagingApi(api_client)
            await line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token, 
                messages=[TextMessage(text="請先輸入車號並進入描述問題階段，再傳送圖片或影片。")]
            ))
        return

    temp_data = state_data["temp_data"]
    async with AsyncApiClient(configuration) as api_client:
        line_bot_blob_api = AsyncMessagingApiBlob(api_client)
        content = await line_bot_blob_api.get_message_content(event.message.id)
        
        ext = "jpg" if isinstance(event.message, ImageMessageContent) else "mp4"
        file_name = f"{uuid.uuid4()}.{ext}"
        public_url = Database.upload_media(content, file_name, f"image/{ext}" if ext=="jpg" else "video/mp4")
        
        if "media_urls" not in temp_data: temp_data["media_urls"] = []
        temp_data["media_urls"].append(public_url)
        
        Database.update_user_state(user_id, "GET_DESCRIPTION", temp_data)
        
        line_bot_api = AsyncMessagingApi(api_client)
        reply = f"已收到第 {len(temp_data['media_urls'])} 個媒體檔案！\n\n如已上傳完畢，請「輸入文字描述問題」即可進入下一步。"
        await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

async def save_and_notify(user_id, temp_data, line_bot_api, reply_token):
    temp_data["user_id"] = user_id
    Database.save_report(temp_data)
    Database.clear_user_state(user_id)
    
    await line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=reply_token, 
        messages=[TextMessage(text="✅ 通報已成功送出！維修售後將會通知您。")]
    ))
    
    msg = f"📣 【新通報】\n車號：{temp_data['car_number']}\n內容：{temp_data.get('description', '純媒體通報')}\n\n請前往後台查看詳情。"
    try:
        await line_bot_api.push_message(PushMessageRequest(to=Config.LINE_ADMIN_GROUP_ID, messages=[TextMessage(text=msg)]))
    except Exception as e:
        print(f"Push notification failed: {e}")
