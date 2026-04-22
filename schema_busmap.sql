-- 建立城市資料表
CREATE TABLE IF NOT EXISTS cities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_code   TEXT UNIQUE NOT NULL,   -- TDX 城市名稱（例：Tainan）
    city_name   TEXT NOT NULL,          -- 中文名稱（例：台南市）
    center_lat  DECIMAL(9,6),           -- 地圖初始中心緯度
    center_lon  DECIMAL(9,6),           -- 地圖初始中心經度
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 插入台南市與高雄市預設資料
INSERT INTO cities (city_code, city_name, center_lat, center_lon) 
VALUES 
    ('Tainan', '台南市', 22.9999, 120.2269),
    ('Kaohsiung', '高雄市', 22.6273, 120.3014)
ON CONFLICT (city_code) DO NOTHING;

-- 建立受監控車輛資料表
CREATE TABLE IF NOT EXISTS monitored_buses (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_code    TEXT NOT NULL REFERENCES cities(city_code),
    plate_number TEXT NOT NULL,          -- 車牌號碼（例：KKA-0001）
    route_name   TEXT,                   -- 預設路線（顯示用）
    vendor_name  TEXT,                   -- 所屬廠商
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(city_code, plate_number)      -- 同城市內車牌唯一
);

-- 建立 GPS 靜止偵測歷史快照資料表
CREATE TABLE IF NOT EXISTS gps_history (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_code    TEXT NOT NULL,
    plate_number TEXT NOT NULL,
    lat          DECIMAL(9,6),
    lon          DECIMAL(9,6),
    stop_name    TEXT,
    stop_sequence INT,              -- 站序（1 = 起始站）
    is_terminal  BOOLEAN DEFAULT FALSE, -- 是否為起點/終點站
    recorded_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 建立索引加速查詢
CREATE INDEX IF NOT EXISTS idx_gps_history_lookup ON gps_history (city_code, plate_number, recorded_at DESC);
