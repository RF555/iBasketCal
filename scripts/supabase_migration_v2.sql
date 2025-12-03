-- ============================================================================
-- Supabase Migration v2: Enable Row Level Security (RLS)
-- ============================================================================
-- Run this script in the Supabase SQL Editor to fix RLS warnings
-- This enables RLS on all tables with:
--   - Public read access (SELECT) for anonymous users
--   - Full access (ALL) for service role (used by backend)
--
-- IMPORTANT: After running this migration, your backend MUST use the
-- service_role key (not anon key) for write operations. Find it in:
-- Supabase Dashboard → Settings → API → service_role key
--
-- Set SUPABASE_KEY=your-service-role-key in your environment
-- ============================================================================

-- ============================================================================
-- METADATA TABLE
-- ============================================================================
ALTER TABLE metadata ENABLE ROW LEVEL SECURITY;

-- Allow public read access
CREATE POLICY "Public read access" ON metadata
    FOR SELECT
    USING (true);

-- Allow service role full access (for backend operations)
CREATE POLICY "Service role full access" ON metadata
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- SEASONS TABLE
-- ============================================================================
ALTER TABLE seasons ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON seasons
    FOR SELECT
    USING (true);

CREATE POLICY "Service role full access" ON seasons
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- COMPETITIONS TABLE
-- ============================================================================
ALTER TABLE competitions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON competitions
    FOR SELECT
    USING (true);

CREATE POLICY "Service role full access" ON competitions
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- GROUPS TABLE
-- ============================================================================
ALTER TABLE groups ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON groups
    FOR SELECT
    USING (true);

CREATE POLICY "Service role full access" ON groups
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- MATCHES TABLE
-- ============================================================================
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON matches
    FOR SELECT
    USING (true);

CREATE POLICY "Service role full access" ON matches
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- TEAMS TABLE
-- ============================================================================
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON teams
    FOR SELECT
    USING (true);

CREATE POLICY "Service role full access" ON teams
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- STANDINGS TABLE
-- ============================================================================
ALTER TABLE standings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON standings
    FOR SELECT
    USING (true);

CREATE POLICY "Service role full access" ON standings
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================
UPDATE metadata SET value = '2', updated_at = NOW() WHERE key = 'schema_version';
