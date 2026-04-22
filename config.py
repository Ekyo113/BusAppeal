import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LINE settings
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_NOTIFY_ID = os.getenv("LINE_NOTIFY_ID", os.getenv("LINE_ADMIN_GROUP_ID"))
    LINE_RECEIVE_ID = os.getenv("LINE_RECEIVE_ID", "")
    
    # Gemini settings
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Supabase settings
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    
    # TDX API settings
    TDX_CLIENT_ID = os.getenv("TDX_CLIENT_ID")
    TDX_CLIENT_SECRET = os.getenv("TDX_CLIENT_SECRET")
    
    # Admin settings
    ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "default_secret_key")
    
    @classmethod
    def validate(cls):
        required = [
            "LINE_CHANNEL_SECRET", 
            "LINE_CHANNEL_ACCESS_TOKEN", 
            "LINE_NOTIFY_ID",
            "SUPABASE_URL",
            "SUPABASE_SERVICE_KEY"
        ]
        missing = [f for f in required if not getattr(cls, f)]
        if missing:
            print(f"Warning: Missing environment variables: {', '.join(missing)}")
            return False
        return True
