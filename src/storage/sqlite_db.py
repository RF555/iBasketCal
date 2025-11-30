"""
SQLite Database Storage for Israeli Basketball Calendar.

Provides efficient storage and retrieval of basketball data with:
- Indexed queries for fast filtering
- Atomic transactions for data safety
- Incremental updates (no full rewrites)
- Concurrent read access via WAL mode

This is the SQLite implementation of the DatabaseInterface.
"""

import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Iterator, List, Dict, Any
import threading

from .base import DatabaseInterface
from .. import config


class SQLiteDatabase(DatabaseInterface):
    """
    SQLite database for basketball data storage.
    Thread-safe with connection per thread.

    Implements the DatabaseInterface abstract base class.
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str = "cache/basketball.db"):
        """
        Create SQLite database instance.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self._local = threading.local()
        self._initialized = False

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def initialize(self) -> None:
        """Initialize the database connection and schema."""
        if self._initialized:
            return

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema
        self._init_schema()
        self._initialized = True

    def close(self) -> None:
        """Close database connections and clean up resources."""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def health_check(self) -> bool:
        """Check if the database connection is healthy."""
        try:
            conn = self._get_connection()
            conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent access
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        return self._local.conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self.transaction() as conn:
            conn.executescript('''
                -- Metadata table
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Seasons
                CREATE TABLE IF NOT EXISTS seasons (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    data JSON NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Competitions
                CREATE TABLE IF NOT EXISTS competitions (
                    id TEXT PRIMARY KEY,
                    season_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    data JSON NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (season_id) REFERENCES seasons(id)
                );

                -- Groups (competition divisions)
                CREATE TABLE IF NOT EXISTS groups (
                    id TEXT PRIMARY KEY,
                    competition_id TEXT NOT NULL,
                    season_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    type TEXT,
                    data JSON NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Matches (main data table)
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
                    data JSON NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Teams
                CREATE TABLE IF NOT EXISTS teams (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    logo TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Standings
                CREATE TABLE IF NOT EXISTS standings (
                    group_id TEXT NOT NULL,
                    team_id TEXT NOT NULL,
                    position INTEGER,
                    data JSON NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (group_id, team_id)
                );

                -- Indexes for fast queries
                CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season_id);
                CREATE INDEX IF NOT EXISTS idx_matches_competition ON matches(competition_name);
                CREATE INDEX IF NOT EXISTS idx_matches_group ON matches(group_id);
                CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
                CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
                CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_name);
                CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_name);
                CREATE INDEX IF NOT EXISTS idx_groups_season ON groups(season_id);
                CREATE INDEX IF NOT EXISTS idx_competitions_season ON competitions(season_id);

                -- SportsPress Players (minimal data - stats fetched on-demand)
                CREATE TABLE IF NOT EXISTS sp_players (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    team_ids TEXT,          -- JSON array of current team IDs
                    league_ids TEXT,        -- JSON array
                    season_ids TEXT,        -- JSON array
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- SportsPress Leagues (for ID to name mapping)
                CREATE TABLE IF NOT EXISTS sp_leagues (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT,
                    data JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- SportsPress Teams (for ID to name mapping)
                CREATE TABLE IF NOT EXISTS sp_teams (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT,
                    data JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- SportsPress Seasons (for ID to name mapping)
                CREATE TABLE IF NOT EXISTS sp_seasons (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT,
                    data JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Player indexes
                CREATE INDEX IF NOT EXISTS idx_sp_players_name ON sp_players(name);
            ''')

            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ('schema_version', str(self.SCHEMA_VERSION))
            )

    # =========================================================================
    # WRITE OPERATIONS
    # =========================================================================

    def save_seasons(self, seasons: List[Dict[str, Any]]) -> int:
        """Save seasons to database. Returns count saved."""
        with self.transaction() as conn:
            conn.executemany('''
                INSERT OR REPLACE INTO seasons (id, name, start_date, end_date, data)
                VALUES (?, ?, ?, ?, ?)
            ''', [
                (
                    s.get('_id') or s.get('id'),
                    s.get('name', ''),
                    s.get('startDate'),
                    s.get('endDate'),
                    json.dumps(s, ensure_ascii=False)
                )
                for s in seasons
            ])
        return len(seasons)

    def save_competitions(self, season_id: str, competitions: List[Dict[str, Any]]) -> int:
        """Save competitions and their groups for a season."""
        with self.transaction() as conn:
            for comp in competitions:
                comp_id = comp.get('id') or f"{season_id}_{comp.get('name', 'unknown')}"

                conn.execute('''
                    INSERT OR REPLACE INTO competitions (id, season_id, name, data)
                    VALUES (?, ?, ?, ?)
                ''', (
                    comp_id,
                    season_id,
                    comp.get('name', ''),
                    json.dumps(comp, ensure_ascii=False)
                ))

                for group in comp.get('groups', []):
                    conn.execute('''
                        INSERT OR REPLACE INTO groups
                        (id, competition_id, season_id, name, type, data)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        group.get('id'),
                        comp_id,
                        season_id,
                        group.get('name', ''),
                        group.get('type'),
                        json.dumps(group, ensure_ascii=False)
                    ))

        return len(competitions)

    def save_matches(
        self,
        group_id: str,
        calendar_data: Dict[str, Any],
        competition_name: str = '',
        group_name: str = '',
        season_id: str = ''
    ) -> int:
        """Save matches from calendar data. Returns count saved."""
        matches = []
        teams = {}

        for round_data in calendar_data.get('rounds', []):
            for match in round_data.get('matches', []):
                match_id = match.get('id')
                if not match_id:
                    continue

                home_team = match.get('homeTeam') or {}
                away_team = match.get('awayTeam') or {}
                court = match.get('court') or {}
                score = match.get('score') or {}
                totals = score.get('totals') or []

                # Extract scores
                home_score = None
                away_score = None
                for t in totals:
                    if t.get('teamId') == home_team.get('id'):
                        home_score = t.get('total')
                    elif t.get('teamId') == away_team.get('id'):
                        away_score = t.get('total')

                # Collect teams
                if home_team.get('id'):
                    teams[home_team['id']] = {
                        'id': home_team['id'],
                        'name': home_team.get('name', ''),
                        'logo': home_team.get('logo')
                    }
                if away_team.get('id'):
                    teams[away_team['id']] = {
                        'id': away_team['id'],
                        'name': away_team.get('name', ''),
                        'logo': away_team.get('logo')
                    }

                # Enrich match with metadata
                enriched_match = {
                    **match,
                    '_competition': competition_name,
                    '_group': group_name,
                    '_group_id': group_id,
                    '_season_id': season_id
                }

                matches.append((
                    match_id,
                    season_id,
                    None,
                    competition_name,
                    group_id,
                    group_name,
                    home_team.get('id'),
                    home_team.get('name'),
                    away_team.get('id'),
                    away_team.get('name'),
                    match.get('date'),
                    match.get('status'),
                    home_score,
                    away_score,
                    court.get('place'),
                    court.get('address'),
                    json.dumps(enriched_match, ensure_ascii=False)
                ))

        with self.transaction() as conn:
            conn.executemany('''
                INSERT OR REPLACE INTO matches
                (id, season_id, competition_id, competition_name, group_id, group_name,
                 home_team_id, home_team_name, away_team_id, away_team_name,
                 date, status, home_score, away_score, venue, venue_address, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', matches)

            conn.executemany('''
                INSERT OR REPLACE INTO teams (id, name, logo)
                VALUES (?, ?, ?)
            ''', [(t['id'], t['name'], t.get('logo')) for t in teams.values()])

        return len(matches)

    def save_standings(self, group_id: str, standings: List[Dict[str, Any]]) -> int:
        """Save standings for a group."""
        with self.transaction() as conn:
            conn.executemany('''
                INSERT OR REPLACE INTO standings (group_id, team_id, position, data)
                VALUES (?, ?, ?, ?)
            ''', [
                (
                    group_id,
                    s.get('teamId'),
                    s.get('position'),
                    json.dumps(s, ensure_ascii=False)
                )
                for s in standings if s.get('teamId')
            ])
        return len(standings)

    def update_scrape_timestamp(self) -> None:
        """Update the last scrape timestamp."""
        with self.transaction() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO metadata (key, value, updated_at)
                VALUES ('last_scrape', ?, CURRENT_TIMESTAMP)
            ''', (datetime.now(timezone.utc).isoformat(),))

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    def get_seasons(self) -> List[Dict[str, Any]]:
        """Get all seasons, ordered by name descending."""
        conn = self._get_connection()
        rows = conn.execute(
            'SELECT data FROM seasons ORDER BY name DESC'
        ).fetchall()
        return [json.loads(row['data']) for row in rows]

    def get_competitions(self, season_id: str) -> List[Dict[str, Any]]:
        """Get competitions for a season."""
        conn = self._get_connection()
        rows = conn.execute(
            'SELECT data FROM competitions WHERE season_id = ? ORDER BY name',
            (season_id,)
        ).fetchall()
        return [json.loads(row['data']) for row in rows]

    def get_all_competitions(self) -> List[Dict[str, Any]]:
        """Get all competitions across all seasons."""
        conn = self._get_connection()
        rows = conn.execute('''
            SELECT data, season_id FROM competitions ORDER BY name
        ''').fetchall()

        result = []
        for row in rows:
            comp = json.loads(row['data'])
            comp['_season_id'] = row['season_id']
            result.append(comp)
        return result

    def get_matches(
        self,
        season_id: Optional[str] = None,
        competition_name: Optional[str] = None,
        team_name: Optional[str] = None,
        group_id: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get matches with flexible filtering."""
        query = "SELECT data FROM matches WHERE 1=1"
        params: List[Any] = []

        if season_id:
            query += " AND season_id = ?"
            params.append(season_id)

        if competition_name:
            query += " AND competition_name LIKE ?"
            params.append(f"%{competition_name}%")

        if team_name:
            query += " AND (home_team_name LIKE ? OR away_team_name LIKE ?)"
            params.extend([f"%{team_name}%", f"%{team_name}%"])

        if group_id:
            query += " AND group_id = ?"
            params.append(group_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        if date_from:
            query += " AND date >= ?"
            params.append(date_from)

        if date_to:
            query += " AND date <= ?"
            params.append(date_to)

        query += " ORDER BY date ASC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        conn = self._get_connection()
        rows = conn.execute(query, params).fetchall()
        return [json.loads(row['data']) for row in rows]

    def get_teams(self, season_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all teams, optionally filtered by season."""
        conn = self._get_connection()

        if season_id:
            rows = conn.execute('''
                SELECT DISTINCT t.id, t.name, t.logo
                FROM teams t
                JOIN matches m ON (t.id = m.home_team_id OR t.id = m.away_team_id)
                WHERE m.season_id = ?
                ORDER BY t.name
            ''', (season_id,)).fetchall()
        else:
            rows = conn.execute(
                'SELECT id, name, logo FROM teams ORDER BY name'
            ).fetchall()

        return [{'id': r['id'], 'name': r['name'], 'logo': r['logo']} for r in rows]

    def search_teams(self, query: str, season_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search teams by name."""
        conn = self._get_connection()

        if season_id:
            rows = conn.execute('''
                SELECT DISTINCT t.id, t.name, t.logo
                FROM teams t
                JOIN matches m ON (t.id = m.home_team_id OR t.id = m.away_team_id)
                WHERE m.season_id = ? AND t.name LIKE ?
                ORDER BY t.name
            ''', (season_id, f"%{query}%")).fetchall()
        else:
            rows = conn.execute(
                'SELECT id, name, logo FROM teams WHERE name LIKE ? ORDER BY name',
                (f"%{query}%",)
            ).fetchall()

        return [{'id': r['id'], 'name': r['name'], 'logo': r['logo']} for r in rows]

    def get_standings(self, group_id: str) -> List[Dict[str, Any]]:
        """Get standings for a group."""
        conn = self._get_connection()
        rows = conn.execute(
            'SELECT data FROM standings WHERE group_id = ? ORDER BY position',
            (group_id,)
        ).fetchall()
        return [json.loads(row['data']) for row in rows]

    # =========================================================================
    # CACHE INFO & MAINTENANCE
    # =========================================================================

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache status information."""
        conn = self._get_connection()

        row = conn.execute(
            "SELECT value, updated_at FROM metadata WHERE key = 'last_scrape'"
        ).fetchone()

        if not row:
            return {
                'exists': False,
                'stale': True,
                'last_updated': None,
                'age_minutes': None,
                'stats': {}
            }

        last_updated = datetime.fromisoformat(row['value'].replace('Z', '+00:00'))
        age = datetime.now(timezone.utc) - last_updated
        age_minutes = int(age.total_seconds() / 60)

        # Get stats
        stats = {}
        for table in ['seasons', 'competitions', 'groups', 'matches', 'teams']:
            count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            stats[table] = count

        return {
            'exists': True,
            'stale': age_minutes > config.CACHE_TTL_MINUTES,
            'last_updated': row['value'],
            'age_minutes': age_minutes,
            'stats': stats
        }

    def get_database_size(self) -> int:
        """Get database file size in bytes."""
        if self.db_path.exists():
            return self.db_path.stat().st_size
        return 0

    def clear_all(self) -> None:
        """Clear all data from database."""
        with self.transaction() as conn:
            for table in ['standings', 'matches', 'teams', 'groups', 'competitions', 'seasons']:
                conn.execute(f'DELETE FROM {table}')
            conn.execute("DELETE FROM metadata WHERE key = 'last_scrape'")

    def vacuum(self) -> None:
        """Reclaim unused space in database file."""
        conn = self._get_connection()
        conn.execute('VACUUM')

    # =========================================================================
    # SPORTSPRESS PLAYER DATA
    # =========================================================================

    def save_players(self, players: List[Dict[str, Any]]) -> int:
        """
        Save players with minimal data (stats fetched on-demand).

        Expects minimal player dicts with: id, name, teams, leagues, seasons
        """
        with self.transaction() as conn:
            for player in players:
                player_id = player.get('id')
                if not player_id:
                    continue

                # Handle both full API response and minimal data format
                # Full API has 'title.rendered', minimal has 'name' directly
                if 'name' in player:
                    name = player['name']
                else:
                    title = player.get('title', {})
                    name = title.get('rendered', '') if isinstance(title, dict) else str(title)

                # Handle both 'teams' and 'current_teams' for flexibility
                teams = player.get('teams') or player.get('current_teams', [])

                conn.execute('''
                    INSERT OR REPLACE INTO sp_players
                    (id, name, team_ids, league_ids, season_ids)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    player_id,
                    name,
                    json.dumps(teams),
                    json.dumps(player.get('leagues', [])),
                    json.dumps(player.get('seasons', []))
                ))

        return len(players)

    def get_players(
        self,
        team_id: Optional[int] = None,
        league_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get players with optional filters (minimal data)."""
        query = "SELECT id, name, team_ids, league_ids, season_ids FROM sp_players WHERE 1=1"
        params: List[Any] = []

        if team_id:
            # Search in JSON array
            query += " AND team_ids LIKE ?"
            params.append(f'%{team_id}%')

        if league_id:
            query += " AND league_ids LIKE ?"
            params.append(f'%{league_id}%')

        query += " ORDER BY name"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        conn = self._get_connection()
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_player(row) for row in rows]

    def search_players(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search players by name (returns minimal data).

        Splits query into words and matches ALL words in any order.
        Example: "יוסי כהן" matches "יוסי כהן", "כהן יוסי", "יוסי דוד כהן"
        """
        conn = self._get_connection()

        # Split query into words and require all words to match
        words = query.strip().split()

        if not words:
            return []

        # Build WHERE clause - each word must appear somewhere in the name
        conditions = ' AND '.join(['name LIKE ?' for _ in words])
        params = [f'%{word}%' for word in words]
        params.append(limit)

        rows = conn.execute(
            f'SELECT id, name, team_ids, league_ids, season_ids FROM sp_players WHERE {conditions} ORDER BY name LIMIT ?',
            params
        ).fetchall()
        return [self._row_to_player(row) for row in rows]

    def get_player(self, player_id: int) -> Optional[Dict[str, Any]]:
        """Get a single player by ID (minimal data - no stats)."""
        conn = self._get_connection()
        row = conn.execute(
            'SELECT id, name, team_ids, league_ids, season_ids FROM sp_players WHERE id = ?',
            (player_id,)
        ).fetchone()
        return self._row_to_player(row) if row else None

    def _row_to_player(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to player dict."""
        return {
            'id': row['id'],
            'name': row['name'],
            'teams': json.loads(row['team_ids'] or '[]'),
            'leagues': json.loads(row['league_ids'] or '[]'),
            'seasons': json.loads(row['season_ids'] or '[]')
        }

    def save_sportspress_leagues(self, leagues: List[Dict[str, Any]]) -> int:
        """Save SportsPress leagues."""
        with self.transaction() as conn:
            conn.executemany('''
                INSERT OR REPLACE INTO sp_leagues (id, name, slug, data)
                VALUES (?, ?, ?, ?)
            ''', [
                (
                    lg.get('id'),
                    lg.get('name', ''),
                    lg.get('slug', ''),
                    json.dumps(lg, ensure_ascii=False)
                )
                for lg in leagues if lg.get('id')
            ])
        return len(leagues)

    def save_sportspress_teams(self, teams: List[Dict[str, Any]]) -> int:
        """Save SportsPress teams."""
        with self.transaction() as conn:
            conn.executemany('''
                INSERT OR REPLACE INTO sp_teams (id, name, slug, data)
                VALUES (?, ?, ?, ?)
            ''', [
                (
                    t.get('id'),
                    t.get('name', ''),
                    t.get('slug', ''),
                    json.dumps(t, ensure_ascii=False)
                )
                for t in teams if t.get('id')
            ])
        return len(teams)

    def save_sportspress_seasons(self, seasons: List[Dict[str, Any]]) -> int:
        """Save SportsPress seasons."""
        with self.transaction() as conn:
            conn.executemany('''
                INSERT OR REPLACE INTO sp_seasons (id, name, slug, data)
                VALUES (?, ?, ?, ?)
            ''', [
                (
                    s.get('id'),
                    s.get('name', ''),
                    s.get('slug', ''),
                    json.dumps(s, ensure_ascii=False)
                )
                for s in seasons if s.get('id')
            ])
        return len(seasons)

    def get_sportspress_leagues(self) -> List[Dict[str, Any]]:
        """Get all SportsPress leagues."""
        conn = self._get_connection()
        rows = conn.execute(
            'SELECT id, name, slug FROM sp_leagues ORDER BY name'
        ).fetchall()
        return [{'id': r['id'], 'name': r['name'], 'slug': r['slug']} for r in rows]

    def get_sportspress_teams(self) -> List[Dict[str, Any]]:
        """Get all SportsPress teams."""
        conn = self._get_connection()
        rows = conn.execute(
            'SELECT id, name, slug FROM sp_teams ORDER BY name'
        ).fetchall()
        return [{'id': r['id'], 'name': r['name'], 'slug': r['slug']} for r in rows]

    def get_sportspress_seasons(self) -> List[Dict[str, Any]]:
        """Get all SportsPress seasons."""
        conn = self._get_connection()
        rows = conn.execute(
            'SELECT id, name, slug FROM sp_seasons ORDER BY name DESC'
        ).fetchall()
        return [{'id': r['id'], 'name': r['name'], 'slug': r['slug']} for r in rows]
