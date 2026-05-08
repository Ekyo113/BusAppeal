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
    def get_vendor_groups(cls, car_number: str) -> list:
        """
        Retrieves matching LINE Group IDs from the vendor_mappings table
        based on an EXACT match of the car_number.
        """
        if not car_number:
            return []
            
        client = cls.get_client()
        try:
            # Query the vendor_mappings table for an exact match on 'pattern'
            response = client.table("vendor_mappings").select("group_id").eq("pattern", car_number).execute()
            if response.data:
                # Return all matching group IDs (usually only one due to UNIQUE constraint)
                return [item["group_id"] for item in response.data]
        except Exception as e:
            print(f"Database Error in get_vendor_groups: {e}")
            # Fallback to the admin groups only if query fails (by returning empty vendor list)
            
        return []

    @classmethod
    def get_all_reports(cls):
        client = cls.get_client()
        return client.table("reports").select("*").order("created_at", desc=True).execute()

    @classmethod
    def delete_report(cls, report_id: str):
        client = cls.get_client()
        return client.table("reports").delete().eq("id", report_id).execute()

    @classmethod
    def update_report_status(cls, report_id: str, status: str, mileage: str = None):
        client = cls.get_client()
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if status == "已完成":
            update_data["completed_at"] = datetime.utcnow().isoformat()
            if mileage:
                update_data["mileage"] = mileage
                
        return client.table("reports").update(update_data).eq("id", report_id).execute()

    @classmethod
    def get_pending_reports_by_car(cls, car_number: str) -> list:
        """查詢指定車號的所有未完成通報（狀態不為「已完成」）"""
        client = cls.get_client()
        try:
            response = (
                client.table("reports")
                .select("id, car_number, description, status, created_at")
                .eq("car_number", car_number)
                .neq("status", "已完成")
                .order("created_at", desc=False)
                .execute()
            )
            return response.data
        except Exception as e:
            print(f"Database Error in get_pending_reports_by_car: {e}")
            return []

    @classmethod
    def update_report_solution(cls, report_id: str, solution: str, mileage: str = None,
                                handler_id: str = None, handler_name: str = "市場組",
                                solution_type: str = None):
        client = cls.get_client()
        update_data = {
            "solution": solution,
            "solution_at": datetime.utcnow().isoformat(),
            "status": "已完成",
            "completed_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "handler_name": handler_name,
        }
        if mileage:
            update_data["mileage"] = mileage
        if handler_id:
            update_data["handler_id"] = handler_id
        if solution_type:
            update_data["solution_type"] = solution_type

        return client.table("reports").update(update_data).eq("id", report_id).execute()

    @classmethod
    def create_completed_report_from_group(
        cls, car_number: str, solution: str, mileage: str = None,
        handler_id: str = None, handler_name: str = "市場組",
        solution_type: str = None
    ):
        """直接從管理群新建一筆已完成通報（無對應待處理項目時使用）"""
        client = cls.get_client()
        now = datetime.utcnow().isoformat()
        report = {
            "car_number": car_number,
            "description": f"[管理群直接完成] {solution}",
            "ai_summary": solution[:20],
            "solution": solution,
            "solution_type": solution_type or "維修",
            "status": "已完成",
            "handler_name": handler_name,
            "solution_at": now,
            "completed_at": now,
            "created_at": now,
            "updated_at": now,
        }
        if mileage:
            report["mileage"] = mileage
        if handler_id:
            report["handler_id"] = handler_id
        return client.table("reports").insert(report).execute()

    @classmethod
    def get_bus_vendors(cls):
        """獲取所有公車與客運的對應清單"""
        client = cls.get_client()
        try:
            res = client.table('monitored_bus').select('plate_number, vendor_name').execute()
            return res.data
        except Exception as e:
            print(f"DB Error get_bus_vendors: {e}")
            return []

    @classmethod
    def get_reports_for_export(cls, start_date: str, end_date: str, export_type: str):
        """
        獲取導出用的數據
        """
        client = cls.get_client()
        try:
            query = client.table('reports').select('*').eq('status', '已完成')
            query = query.gte('completed_at', f"{start_date}T00:00:00")
            query = query.lte('completed_at', f"{end_date}T23:59:59")
            
            if export_type == 'replacement':
                query = query.eq('solution_type', '更換')
            
            res = query.order('completed_at', desc=False).execute()
            reports = res.data
            
            # 關聯客運公司 (使用 monitored_bus 表)
            vendors = cls.get_bus_vendors()
            for r in reports:
                r['vendor_name'] = '未知客運'
                car = (r.get('car_number', '') or '').strip()
                for v in vendors:
                    plate = (v.get('plate_number', '') or '').strip()
                    if plate and plate == car: # 改用精確匹配或包含匹配
                        r['vendor_name'] = v.get('vendor_name', '未知客運')
                        break
            
            return reports
        except Exception as e:
            print(f"DB Error get_reports_for_export: {e}")
            return []

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
