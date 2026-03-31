from supabase import create_client, Client
from config import Config
from datetime import datetime
import json

class Database:
    _instance: Client = None

    @classmethod
    def get_client(cls) -> Client:
        if cls._instance is None:
            cls._instance = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)
        return cls._instance

    @classmethod
    def get_user_state(cls, user_id: str):
        client = cls.get_client()
        response = client.table("conversation_state").select("*").eq("user_id", user_id).execute()
        return response.data[0] if response.data else None

    @classmethod
    def update_user_state(cls, user_id: str, step: str, temp_data: dict):
        client = cls.get_client()
        data = {
            "user_id": user_id,
            "step": step,
            "temp_data": temp_data,
            "updated_at": datetime.utcnow().isoformat()
        }
        # Upsert
        return client.table("conversation_state").upsert(data).execute()

    @classmethod
    def clear_user_state(cls, user_id: str):
        client = cls.get_client()
        return client.table("conversation_state").delete().eq("user_id", user_id).execute()

    @classmethod
    def save_report(cls, data: dict):
        client = cls.get_client()
        report = {
            "car_number": data.get("car_number"),
            "description": data.get("description"),
            "ai_summary": data.get("ai_summary"),
            "status": "待處理",
            "driver_line_user_id": data.get("user_id"),
            "media_urls": data.get("media_urls", []),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        return client.table("reports").insert(report).execute()

    @classmethod
    def get_all_reports(cls):
        client = cls.get_client()
        return client.table("reports").select("*").order("created_at", desc=True).execute()

    @classmethod
    def delete_report(cls, report_id: str):
        client = cls.get_client()
        return client.table("reports").delete().eq("id", report_id).execute()

    @classmethod
    def update_report_status(cls, report_id: str, status: str):
        client = cls.get_client()
        return client.table("reports").update({
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", report_id).execute()

    @classmethod
    def upload_media(cls, file_content: bytes, file_name: str, content_type: str):
        client = cls.get_client()
        # Upload to 'bus-media' bucket
        path = f"reports/{datetime.now().strftime('%Y%m%d')}/{file_name}"
        client.storage.from_("bus-media").upload(
            path=path,
            file=file_content,
            file_options={"content-type": content_type}
        )
        # Get public URL
        return client.storage.from_("bus-media").get_public_url(path)
