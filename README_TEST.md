# BusAppeal Local Matching Test

這個測試程式旨在模擬 `BusAppeal` 系統中的 GPS 紀錄與時刻表比對邏輯，專門針對車號 `EAA-778` 進行分析。

## 功能
- 載入本地 `gps_log.json` 與 `route_chedules.json`。
- 自動過濾 `EAA-778` 的資料。
- 按日期分組，並模擬 `bus_service.py` 中的時間轉換（UTC -> UTC+8）與排序邏輯。
- 呼叫 `AIService` 進行模型分析，並輸出完整的 JSON 結果。

## 使用方法

### 1. 設定環境變數
在 `BusAppeal/` 目錄下建立 `.env` 檔案，並填入您的 `GEMINI_API_KEY`：
```env
GEMINI_API_KEY=your_actual_api_key_here
```

### 2. 安裝依賴 (建議使用虛擬環境)
```bash
# 在專案根目錄執行
python3 -m venv venv
source venv/bin/activate
pip install -r BusAppeal/requirements.txt
```

### 3. 執行測試
```bash
cd BusAppeal
python local_test_matching.py
```

## 觀察重點
- **Routes identified**: 確認程式是否正確識別出該車輛當天行駛的路線。
- **Schedules found**: 確認是否有對應的時刻表資料被載入。
- **AI Analysis Result**: 觀察 AI 的分析方案，檢查是否有遺漏行程或誤判休息時間的情況。
- **Total Mileage**: 確認里程計算是否符合預期。

## 檔案說明
- `local_test_matching.py`: 核心測試腳本。
- `gps_log.json`: 測試用的 GPS 原始資料。
- `route_chedules.json`: 測試用的時刻表資料。
