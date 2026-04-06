-- 1. Create the vendor_mappings table
-- This table stores the mapping between precise car numbers and their respective vendor Line Group IDs.
-- The 'pattern' column is UNIQUE to ensure one car number has at most one direct mapping.
CREATE TABLE IF NOT EXISTS vendor_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern TEXT UNIQUE NOT NULL, -- The EXACT car number string (e.g., "AAA-111")
    group_id TEXT NOT NULL,       -- The target LINE Group ID or User ID for this vendor
    vendor_name TEXT,             -- Human-readable vendor name for easier management
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Add sample data (Optional/Example)
-- Replace the values below with your real car numbers and Group IDs.
-- INSERT INTO vendor_mappings (pattern, group_id, vendor_name) 
-- VALUES ('AAA-111', 'INSERT_REAL_GROUP_ID_FOR_VENDOR_1', 'Vendor 1');
