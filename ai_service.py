import google.generativeai as genai
from config import Config
import json

class AIService:
    def __init__(self):
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')

    async def analyze_report(self, description: str):
        prompt = f"""
你是一個公車維修系統的後端助理。請將駕駛通報的資訊整理成固定格式。
原始描述：「{description}」

請以 JSON 格式回傳，包含以下欄位：
- summary: 簡短的問題摘要（繁體中文）
- missing_info: 如果資訊不足（例如沒有提到是哪裡壞掉、壞掉的情境），請提出一個簡短的問題請駕駛補充；如果資訊充足，此欄位留空。
- suggestion: 給管理者的維修初步建議（選擇性）。

回應範例：
{{
  "summary": "前門氣壓缸異常",
  "missing_info": "請問是開門還是關門時有異音？",
  "suggestion": "建議檢查電磁閥及氣壓管路"
}}

請只回傳 JSON 字串，不要有其他解釋文字。
"""
        try:
            response = self.model.generate_content(prompt)
            # Try to parse JSON
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            print(f"AI Service Error: {e}")
            return {
                "summary": description[:50],
                "missing_info": "",
                "suggestion": "AI 處理失敗，請人工檢查"
            }
