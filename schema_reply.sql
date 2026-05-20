-- ──────────────────────────────────────────────────────────────────
-- 通報回覆欄位功能 — reports 表欄位異動
-- 請在 Supabase SQL Editor 執行以下語法
-- ──────────────────────────────────────────────────────────────────

-- 1. 新增通報回覆欄位
ALTER TABLE reports
  ADD COLUMN IF NOT EXISTS reply TEXT;                       -- 通報回覆欄位，可編輯，預設與處理方案相同

-- 2. 驗證欄位是否已正確新增
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'reports'
  AND column_name = 'reply';
