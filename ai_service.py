import google.generativeai as genai
from config import Config
import json
import re

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

    async def parse_group_message(self, text: str):
        """
        解析管理群發送的處理結果訊息。
        支援多筆、多種書寫格式。
        回傳 list of dict: [{car_number, mileage(純數字字串), solution, solution_type}, ...]
        """
        prompt = f"""
你是公車維修系統的解析助理。請從以下管理群訊息中，擷取所有車輛處理結果。

訊息內容：
「{text}」

請依照以下規則解析：
1. 一則訊息可能包含多筆車輛資料，請全部擷取。
2. 里程：統一轉為純整數數字字串（例如「123km」、「12345公里」、「1.2萬公里」都轉為純數字），若無里程填空字串。
3. solution_type：根據處理方案內容判斷，若包含「更換」、「換」、「替換」等字則填「更換」；若包含「修」、「調整」、「校正」、「清潔」等字則填「維修」；若無法判斷填「維修」。
4. 若某欄位無法擷取，請填空字串。

請回傳 JSON 陣列（只回傳 JSON，不要其他文字）：
[
  {{"car_number": "車號", "mileage": "純數字里程", "solution": "處理方案", "solution_type": "更換或維修"}}
]
"""
        try:
            print(f"AI GroupMsg: Parsing: {text}")
            response = self.model.generate_content(prompt)
            raw = response.text.replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)
            # 確保回傳 list
            if isinstance(result, dict):
                result = [result]
            # 里程二次清理：移除所有非數字字元
            for item in result:
                m = re.sub(r'[^\d]', '', str(item.get('mileage', '')))
                item['mileage'] = m
            print(f"AI GroupMsg: Parsed {len(result)} items.")
            return result
        except Exception as e:
            print(f"AI GroupMsg Error: {type(e).__name__}: {e}")
            return []

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
