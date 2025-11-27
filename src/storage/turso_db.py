"""
Turso Database Storage for Israeli Basketball Calendar.

Provides cloud-hosted SQLite-compatible storage using Turso's libSQL.
Key differences from local SQLite:
- Connection via URL + auth token
- No executemany() - use individual execute() calls
- No executescript() - execute statements individually
- Row access via index (row[0]) instead of dict key
- vacuum() is no-op (handled by Turso service)

Requires: pip install libsql-experimental
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .base import DatabaseInterface
from .exceptions import ConfigurationError, ConnectionError
from .. import config


class TursoDatabase(DatabaseInterface):
    """
    Turso cloud database implementation.

    Uses libSQL for SQLite-compatible cloud storage with edge replicas.
    Implements the DatabaseInterface abstract base class.
    """

    SCHEMA_VERSION = 1

    def __init__(self):
        """
        Create Turso database instance.

        Reads configuration from environment variables:
        - TURSO_DATABASE_URL: Database URL (e.g., libsql://your-db.turso.io)
        - TURSO_AUTH_TOKEN: Authentication token
        """
        self._url = os.environ.get('TURSO_DATABASE_URL')
        self._token = os.environ.get('TURSO_AUTH_TOKEN')
        self._conn = None
        self._initialized = False

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def initialize(self) -> None:
        """Initialize the database connection and schema."""
        if self._initialized:
            return

        if not self._url:
            raise ConfigurationError(
                "TURSO_DATABASE_URL environment variable is required for Turso backend"
            )
        if not self._token:
            raise ConfigurationError(
                "TURSO_AUTH_TOKEN environment variable is required for Turso backend"
            )

        # Initialize schema
        self._init_schema()
        self._initialized = True

    def _get_connection(self):
        """Get or create database connection."""
        if self._conn is None:
            try:
                import libsql_experimental as libsql
            except ImportError:
                raise ConfigurationError(
                    "libsql-experimental package not installed. "
                    "Install with: pip install libsql-experimental"
                )

            try:
                self._conn = libsql.connect(
                    self._url,
                    auth_token=self._token
                )
            except Exception as e:
                raise ConnectionError(f"Failed to connect to Turso: {e}")

        return self._conn

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def health_check(self) -> bool:
        """Check if the database connection is healthy."""
        try:
            conn = self._get_connection()
            conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def _init_schema(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()

        # Execute each statement individually (no executescript in libsql)
        statements = [
            # Metadata table
            '''CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )''',

            # Seasons
            '''CREATE TABLE IF NOT EXISTS seasons (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                data TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )''',

            # Competitions
            '''CREATE TABLE IF NOT EXISTS competitions (
                id TEXT PRIMARY KEY,
                season_id TEXT NOT NULL,
                name TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )''',

            # Groups
            '''CREATE TABLE IF NOT EXISTS groups (
                id TEXT PRIMARY KEY,
                competition_id TEXT NOT NULL,
                season_id TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT,
                data TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )''',

            # Matches
            '''CREATE TABLE IF NOT EXISTS matches (
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
                data TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )''',

            # Teams
            '''CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                logo TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )''',

            # Standings
            '''CREATE TABLE IF NOT EXISTS standings (
                group_id TEXT NOT NULL,
                team_id TEXT NOT NULL,
                position INTEGER,
                data TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (group_id, team_id)
            )''',

            # Indexes
            'CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season_id)',
            'CREATE INDEX IF NOT EXISTS idx_matches_competition ON matches(competition_name)',
            'CREATE INDEX IF NOT EXISTS idx_matches_group ON matches(group_id)',
            'CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date)',
            'CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status)',
            'CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_name)',
            'CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_name)',
            'CREATE INDEX IF NOT EXISTS idx_groups_season ON groups(season_id)',
            'CREATE INDEX IF NOT EXISTS idx_competitions_season ON competitions(season_id)',
        ]

        for stmt in statements:
            conn.execute(stmt)
        conn.commit()

        # Set schema version
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ('schema_version', str(self.SCHEMA_VERSION))
        )
        conn.commit()

    # =========================================================================
    # WRITE OPERATIONS
    # =========================================================================

    def save_seasons(self, seasons: List[Dict[str, Any]]) -> int:
        """Save seasons to database."""
        conn = self._get_connection()

        for s in seasons:
            conn.execute('''
                INSERT OR REPLACE INTO seasons (id, name, start_date, end_date, data)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                s.get('_id') or s.get('id'),
                s.get('name', ''),
                s.get('startDate'),
                s.get('endDate'),
                json.dumps(s, ensure_ascii=False)
            ))
        conn.commit()

        return len(seasons)

    def save_competitions(self, season_id: str, competitions: List[Dict[str, Any]]) -> int:
        """Save competitions and their groups for a season."""
        conn = self._get_connection()

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

        conn.commit()
        return len(competitions)

    def save_matches(
        self,
        group_id: str,
        calendar_data: Dict[str, Any],
        competition_name: str = '',
        group_name: str = '',
        season_id: str = ''
    ) -> int:
        """Save matches from calendar data."""
        conn = self._get_connection()
        match_count = 0
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

                conn.execute('''
                    INSERT OR REPLACE INTO matches
                    (id, season_id, competition_id, competition_name, group_id, group_name,
                     home_team_id, home_team_name, away_team_id, away_team_name,
                     date, status, home_score, away_score, venue, venue_address, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
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
                match_count += 1

        # Save teams
        for team in teams.values():
            conn.execute('''
                INSERT OR REPLACE INTO teams (id, name, logo)
                VALUES (?, ?, ?)
            ''', (team['id'], team['name'], team.get('logo')))

        conn.commit()
        return match_count

    def save_standings(self, group_id: str, standings: List[Dict[str, Any]]) -> int:
        """Save standings for a group."""
        conn = self._get_connection()

        for s in standings:
            if s.get('teamId'):
                conn.execute('''
                    INSERT OR REPLACE INTO standings (group_id, team_id, position, data)
                    VALUES (?, ?, ?, ?)
                ''', (
                    group_id,
                    s.get('teamId'),
                    s.get('position'),
                    json.dumps(s, ensure_ascii=False)
                ))

        conn.commit()
        return len(standings)

    def update_scrape_timestamp(self) -> None:
        """Update the last scrape timestamp."""
        conn = self._get_connection()
        conn.execute('''
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('last_scrape', ?, CURRENT_TIMESTAMP)
        ''', (datetime.now(timezone.utc).isoformat(),))
        conn.commit()

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    def get_seasons(self) -> List[Dict[str, Any]]:
        """Get all seasons, ordered by name descending."""
        conn = self._get_connection()
        rows = conn.execute(
            'SELECT data FROM seasons ORDER BY name DESC'
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_competitions(self, season_id: str) -> List[Dict[str, Any]]:
        """Get competitions for a season."""
        conn = self._get_connection()
        rows = conn.execute(
            'SELECT data FROM competitions WHERE season_id = ? ORDER BY name',
            (season_id,)
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_all_competitions(self) -> List[Dict[str, Any]]:
        """Get all competitions across all seasons."""
        conn = self._get_connection()
        rows = conn.execute('''
            SELECT data, season_id FROM competitions ORDER BY name
        ''').fetchall()

        result = []
        for row in rows:
            comp = json.loads(row[0])
            comp['_season_id'] = row[1]
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
        return [json.loads(row[0]) for row in rows]

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

        return [{'id': r[0], 'name': r[1], 'logo': r[2]} for r in rows]

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

        return [{'id': r[0], 'name': r[1], 'logo': r[2]} for r in rows]

    def get_standings(self, group_id: str) -> List[Dict[str, Any]]:
        """Get standings for a group."""
        conn = self._get_connection()
        rows = conn.execute(
            'SELECT data FROM standings WHERE group_id = ? ORDER BY position',
            (group_id,)
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

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

        last_updated = datetime.fromisoformat(row[0].replace('Z', '+00:00'))
        age = datetime.now(timezone.utc) - last_updated
        age_minutes = int(age.total_seconds() / 60)

        # Get stats
        stats = {}
        for table in ['seasons', 'competitions', 'groups', 'matches', 'teams']:
            count_row = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()
            stats[table] = count_row[0] if count_row else 0

        return {
            'exists': True,
            'stale': age_minutes > config.CACHE_TTL_MINUTES,
            'last_updated': row[0],
            'age_minutes': age_minutes,
            'stats': stats
        }

    def get_database_size(self) -> int:
        """Get estimated database size based on row counts."""
        # Turso doesn't expose file size, estimate based on rows
        conn = self._get_connection()
        total = 0
        for table in ['seasons', 'competitions', 'groups', 'matches', 'teams', 'standings']:
            count_row = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()
            count = count_row[0] if count_row else 0
            # Rough estimate: ~500 bytes per row average
            total += count * 500
        return total

    def clear_all(self) -> None:
        """Clear all data from database."""
        conn = self._get_connection()
        for table in ['standings', 'matches', 'teams', 'groups', 'competitions', 'seasons']:
            conn.execute(f'DELETE FROM {table}')
        conn.execute("DELETE FROM metadata WHERE key = 'last_scrape'")
        conn.commit()

    def vacuum(self) -> None:
        """Optimize database storage - no-op for Turso (handled by service)."""
        # Turso handles optimization automatically
        pass
