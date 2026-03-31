import google.generativeai as genai
from config import Config
import json

class AIService:
    def __init__(self):
        # Diagnostic print (masked for safety)
        key = Config.GEMINI_API_KEY
        if not key:
            print("AI Service Diagnostic: GEMINI_API_KEY is EMPTY or NOT FOUND!")
        else:
            print(f"AI Service Diagnostic: Key starts with {key[:5]}... and ends with ...{key[-5:]}")
        
        genai.configure(api_key=key)
        # Switching to gemini-1.5-flash for better performance and format support
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    async def analyze_report(self, description: str):
        prompt = f"""
你是一個公車維修系統的後端助理。請將駕駛通報的資訊整理成正確的 JSON 格式。
原始描述：「{description}」

請回傳 JSON 格式如下：
{{
  "car_number": "偵測到的車號（若未偵測到請留空）",
  "summary": "簡短摘要",
  "missing_info": "追問資訊（若資訊充足請留空）",
  "suggestion": "初步維修建議"
}}
"""
        try:
            print(f"AI Service: Analyzing description: {description}")
            response = self.model.generate_content(prompt)
            print("AI Service: Successfully got response from Gemini.")
            
            # Clean up the response text (sometimes Gemini adds ```json ... ```)
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            print(f"AI Service Error during generate_content: {type(e).__name__}: {e}")
            # If it's a real API key error, this print will help confirm
            return {
                "summary": description[:50],
                "missing_info": "",
                "suggestion": "AI 處理失敗，請人工檢查"
            }
