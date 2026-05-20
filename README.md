# 公車駕駛品情通報系統 (Line Bot 版)

本系統提供公車駕駛透過 Line 快速通報車輛問題，由 AI 自動解析格式並同步至管理後台。

## 快速開始

1. 複製 `.env.example` 為 `.env` 並填入金鑰設定。
2. 執行資料庫結構初始化（參考 `schema.sql` 系列檔案）。
3. 本地執行：
   ```bash
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

*注意：請務必妥善保管私密金鑰，切勿將 `.env` 提交至公開倉庫。*
