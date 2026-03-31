import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LINE settings
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_ADMIN_GROUP_ID = os.getenv("LINE_ADMIN_GROUP_ID") # Comma-separated IDs
    
    # Gemini settings
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Supabase settings
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    
    # Admin settings
    ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "default_secret_key")
    
    @classmethod
    def validate(cls):
        required = [
            "LINE_CHANNEL_SECRET", 
            "LINE_CHANNEL_ACCESS_TOKEN", 
            "LINE_ADMIN_GROUP_ID",
            "GEMINI_API_KEY",
            "SUPABASE_URL",
            "SUPABASE_SERVICE_KEY"
        ]
        missing = [f for f in required if not getattr(cls, f)]
        if missing:
            print(f"Warning: Missing environment variables: {', '.join(missing)}")
            return False
        return True
