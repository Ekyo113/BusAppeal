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
    
    # Debug: Output source ID (User, Group, or Room) to logs for easy configuration
    source_id = getattr(event.source, "group_id", getattr(event.source, "room_id", user_id))
    print(f"DEBUG: Message from {user_id}. Source ID (use this for LINE_NOTIFY_ID): {source_id}")
    
    # Get current state
    state_data = Database.get_user_state(user_id)
    step = state_data["step"] if state_data else "START"
    temp_data = state_data["temp_data"] if state_data else {}

    async with AsyncApiClient(configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)
        
        if text.lower() in ["取消", "退出", "reset"]:
            Database.clear_user_state(user_id)
            reply = "已取消通報流程。隨時可以再傳訊息開始新通報。"
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        if step == "START":
            # Treat first message as car number
            temp_data["car_number"] = text
            Database.update_user_state(user_id, "VERIFY_CAR_NUMBER", temp_data)
            
            reply = f"您好！已收到車號：{text}\n請問車號正確嗎？"
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=PostbackAction(label="✅ 正確", data="action=car_ok", display_text="正確")),
                QuickReplyItem(action=PostbackAction(label="❌ 重新輸入", data="action=car_retry", display_text="重新輸入"))
            ])
            await line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token, 
                messages=[TextMessage(text=reply, quick_reply=quick_reply)]
            ))

        elif step == "VERIFY_CAR_NUMBER":
            # If they type instead of clicking button
            if text in ["正確", "是", "OK"]:
                await ask_for_description(user_id, temp_data, line_bot_api, event.reply_token)
            else:
                await ask_for_car_number_again(user_id, line_bot_api, event.reply_token)

        elif step == "GET_CAR_NUMBER":
            temp_data["car_number"] = text
            Database.update_user_state(user_id, "VERIFY_CAR_NUMBER", temp_data)
            reply = f"已收到車號：{text}\n請問正確嗎？"
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=PostbackAction(label="✅ 正確", data="action=car_ok", display_text="正確")),
                QuickReplyItem(action=PostbackAction(label="❌ 重新輸入", data="action=car_retry", display_text="重新輸入"))
            ])
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply, quick_reply=quick_reply)]))

        elif step == "GET_DESCRIPTION":
            # Step 2: Ask if Media is needed
            temp_data["description"] = text
            Database.update_user_state(user_id, "GET_MEDIA_PROMPT", temp_data)
            
            reply = "收到描述。最後一步：\n\n3. 是否需要上傳「照片或影片」？"
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=PostbackAction(label="📷 我要傳照片/影片", data="action=need_media", display_text="我要傳照片/影片")),
                QuickReplyItem(action=PostbackAction(label="✅ 不用，直接送出", data="action=confirm_preview", display_text="直接送出"))
            ])
            await line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token, 
                messages=[TextMessage(text=reply, quick_reply=quick_reply)]
            ))

        elif step == "WAIT_MEDIA":
            reply = "請傳送照片或影片。上傳完畢後請點擊下方「預覽並送出」按鈕。"
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=PostbackAction(label="✅ 預覽並送出", data="action=confirm_preview", display_text="預覽並送出"))
            ])
            await line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token, 
                messages=[TextMessage(text=reply, quick_reply=quick_reply)]
            ))

        elif step == "CONFIRM":
            await save_and_notify(user_id, temp_data, line_bot_api, event.reply_token)

async def ask_for_description(user_id, temp_data, line_bot_api, reply_token):
    Database.update_user_state(user_id, "GET_DESCRIPTION", temp_data)
    reply = f"好的，車號 {temp_data['car_number']} 已確認。\n\n2. 請輸入「問題描述」："
    await line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)]))

async def ask_for_car_number_again(user_id, line_bot_api, reply_token):
    Database.update_user_state(user_id, "GET_CAR_NUMBER", {})
    reply = "沒問題，請重新輸入您的「車號」："
    await line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)]))

async def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    
    state_data = Database.get_user_state(user_id)
    if not state_data: return
    step = state_data["step"]
    temp_data = state_data["temp_data"]
    
    async with AsyncApiClient(configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)
        
        if data == "action=car_ok":
            await ask_for_description(user_id, temp_data, line_bot_api, event.reply_token)
        elif data == "action=car_retry":
            await ask_for_car_number_again(user_id, line_bot_api, event.reply_token)
        elif data == "action=need_media":
            Database.update_user_state(user_id, "WAIT_MEDIA", temp_data)
            reply = "請開始傳送照片或影片（可傳送多張）。\n傳送完畢後，請點擊下方按鈕進行下一步。"
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=PostbackAction(label="✅ 預覽並送出", data="action=confirm_preview", display_text="預覽並送出"))
            ])
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply, quick_reply=quick_reply)]))
        
        elif data == "action=confirm_preview":
            Database.update_user_state(user_id, "CONFIRM", temp_data)
            media_count = len(temp_data.get("media_urls", []))
            summary_text = f"📋 通報內容預覽：\n\n🚌 車號：{temp_data['car_number']}\n📝 描述：{temp_data['description']}\n🖼️ 媒體：{media_count} 個檔案\n\n確認內容無誤並送出通報嗎？"
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=PostbackAction(label="✅ 確認送出", data="action=final_submit", display_text="確認送出")),
                QuickReplyItem(action=PostbackAction(label="❌ 取消重填", data="action=cancel", display_text="取消重填"))
            ])
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=summary_text, quick_reply=quick_reply)]))
            
        elif data == "action=final_submit":
            await save_and_notify(user_id, temp_data, line_bot_api, event.reply_token)
            
        elif data == "action=cancel":
            Database.clear_user_state(user_id)
            reply = "已取消。如需重新報修請再次傳送訊息。"
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

async def handle_content_message(event):
    user_id = event.source.user_id
    
    async with AsyncApiClient(configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)
        profile = await line_bot_api.get_profile(user_id)
        display_name = profile.display_name
        
        # Debug: Output source ID (User or Group) to logs
        source_id = getattr(event.source, "group_id", getattr(event.source, "room_id", user_id))
        print(f"DEBUG: Message from {display_name} ({user_id}). Source ID (for config): {source_id}")

    state_data = Database.get_user_state(user_id)
    
    if not state_data or state_data["step"] not in ["GET_DESCRIPTION", "WAIT_MEDIA", "GET_MEDIA_PROMPT"]:
        async with AsyncApiClient(configuration) as api_client:
            line_bot_api = AsyncMessagingApi(api_client)
            await line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token, 
                messages=[TextMessage(text="請先依照步驟輸入車號與問題描述後，再上傳媒體檔案。")]
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
        
        Database.update_user_state(user_id, state_data["step"], temp_data)
        
        line_bot_api = AsyncMessagingApi(api_client)
        reply = f"已收到第 {len(temp_data['media_urls'])} 個媒體檔案！\n\n還可以繼續傳送，或點擊下方按鈕預覽並送出。"
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=PostbackAction(label="✅ 預覽並送出", data="action=confirm_preview", display_text="預覽並送出"))
        ])
        await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply, quick_reply=quick_reply)]))

async def save_and_notify(user_id, temp_data, line_bot_api, reply_token):
    temp_data["user_id"] = user_id
    temp_data["ai_summary"] = temp_data.get("description", "")[:20]
    Database.save_report(temp_data)
    Database.clear_user_state(user_id)
    
    await line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=reply_token, 
        messages=[TextMessage(text="✅ 通報已成功送出！維修售後將會通知您。")]
    ))
    
    msg = f"📣 【新通報】\n車號：{temp_data['car_number']}\n內容：{temp_data.get('description', '純媒體通報')}\n\n請前往後台查看詳情。"
    
    # Notify Admin Groups
    notify_ids = [id.strip() for id in Config.LINE_NOTIFY_ID.split(",") if id.strip()]
    receive_ids = [id.strip() for id in Config.LINE_RECEIVE_ID.split(",") if id.strip()]
    
    all_targets = list(set(notify_ids + receive_ids))
    for target_id in all_targets:
        try:
            await line_bot_api.push_message(PushMessageRequest(to=target_id, messages=[TextMessage(text=msg)]))
        except Exception as e:
            print(f"Push notification to {target_id} failed: {e}")
