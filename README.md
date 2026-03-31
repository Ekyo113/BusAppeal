# 公車駕駛品情通報系統 (Line Bot 版)

透過 Line 官方帳號讓駕駛快速通報車輛問題，並由 AI 自動整理格式。管理員可透過後台管理進度，並在維修完成後自動通知駕駛。

## 功能特點
- **駕駛端**：直接在 Line 聊天，支援語音轉文字、傳送相片/影片。
- **AI 整理**：自動從對話中提取車號、問題描述，並給予維修建議。
- **管理端**：網頁版後台，一鍵標記維修完成並推播 Line 訊息給駕駛。
- **資安**：資料存於私有資料庫，後台受金鑰保護。

## 技術棧
- **Backend**: FastAPI (Python 3.10+)
- **AI**: Google Gemini 1.5 Pro
- **Database**: Supabase (PostgreSQL + Storage)
- **Deployment**: Render / Vercel

---

## 快速開始

### 1. Supabase 設定
請在 Supabase SQL Editor 執行以下指令建立資料表：

```sql
-- 通報記錄表
CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  car_number TEXT NOT NULL,
  description TEXT,
  ai_summary TEXT,
  status TEXT DEFAULT '待處理',
  driver_line_user_id TEXT,
  media_urls TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 對話狀態表
CREATE TABLE conversation_state (
  user_id TEXT PRIMARY KEY,
  step TEXT NOT NULL,
  temp_data JSONB DEFAULT '{}',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 建立儲存桶
-- 請在 Storage 介面建立一個名為 'bus-media' 的 Bucket，並設為 Public (或根據需求調整權限)
```

### 2. 環境變數 (.env)
請參考 `.env.example` 設定以下變數：
- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_ADMIN_GROUP_ID`: 接收新通報通知的群組 ID
- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `ADMIN_SECRET_KEY`: 設定後台管理登入用的密碼

### 3. 本地執行
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

---

## 部署說明
1. 將程式碼推送到 GitHub。
2. 在 **Render** 建立新的 Web Service，串接此 Repo。
3. 設定上述環境變數。
4. 在 **Line Developers Console** 將 Webhook URL 設為：`https://你的網址.onrender.com/webhook`
5. 掃描 Line 官方帳號 QR Code 即可開始測試。
