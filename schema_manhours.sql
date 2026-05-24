-- ──────────────────────────────────────────────────────────────────
-- 工時統計功能 — reply_hours 表初始化
-- 請在 Supabase SQL Editor 執行以下語法以建立資料庫表
-- ──────────────────────────────────────────────────────────────────

-- 1. 建立工時表
CREATE TABLE IF NOT EXISTS reply_hours (
    reply_text TEXT PRIMARY KEY,                             -- 通報回覆項目名稱 (Unique)
    hours NUMERIC DEFAULT 0.5,                               -- 每項工作之預設工時 (預設為 0.5hr)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 驗證資料表是否已建立
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name = 'reply_hours';
