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
    MessageAction,
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
import json

configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(Config.LINE_CHANNEL_SECRET)
ai_service = AIService()

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
    source_type = event.source.type
    source_id = getattr(event.source, "group_id", getattr(event.source, "room_id", user_id))
    print(f"DEBUG: Message source type: {source_type}, source ID: {source_id}")

    # ── 管理群訊息處理 ──
    admin_group_ids = [gid.strip() for gid in (Config.LINE_NOTIFY_ID or "").split(",") if gid.strip()]
    if source_type == "group" and source_id in admin_group_ids:
        await handle_group_message(event, user_id, source_id, text)
        return

    # [NEW] Check if this is a private chat. If not, don't trigger the flow.
    if source_type != "user":
        print(f"DEBUG: Skipping message because source type is {source_type}")
        return

    # Get current state
    print(f"DEBUG: Fetching state for {user_id}...")
    state_data = Database.get_user_state(user_id)
    step = state_data["step"] if state_data else "START"
    print(f"DEBUG: Current step: {step}")
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

        elif step == "GET_MEDIA_PROMPT":
            # If they type instead of clicking button
            if text in ["是", "要", "好", "上傳", "照片", "影片"]:
                Database.update_user_state(user_id, "WAIT_MEDIA", temp_data)
                reply = "請開始傳送照片或影片（可傳送多張）。\n傳送完畢後，請點擊下方按鈕進行下一步。"
                quick_reply = QuickReply(items=[
                    QuickReplyItem(action=PostbackAction(label="✅ 預覽並送出", data="action=confirm_preview", display_text="預覽並送出"))
                ])
                await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply, quick_reply=quick_reply)]))
            else:
                # Default to no and show preview
                Database.update_user_state(user_id, "CONFIRM", temp_data)
                summary_text = f"📋 通報內容預覽：\n\n🚌 車號：{temp_data['car_number']}\n📝 描述：{temp_data['description']}\n\n確認內容無誤並送出通報嗎？"
                quick_reply = QuickReply(items=[
                    QuickReplyItem(action=PostbackAction(label="✅ 確認送出", data="action=final_submit", display_text="確認送出")),
                    QuickReplyItem(action=PostbackAction(label="❌ 取消重填", data="action=cancel", display_text="取消重填"))
                ])
                await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=summary_text, quick_reply=quick_reply)]))

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

async def handle_group_message(event, sender_user_id: str, group_id: str, text: str):
    """處理管理群發送的維修結果訊息，自動更新對應通報單。"""
    async with AsyncApiClient(configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)

        parsed_items = await ai_service.parse_group_message(text)

        if not parsed_items:
            await line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="⚠️ 無法解析訊息內容，請確認格式（車號 + 里程 + 處理方案）。")]
            ))
            return

        reply_lines = []
        deferred_choices = []  # 需要多筆選擇的項目

        for item in parsed_items:
            car_number = item.get("car_number", "").strip()
            mileage    = item.get("mileage", "").strip()
            solution   = item.get("solution", "").strip()
            sol_type   = item.get("solution_type", "維修").strip()

            if not car_number or not solution:
                reply_lines.append(f"⚠️ 無法識別某筆資料，請重新確認。")
                continue

            pending = Database.get_pending_reports_by_car(car_number)

            if len(pending) == 0:
                # 規則7：無待處理項目 → 直接新建已完成通報
                Database.create_completed_report_from_group(
                    car_number=car_number, solution=solution, mileage=mileage,
                    handler_id=sender_user_id, solution_type=sol_type
                )
                reply_lines.append(f"✅ {car_number}：已新增並完成（{sol_type}）\n   方案：{solution}" + (f"\n   里程：{mileage} km" if mileage else ""))

            elif len(pending) == 1:
                # 只有一筆 → 直接更新
                Database.update_report_solution(
                    report_id=pending[0]["id"], solution=solution, mileage=mileage,
                    handler_id=sender_user_id, solution_type=sol_type
                )
                reply_lines.append(f"✅ {car_number}：已完成（{sol_type}）\n   方案：{solution}" + (f"\n   里程：{mileage} km" if mileage else ""))

            else:
                # 多筆 → 暫存，等用戶選擇
                deferred_choices.append({
                    "car_number": car_number,
                    "mileage": mileage,
                    "solution": solution,
                    "solution_type": sol_type,
                    "pending": pending,
                    "sender_user_id": sender_user_id
                })

        # 先回覆已完成的結果
        if reply_lines and not deferred_choices:
            await line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="\n\n".join(reply_lines))]
            ))
        elif deferred_choices:
            # 有需要選擇的項目：先存入 conversation_state，再發選單
            first = deferred_choices[0]
            pending = first["pending"]
            car = first["car_number"]

            # 將所有資訊存入 state（用 group_id 當 key）
            state_payload = {
                "pending_choice": first,
                "remaining": deferred_choices[1:],
                "done_lines": reply_lines
            }
            Database.update_user_state(group_id, "GROUP_CHOOSE", state_payload)

            choice_text = f"🔧 {car} 有 {len(pending)} 筆未完成項目，請選擇要更新哪一筆："
            qr_items = []
            labels = "abcdefghij"
            for i, p in enumerate(pending[:10]):
                created = p["created_at"][:10]
                label = f"{labels[i]}. {p['description'][:15]}({created})"
                qr_items.append(
                    QuickReplyItem(
                        action=PostbackAction(
                            label=label[:20],
                            data=f"action=group_select&idx={i}&group_id={group_id}",
                            display_text=label[:20]
                        )
                    )
                )
            # 加一個「全部套用第一筆」快捷
            qr_items.append(
                QuickReplyItem(
                    action=PostbackAction(
                        label="⏭️ 套用最早一筆",
                        data=f"action=group_select&idx=0&group_id={group_id}",
                        display_text="套用最早一筆"
                    )
                )
            )
            full_text = ("\n\n".join(reply_lines) + "\n\n" if reply_lines else "") + choice_text
            await line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=full_text, quick_reply=QuickReply(items=qr_items))]
            ))


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

    async with AsyncApiClient(configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)

        # ── 群組選擇回呼（不依賴 user state，改用 group_id 查詢） ──
        if data.startswith("action=group_select"):
            params = dict(kv.split("=", 1) for kv in data.split("&") if "=" in kv)
            idx = int(params.get("idx", 0))
            gid = params.get("group_id", "")

            grp_state = Database.get_user_state(gid)
            if not grp_state:
                await line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="⚠️ 選擇逾時，請重新發送處理結果。")]
                ))
                return

            payload    = grp_state["temp_data"]
            choice     = payload["pending_choice"]
            remaining  = payload.get("remaining", [])
            done_lines = payload.get("done_lines", [])

            chosen_report = choice["pending"][idx]
            Database.update_report_solution(
                report_id=chosen_report["id"],
                solution=choice["solution"],
                mileage=choice["mileage"],
                handler_id=choice["sender_user_id"],
                solution_type=choice["solution_type"]
            )
            car      = choice["car_number"]
            sol      = choice["solution"]
            sol_type = choice["solution_type"]
            mileage  = choice["mileage"]
            done_lines.append(
                f"✅ {car}：已完成（{sol_type}）\n   方案：{sol}" + (f"\n   里程：{mileage} km" if mileage else "")
            )

            if remaining:
                next_choice = remaining[0]
                Database.update_user_state(gid, "GROUP_CHOOSE", {
                    "pending_choice": next_choice,
                    "remaining": remaining[1:],
                    "done_lines": done_lines
                })
                next_pending = next_choice["pending"]
                next_car = next_choice["car_number"]
                choice_text = f"🔧 {next_car} 有 {len(next_pending)} 筆未完成項目，請選擇要更新哪一筆："
                qr_items = []
                for i, p in enumerate(next_pending[:10]):
                    label = f"{'abcdefghij'[i]}. {p['description'][:15]}({p['created_at'][:10]})"
                    qr_items.append(QuickReplyItem(action=PostbackAction(
                        label=label[:20],
                        data=f"action=group_select&idx={i}&group_id={gid}",
                        display_text=label[:20]
                    )))
                full_text = ("\n\n".join(done_lines) + "\n\n" if done_lines else "") + choice_text
                await line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=full_text, quick_reply=QuickReply(items=qr_items))]
                ))
            else:
                Database.clear_user_state(gid)
                await line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="\n\n".join(done_lines))]
                ))
            return

        # ── 一般私訊 Postback（依賴 user state） ──
        state_data = Database.get_user_state(user_id)
        if not state_data:
            return
        step = state_data["step"]
        temp_data = state_data["temp_data"]

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
        source_type = event.source.type
        source_id = getattr(event.source, "group_id", getattr(event.source, "room_id", user_id))
        print(f"DEBUG: Media from {display_name} ({user_id}). Source type: {source_type}")

    # [NEW] Check if this is a private chat. If not, don't trigger the flow.
    if source_type != "user":
        print(f"DEBUG: Skipping media because source type is {source_type}")
        return

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
    # Use first 20 chars of description as summary instead of AI
    temp_data["ai_summary"] = temp_data.get("description", "")[:20]
    Database.save_report(temp_data)
    Database.clear_user_state(user_id)
    
    await line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=reply_token, 
        messages=[TextMessage(text="✅ 通報已成功送出！維修售後將會通知您。")]
    ))
    
    car_number = temp_data.get("car_number", "")
    msg = f"📣 【新通報】\n車號：{car_number}\n內容：{temp_data.get('description', '純媒體通報')}\n\n請前往後台查看詳情。"
    
    # 1. Fetch dynamic vendor group IDs based on exact car number match
    vendor_ids = Database.get_vendor_groups(car_number)
    print(f"DEBUG Routing: Car {car_number} matched vendor groups: {vendor_ids}")

    # 2. Get default Admin/Receiver IDs from config
    notify_ids = [id.strip() for id in Config.LINE_NOTIFY_ID.split(",") if id.strip()]
    receive_ids = [id.strip() for id in Config.LINE_RECEIVE_ID.split(",") if id.strip()]
    
    # 3. Merge all targets (Set to ensure uniqueness)
    all_targets = list(set(notify_ids + receive_ids + vendor_ids))
    print(f"DEBUG Routing: Final push target IDs: {all_targets}")

    for target_id in all_targets:
        try:
            await line_bot_api.push_message(PushMessageRequest(to=target_id, messages=[TextMessage(text=msg)]))
        except Exception as e:
            print(f"Push notification to {target_id} failed: {e}")
