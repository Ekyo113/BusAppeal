# 公車駕駛品情通報系統 (Line Bot 版)

透過 Line 官方帳號讓駕駛快速通報車輛問題，並由 AI 自動整理格式，簡化維修通報流程。

## 功能特點
- **駕駛端**：支援語音轉文字、圖片/影片傳送，溝通零障礙。
- **AI 整理**：自動提取車號、描述並提供維修建議。
- **管理後台**：進度追蹤、維修完成通知推播。
- **安全保障**：私有資料庫存儲，管理端受金鑰保護。

## 技術棧
- **後端**: FastAPI (Python 3.10+)
- **AI**: Google Gemini 1.5 Pro
- **資料庫**: Supabase
- **部署**: Render / Vercel

---

## 快速開始

### 1. 環境設定
請參考 `.env.example` 建立 `.env` 檔案並填入必要金鑰。
> [!IMPORTANT]
> **資訊安全提醒**：請勿將含有真實金鑰的 `.env` 檔案提交至 Git。

### 2. 資料庫初始化
請參考 `schema.sql` 中的指令在 Supabase SQL Editor 建立所需的資料表與儲存空間。

### 3. 本地開發
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

---

## 部署與 Webhook
1. 部署程式碼至雲端平台（如 Render）。
2. 在 **Line Developers Console** 設定 Webhook URL：`https://你的網址/webhook`
3. 設定環境變數後即可運作。
