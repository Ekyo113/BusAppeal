-- Cache for TDX bus schedules
CREATE TABLE IF NOT EXISTS bus_route_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_code TEXT NOT NULL,
    route_name TEXT NOT NULL,
    direction INT, -- 0 or 1
    departure_time TEXT, -- HH:mm
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Analyzed operating plans
CREATE TABLE IF NOT EXISTS bus_operating_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plate_number TEXT NOT NULL,
    date DATE NOT NULL,
    plan_name TEXT NOT NULL, -- '營運方案一', '營運方案二', etc.
    route_summary TEXT,      -- e.g., "路線A -> 路線B -> 路線A"
    total_mileage DECIMAL(10,2), -- Estimated daily mileage in km
    route_details JSONB,     -- Detailed segments with times
    break_details JSONB,     -- Mid-day break (中退) times and locations
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(plate_number, date)
);

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_bus_plans_lookup ON bus_operating_plans (plate_number, date);
CREATE INDEX IF NOT EXISTS idx_bus_schedules_lookup ON bus_route_schedules (city_code, route_name);

-- 建立 reports 表索引以加速列表撈取
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports (status);

-- 建立 weekly_bus_gps_log 複合索引
CREATE INDEX IF NOT EXISTS idx_weekly_gps_log_plate_time ON weekly_bus_gps_log (plate_number, recorded_at);

-- 建立不重複車牌與日期的預存程序
DROP FUNCTION IF EXISTS get_unique_bus_gps_pairs();

CREATE OR REPLACE FUNCTION get_unique_bus_gps_pairs()
RETURNS TABLE(plate_number TEXT, recorded_date TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT weekly_bus_gps_log.plate_number, split_part(weekly_bus_gps_log.recorded_at, 'T', 1)
    FROM weekly_bus_gps_log;
END;
$$ LANGUAGE plpgsql
SECURITY INVOKER;

-- 限制執行權限以策安全 (防止匿名或一般登入帳戶透過 API 呼叫)
REVOKE EXECUTE ON FUNCTION get_unique_bus_gps_pairs() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION get_unique_bus_gps_pairs() FROM anon;
REVOKE EXECUTE ON FUNCTION get_unique_bus_gps_pairs() FROM authenticated;
GRANT EXECUTE ON FUNCTION get_unique_bus_gps_pairs() TO service_role;
GRANT EXECUTE ON FUNCTION get_unique_bus_gps_pairs() TO postgres;

