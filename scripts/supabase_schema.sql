-- ============================================================================
-- Supabase Schema for iBasketCal
-- ============================================================================
-- Run this script in the Supabase SQL Editor before using DB_TYPE=supabase
-- This creates all required tables and indexes for the basketball calendar app
-- ============================================================================

-- Metadata table (stores schema version, last scrape time, etc.)
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seasons table
CREATE TABLE IF NOT EXISTS seasons (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Competitions table
CREATE TABLE IF NOT EXISTS competitions (
    id TEXT PRIMARY KEY,
    season_id TEXT NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Groups table (competition divisions/groups)
CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    competition_id TEXT NOT NULL,
    season_id TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Matches table (main data table)
CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    season_id TEXT NOT NULL,
    competition_id TEXT,
    competition_name TEXT,
    group_id TEXT NOT NULL,
    group_name TEXT,
    home_team_id TEXT,
    home_team_name TEXT,
    away_team_id TEXT,
    away_team_name TEXT,
    date TEXT,
    status TEXT,
    home_score INTEGER,
    away_score INTEGER,
    venue TEXT,
    venue_address TEXT,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Teams table
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    logo TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Standings table
CREATE TABLE IF NOT EXISTS standings (
    group_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    position INTEGER,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (group_id, team_id)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Matches indexes (most important for query performance)
CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season_id);
CREATE INDEX IF NOT EXISTS idx_matches_competition ON matches(competition_name);
CREATE INDEX IF NOT EXISTS idx_matches_group ON matches(group_id);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_name);
CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_name);
CREATE INDEX IF NOT EXISTS idx_matches_home_team_id ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away_team_id ON matches(away_team_id);

-- Groups indexes
CREATE INDEX IF NOT EXISTS idx_groups_season ON groups(season_id);
CREATE INDEX IF NOT EXISTS idx_groups_competition ON groups(competition_id);

-- Competitions indexes
CREATE INDEX IF NOT EXISTS idx_competitions_season ON competitions(season_id);

-- Teams index
CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================
-- Enables public read access for all tables
-- Backend must use service_role key for write operations
-- Find service_role key in: Supabase Dashboard → Settings → API

-- Metadata table
ALTER TABLE metadata ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access" ON metadata FOR SELECT USING (true);
CREATE POLICY "Service role full access" ON metadata FOR ALL
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

-- Seasons table
ALTER TABLE seasons ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access" ON seasons FOR SELECT USING (true);
CREATE POLICY "Service role full access" ON seasons FOR ALL
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

-- Competitions table
ALTER TABLE competitions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access" ON competitions FOR SELECT USING (true);
CREATE POLICY "Service role full access" ON competitions FOR ALL
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

-- Groups table
ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access" ON groups FOR SELECT USING (true);
CREATE POLICY "Service role full access" ON groups FOR ALL
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

-- Matches table
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access" ON matches FOR SELECT USING (true);
CREATE POLICY "Service role full access" ON matches FOR ALL
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

-- Teams table
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access" ON teams FOR SELECT USING (true);
CREATE POLICY "Service role full access" ON teams FOR ALL
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

-- Standings table
ALTER TABLE standings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access" ON standings FOR SELECT USING (true);
CREATE POLICY "Service role full access" ON standings FOR ALL
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- INITIAL METADATA
-- ============================================================================

INSERT INTO metadata (key, value) VALUES ('schema_version', '1')
ON CONFLICT (key) DO UPDATE SET value = '1', updated_at = NOW();
