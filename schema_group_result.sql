-- ──────────────────────────────────────────────────────────────────
-- 管理群自動填入功能 — reports 表欄位異動
-- 請在 Supabase SQL Editor 執行以下語法
-- ──────────────────────────────────────────────────────────────────

-- 1. 新增處理人員欄位
ALTER TABLE reports
  ADD COLUMN IF NOT EXISTS handler_id   TEXT,                        -- 處理人員 LINE User ID
  ADD COLUMN IF NOT EXISTS handler_name TEXT DEFAULT '市場組';       -- 處理人員顯示名稱

-- 2. 新增方案類型欄位（更換 / 維修）
ALTER TABLE reports
  ADD COLUMN IF NOT EXISTS solution_type TEXT;                       -- 由 AI 自動分類

-- ──────────────────────────────────────────────────────────────────
-- 驗證欄位是否已正確新增
-- ──────────────────────────────────────────────────────────────────
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'reports'
  AND column_name IN ('handler_id', 'handler_name', 'solution_type');
