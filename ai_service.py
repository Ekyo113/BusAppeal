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
        # 2.0 額度可能受限，改用最穩定的 gemini-flash-latest
        self.model = genai.GenerativeModel('gemini-flash-latest')
        
        try:
            # 異步環境下同步呼叫 list_models 僅用於啟動時診斷
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    print(f"AI Service Diagnostic: Found supported model: {m.name}")
        except Exception as e:
            print(f"AI Service Diagnostic: Could not list models: {e}")

    async def parse_group_message(self, text: str):
        """
        解析管理群發送的處理結果訊息。
        支援多筆、多種非標準書寫格式。
        回傳 list of dict: [{car_number, mileage(純數字字串), solution, solution_type}, ...]
        """
        prompt = f"""你是公車維修系統的資料擷取助理。你的任務是從管理群的自由格式訊息中，盡力擷取所有車輛維修處理結果。

訊息內容：
「{text}」

【書寫格式非常多元，以下是常見範例，但不限於此】
- 標準：EEE-111, 12345km, 更換大燈
- 括號里程：EEE-111(12345km)更換大燈
- 無分隔：EEE111 12345公里 更換大燈
- 僅數字車號：111(12345km)更換大燈
- 多筆換行：EEE-111 12345 更換大燈\nFFF-222 56000 換輪胎
- 多筆分號：EEE-111,123km,更換大燈；FFF-222,56000km,換輪胎
- 缺少里程：EEE-111 更換大燈
- 中文里程：EEE-111 一萬兩千公里 更換大燈
- 萬為單位：EEE-111 1.2萬 更換大燈（轉為12000）

【解析規則】
1. 車號：可能是 AAA-111、AAA111、111 等格式，盡力擷取。
2. 里程：轉為純整數字串（去除km/公里/萬等單位，1.2萬=12000），若無里程填空字串 ""。
3. 處理方案 (solution)：請簡化為「動作 + 零件」格式（例如：更換左後尾燈）。
   - 請統一相似零件名稱，例如：「左後燈」、「後尾燈」統一改為「左後尾燈」；「方向蜂鳴器」維持原樣。
   - 去除多餘敘述，如「完成」、「(翻修件)」、「功能測試ok」、「...」等。
4. solution_type：含「換」「替換」「更換」填「更換」；含「修」「調整」「校正」「清潔」填「維修」；其他填「維修」。
5. 若某筆資料欄位不完整，仍要回傳，缺少的欄位填空字串。
6. 無論格式多特殊，都要盡力解析，不要放棄。

只回傳 JSON 陣列，不要任何說明文字：
[
  {{"car_number": "車號", "mileage": "純數字里程", "solution": "處理方案", "solution_type": "更換或維修"}}
]"""
        try:
            print(f"AI GroupMsg: Parsing text: {text!r}")
            response = self.model.generate_content(prompt)
            raw = response.text
            print(f"AI GroupMsg: Raw response: {raw!r}")

            # 清理 markdown code block
            cleaned = re.sub(r'```(?:json)?', '', raw).replace('```', '').strip()

            # 若仍無法直接 parse，嘗試用 regex 抓出 JSON 陣列區塊
            try:
                result = json.loads(cleaned)
            except json.JSONDecodeError:
                match = re.search(r'\[.*\]', cleaned, re.DOTALL)
                if match:
                    result = json.loads(match.group())
                else:
                    print(f"AI GroupMsg: Cannot extract JSON from: {cleaned!r}")
                    return []

            # 確保回傳 list
            if isinstance(result, dict):
                result = [result]

            # 里程二次清理：處理萬為單位，再移除所有非數字
            for item in result:
                # 車號：若純數字則補 "EAL-" 前綴
                car = str(item.get('car_number', '')).strip()
                if car and re.fullmatch(r'\d+', car):
                    item['car_number'] = f'EAL-{car}'

                m = str(item.get('mileage', ''))
                # 處理「1.2萬」→12000
                wan = re.search(r'(\d+\.?\d*)\s*萬', m)
                if wan:
                    m = str(int(float(wan.group(1)) * 10000))
                else:
                    m = re.sub(r'[^\d]', '', m)
                item['mileage'] = m
                # 確保 solution_type 有值
                if not item.get('solution_type'):
                    item['solution_type'] = '維修'

            # 過濾掉車號和處理方案都為空的無效項目
            result = [r for r in result if r.get('car_number') or r.get('solution')]
            print(f"AI GroupMsg: Parsed {len(result)} items: {result}")
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
