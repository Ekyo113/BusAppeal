-- ──────────────────────────────────────────────────────────────────
-- 部件選項功能 — reports 表欄位增設
-- 請在 Supabase SQL Editor 執行以下語法
-- ──────────────────────────────────────────────────────────────────

-- 1. 新增部件選項欄位
ALTER TABLE reports
  ADD COLUMN IF NOT EXISTS component TEXT;                       -- 部件選項欄位，可編輯

-- 2. 驗證欄位是否已正確新增
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'reports'
  AND column_name = 'component';
