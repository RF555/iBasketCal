-- =====================================================
-- SportsPress Player Tables Migration for Supabase
-- Run this in the Supabase SQL Editor to add player support
--
-- NOTE: This uses minimal data storage - stats are fetched on-demand
-- =====================================================

-- Drop old table if exists (to update schema)
DROP TABLE IF EXISTS sp_players;

-- SportsPress Players Table (minimal data - stats fetched on-demand)
CREATE TABLE IF NOT EXISTS sp_players (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    team_ids TEXT,          -- JSON array of current team IDs
    league_ids TEXT,        -- JSON array
    season_ids TEXT,        -- JSON array
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- SportsPress Leagues Table (ID to name mapping)
CREATE TABLE IF NOT EXISTS sp_leagues (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT,
    data JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- SportsPress Teams Table (ID to name mapping)
CREATE TABLE IF NOT EXISTS sp_teams (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT,
    data JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- SportsPress Seasons Table (ID to name mapping)
CREATE TABLE IF NOT EXISTS sp_seasons (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT,
    data JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_sp_players_name ON sp_players(name);
CREATE INDEX IF NOT EXISTS idx_sp_leagues_name ON sp_leagues(name);
CREATE INDEX IF NOT EXISTS idx_sp_teams_name ON sp_teams(name);
CREATE INDEX IF NOT EXISTS idx_sp_seasons_name ON sp_seasons(name);

-- Enable RLS (Row Level Security) - allow public read/write for now
ALTER TABLE sp_players ENABLE ROW LEVEL SECURITY;
ALTER TABLE sp_leagues ENABLE ROW LEVEL SECURITY;
ALTER TABLE sp_teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE sp_seasons ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any
DROP POLICY IF EXISTS "Allow public read access to sp_players" ON sp_players;
DROP POLICY IF EXISTS "Allow public insert access to sp_players" ON sp_players;
DROP POLICY IF EXISTS "Allow public update access to sp_players" ON sp_players;
DROP POLICY IF EXISTS "Allow public read access to sp_leagues" ON sp_leagues;
DROP POLICY IF EXISTS "Allow public insert access to sp_leagues" ON sp_leagues;
DROP POLICY IF EXISTS "Allow public update access to sp_leagues" ON sp_leagues;
DROP POLICY IF EXISTS "Allow public read access to sp_teams" ON sp_teams;
DROP POLICY IF EXISTS "Allow public insert access to sp_teams" ON sp_teams;
DROP POLICY IF EXISTS "Allow public update access to sp_teams" ON sp_teams;
DROP POLICY IF EXISTS "Allow public read access to sp_seasons" ON sp_seasons;
DROP POLICY IF EXISTS "Allow public insert access to sp_seasons" ON sp_seasons;
DROP POLICY IF EXISTS "Allow public update access to sp_seasons" ON sp_seasons;

-- Create policies for public access
CREATE POLICY "Allow public read access to sp_players"
    ON sp_players FOR SELECT TO anon USING (true);

CREATE POLICY "Allow public insert access to sp_players"
    ON sp_players FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "Allow public update access to sp_players"
    ON sp_players FOR UPDATE TO anon USING (true) WITH CHECK (true);

CREATE POLICY "Allow public read access to sp_leagues"
    ON sp_leagues FOR SELECT TO anon USING (true);

CREATE POLICY "Allow public insert access to sp_leagues"
    ON sp_leagues FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "Allow public update access to sp_leagues"
    ON sp_leagues FOR UPDATE TO anon USING (true) WITH CHECK (true);

CREATE POLICY "Allow public read access to sp_teams"
    ON sp_teams FOR SELECT TO anon USING (true);

CREATE POLICY "Allow public insert access to sp_teams"
    ON sp_teams FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "Allow public update access to sp_teams"
    ON sp_teams FOR UPDATE TO anon USING (true) WITH CHECK (true);

CREATE POLICY "Allow public read access to sp_seasons"
    ON sp_seasons FOR SELECT TO anon USING (true);

CREATE POLICY "Allow public insert access to sp_seasons"
    ON sp_seasons FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "Allow public update access to sp_seasons"
    ON sp_seasons FOR UPDATE TO anon USING (true) WITH CHECK (true);

-- Success message
SELECT 'SportsPress player tables created successfully!' as message;
