"""
Supabase Database Storage for Israeli Basketball Calendar.

Provides PostgreSQL-based cloud storage using Supabase's REST API.
Key differences from SQLite:
- Uses supabase-py client library (REST API)
- upsert() instead of INSERT OR REPLACE
- ilike() for case-insensitive LIKE queries
- or_() for OR conditions in queries
- Batch size limits (chunk large inserts at 500 rows)
- initialize() verifies tables exist (doesn't create them)
- vacuum() is no-op (not available via REST)

Requires: pip install supabase
Schema must be created first via scripts/supabase_schema.sql
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .base import DatabaseInterface
from .exceptions import ConfigurationError, ConnectionError
from .. import config


# Batch size for upsert operations
BATCH_SIZE = 500


class SupabaseDatabase(DatabaseInterface):
    """
    Supabase cloud database implementation.

    Uses PostgreSQL via Supabase's REST API.
    Implements the DatabaseInterface abstract base class.
    """

    def __init__(self):
        """
        Create Supabase database instance.

        Reads configuration from environment variables:
        - SUPABASE_URL: Project URL (e.g., https://your-project.supabase.co)
        - SUPABASE_KEY: Anon or service key
        """
        self._url = os.environ.get('SUPABASE_URL')
        self._key = os.environ.get('SUPABASE_KEY')
        self._client = None
        self._initialized = False

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def initialize(self) -> None:
        """Initialize the database connection and verify schema."""
        if self._initialized:
            return

        if not self._url:
            raise ConfigurationError(
                "SUPABASE_URL environment variable is required for Supabase backend"
            )
        if not self._key:
            raise ConfigurationError(
                "SUPABASE_KEY environment variable is required for Supabase backend"
            )

        # Verify connection and schema by querying metadata
        client = self._get_client()
        try:
            # Check if tables exist by querying metadata
            client.table('metadata').select('key').limit(1).execute()
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to Supabase or schema not initialized. "
                f"Run scripts/supabase_schema.sql in Supabase SQL Editor first. "
                f"Error: {e}"
            )

        self._initialized = True

    def _get_client(self):
        """Get or create Supabase client."""
        if self._client is None:
            try:
                from supabase import create_client
            except ImportError:
                raise ConfigurationError(
                    "supabase package not installed. "
                    "Install with: pip install supabase"
                )

            try:
                self._client = create_client(self._url, self._key)
            except Exception as e:
                raise ConnectionError(f"Failed to create Supabase client: {e}")

        return self._client

    def close(self) -> None:
        """Close database connection (no-op for Supabase REST API)."""
        # REST API doesn't maintain persistent connections
        self._client = None

    def health_check(self) -> bool:
        """Check if the database connection is healthy."""
        try:
            client = self._get_client()
            client.table('metadata').select('key').limit(1).execute()
            return True
        except Exception:
            return False

    # =========================================================================
    # WRITE OPERATIONS
    # =========================================================================

    def save_seasons(self, seasons: List[Dict[str, Any]]) -> int:
        """Save seasons to database."""
        client = self._get_client()

        rows = [
            {
                'id': s.get('_id') or s.get('id'),
                'name': s.get('name', ''),
                'start_date': s.get('startDate'),
                'end_date': s.get('endDate'),
                'data': json.dumps(s, ensure_ascii=False),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            for s in seasons
        ]

        # Upsert in batches
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            client.table('seasons').upsert(batch, on_conflict='id').execute()

        return len(seasons)

    def save_competitions(self, season_id: str, competitions: List[Dict[str, Any]]) -> int:
        """Save competitions and their groups for a season."""
        client = self._get_client()

        comp_rows = []
        group_rows = []

        for comp in competitions:
            comp_id = comp.get('id') or f"{season_id}_{comp.get('name', 'unknown')}"

            comp_rows.append({
                'id': comp_id,
                'season_id': season_id,
                'name': comp.get('name', ''),
                'data': json.dumps(comp, ensure_ascii=False),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })

            for group in comp.get('groups', []):
                group_rows.append({
                    'id': group.get('id'),
                    'competition_id': comp_id,
                    'season_id': season_id,
                    'name': group.get('name', ''),
                    'type': group.get('type'),
                    'data': json.dumps(group, ensure_ascii=False),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })

        # Upsert competitions
        for i in range(0, len(comp_rows), BATCH_SIZE):
            batch = comp_rows[i:i + BATCH_SIZE]
            client.table('competitions').upsert(batch, on_conflict='id').execute()

        # Upsert groups
        for i in range(0, len(group_rows), BATCH_SIZE):
            batch = group_rows[i:i + BATCH_SIZE]
            client.table('groups').upsert(batch, on_conflict='id').execute()

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
        client = self._get_client()
        match_rows = []
        team_rows = []
        teams_seen = set()

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
                if home_team.get('id') and home_team['id'] not in teams_seen:
                    teams_seen.add(home_team['id'])
                    team_rows.append({
                        'id': home_team['id'],
                        'name': home_team.get('name', ''),
                        'logo': home_team.get('logo'),
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    })
                if away_team.get('id') and away_team['id'] not in teams_seen:
                    teams_seen.add(away_team['id'])
                    team_rows.append({
                        'id': away_team['id'],
                        'name': away_team.get('name', ''),
                        'logo': away_team.get('logo'),
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    })

                # Enrich match with metadata
                enriched_match = {
                    **match,
                    '_competition': competition_name,
                    '_group': group_name,
                    '_group_id': group_id,
                    '_season_id': season_id
                }

                match_rows.append({
                    'id': match_id,
                    'season_id': season_id,
                    'competition_id': None,
                    'competition_name': competition_name,
                    'group_id': group_id,
                    'group_name': group_name,
                    'home_team_id': home_team.get('id'),
                    'home_team_name': home_team.get('name'),
                    'away_team_id': away_team.get('id'),
                    'away_team_name': away_team.get('name'),
                    'date': match.get('date'),
                    'status': match.get('status'),
                    'home_score': home_score,
                    'away_score': away_score,
                    'venue': court.get('place'),
                    'venue_address': court.get('address'),
                    'data': json.dumps(enriched_match, ensure_ascii=False),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })

        # Upsert teams first
        for i in range(0, len(team_rows), BATCH_SIZE):
            batch = team_rows[i:i + BATCH_SIZE]
            client.table('teams').upsert(batch, on_conflict='id').execute()

        # Upsert matches
        for i in range(0, len(match_rows), BATCH_SIZE):
            batch = match_rows[i:i + BATCH_SIZE]
            client.table('matches').upsert(batch, on_conflict='id').execute()

        return len(match_rows)

    def save_standings(self, group_id: str, standings: List[Dict[str, Any]]) -> int:
        """Save standings for a group."""
        client = self._get_client()

        rows = [
            {
                'group_id': group_id,
                'team_id': s.get('teamId'),
                'position': s.get('position'),
                'data': json.dumps(s, ensure_ascii=False),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            for s in standings if s.get('teamId')
        ]

        # Upsert standings (composite key: group_id, team_id)
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            client.table('standings').upsert(batch, on_conflict='group_id,team_id').execute()

        return len(standings)

    def update_scrape_timestamp(self) -> None:
        """Update the last scrape timestamp."""
        client = self._get_client()
        client.table('metadata').upsert({
            'key': 'last_scrape',
            'value': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }, on_conflict='key').execute()

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    def get_seasons(self) -> List[Dict[str, Any]]:
        """Get all seasons, ordered by name descending."""
        client = self._get_client()
        response = client.table('seasons').select('data').order('name', desc=True).execute()
        return [json.loads(row['data']) for row in response.data]

    def get_competitions(self, season_id: str) -> List[Dict[str, Any]]:
        """Get competitions for a season."""
        client = self._get_client()
        response = (
            client.table('competitions')
            .select('data')
            .eq('season_id', season_id)
            .order('name')
            .execute()
        )
        return [json.loads(row['data']) for row in response.data]

    def get_all_competitions(self) -> List[Dict[str, Any]]:
        """Get all competitions across all seasons."""
        client = self._get_client()
        response = (
            client.table('competitions')
            .select('data, season_id')
            .order('name')
            .execute()
        )

        result = []
        for row in response.data:
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
        client = self._get_client()
        query = client.table('matches').select('data')

        if season_id:
            query = query.eq('season_id', season_id)

        if competition_name:
            query = query.ilike('competition_name', f'%{competition_name}%')

        if team_name:
            # OR condition for home or away team
            query = query.or_(
                f"home_team_name.ilike.%{team_name}%,"
                f"away_team_name.ilike.%{team_name}%"
            )

        if group_id:
            query = query.eq('group_id', group_id)

        if status:
            query = query.eq('status', status)

        if date_from:
            query = query.gte('date', date_from)

        if date_to:
            query = query.lte('date', date_to)

        query = query.order('date')

        if limit:
            query = query.limit(limit)

        response = query.execute()
        return [json.loads(row['data']) for row in response.data]

    def get_teams(self, season_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all teams, optionally filtered by season."""
        client = self._get_client()

        if season_id:
            # Use a raw query approach - get team IDs from matches, then fetch teams
            matches_response = (
                client.table('matches')
                .select('home_team_id, away_team_id')
                .eq('season_id', season_id)
                .execute()
            )

            team_ids = set()
            for row in matches_response.data:
                if row.get('home_team_id'):
                    team_ids.add(row['home_team_id'])
                if row.get('away_team_id'):
                    team_ids.add(row['away_team_id'])

            if not team_ids:
                return []

            response = (
                client.table('teams')
                .select('id, name, logo')
                .in_('id', list(team_ids))
                .order('name')
                .execute()
            )
        else:
            response = (
                client.table('teams')
                .select('id, name, logo')
                .order('name')
                .execute()
            )

        return [{'id': r['id'], 'name': r['name'], 'logo': r['logo']} for r in response.data]

    def search_teams(self, query: str, season_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search teams by name."""
        client = self._get_client()

        if season_id:
            # Get team IDs from matches first
            matches_response = (
                client.table('matches')
                .select('home_team_id, away_team_id')
                .eq('season_id', season_id)
                .execute()
            )

            team_ids = set()
            for row in matches_response.data:
                if row.get('home_team_id'):
                    team_ids.add(row['home_team_id'])
                if row.get('away_team_id'):
                    team_ids.add(row['away_team_id'])

            if not team_ids:
                return []

            response = (
                client.table('teams')
                .select('id, name, logo')
                .in_('id', list(team_ids))
                .ilike('name', f'%{query}%')
                .order('name')
                .execute()
            )
        else:
            response = (
                client.table('teams')
                .select('id, name, logo')
                .ilike('name', f'%{query}%')
                .order('name')
                .execute()
            )

        return [{'id': r['id'], 'name': r['name'], 'logo': r['logo']} for r in response.data]

    def get_standings(self, group_id: str) -> List[Dict[str, Any]]:
        """Get standings for a group."""
        client = self._get_client()
        response = (
            client.table('standings')
            .select('data')
            .eq('group_id', group_id)
            .order('position')
            .execute()
        )
        return [json.loads(row['data']) for row in response.data]

    # =========================================================================
    # CACHE INFO & MAINTENANCE
    # =========================================================================

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache status information."""
        client = self._get_client()

        response = (
            client.table('metadata')
            .select('value, updated_at')
            .eq('key', 'last_scrape')
            .execute()
        )

        if not response.data:
            return {
                'exists': False,
                'stale': True,
                'last_updated': None,
                'age_minutes': None,
                'stats': {}
            }

        row = response.data[0]
        last_updated = datetime.fromisoformat(row['value'].replace('Z', '+00:00'))
        age = datetime.now(timezone.utc) - last_updated
        age_minutes = int(age.total_seconds() / 60)

        # Get stats (count queries)
        stats = {}
        for table in ['seasons', 'competitions', 'groups', 'matches', 'teams']:
            count_response = (
                client.table(table)
                .select('id', count='exact')
                .execute()
            )
            stats[table] = count_response.count or 0

        return {
            'exists': True,
            'stale': age_minutes > config.CACHE_TTL_MINUTES,
            'last_updated': row['value'],
            'age_minutes': age_minutes,
            'stats': stats
        }

    def get_database_size(self) -> int:
        """Get estimated database size based on row counts."""
        # Supabase doesn't expose direct storage size via REST API
        # Estimate based on row counts
        client = self._get_client()
        total = 0

        # Tables with 'id' primary key
        for table in ['seasons', 'competitions', 'groups', 'matches', 'teams']:
            count_response = (
                client.table(table)
                .select('id', count='exact')
                .execute()
            )
            count = count_response.count or 0
            # Rough estimate: ~500 bytes per row average
            total += count * 500

        # Standings table has composite key (group_id, team_id), not 'id'
        standings_response = (
            client.table('standings')
            .select('group_id', count='exact')
            .execute()
        )
        standings_count = standings_response.count or 0
        total += standings_count * 500

        return total

    def clear_all(self) -> None:
        """Clear all data from database."""
        client = self._get_client()

        # Delete standings first (uses composite key, not 'id')
        client.table('standings').delete().neq('group_id', '').execute()

        # Delete other tables in order to respect foreign keys
        for table in ['matches', 'teams', 'groups', 'competitions', 'seasons']:
            # Use a filter that matches all rows
            client.table(table).delete().neq('id', '').execute()

        # Clear last_scrape metadata
        client.table('metadata').delete().eq('key', 'last_scrape').execute()

    def vacuum(self) -> None:
        """Optimize database storage - no-op for Supabase (not available via REST)."""
        # VACUUM requires direct SQL access, not available via Supabase REST API
        pass

    # =========================================================================
    # SPORTSPRESS PLAYER DATA
    # =========================================================================

    def save_players(self, players: List[Dict[str, Any]]) -> int:
        """
        Save players with minimal data (stats fetched on-demand).

        Expects minimal player dicts with: id, name, teams, leagues, seasons
        """
        client = self._get_client()

        rows = []
        for player in players:
            player_id = player.get('id')
            if not player_id:
                continue

            # Handle both full API response and minimal data format
            if 'name' in player:
                name = player['name']
            else:
                title = player.get('title', {})
                name = title.get('rendered', '') if isinstance(title, dict) else str(title)

            # Handle both 'teams' and 'current_teams' for flexibility
            teams = player.get('teams') or player.get('current_teams', [])

            rows.append({
                'id': player_id,
                'name': name,
                'team_ids': json.dumps(teams),
                'league_ids': json.dumps(player.get('leagues', [])),
                'season_ids': json.dumps(player.get('seasons', [])),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })

        # Upsert in batches
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            client.table('sp_players').upsert(batch, on_conflict='id').execute()

        return len(players)

    def get_players(
        self,
        team_id: Optional[int] = None,
        league_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get players with optional filters (minimal data)."""
        client = self._get_client()
        query = client.table('sp_players').select('id, name, team_ids, league_ids, season_ids')

        if team_id:
            # PostgreSQL ILIKE for JSON array search
            query = query.ilike('team_ids', f'%{team_id}%')

        if league_id:
            query = query.ilike('league_ids', f'%{league_id}%')

        query = query.order('name')

        if limit:
            query = query.limit(limit)

        response = query.execute()
        return [self._row_to_player(row) for row in response.data]

    def search_players(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search players by name (returns minimal data).

        Splits query into words and matches ALL words in any order.
        Example: "יוסי כהן" matches "יוסי כהן", "כהן יוסי", "יוסי דוד כהן"
        """
        client = self._get_client()

        # Split query into words and require all words to match
        words = query.strip().split()

        if not words:
            return []

        # Build query - each word must appear somewhere in the name
        q = client.table('sp_players').select('id, name, team_ids, league_ids, season_ids')

        for word in words:
            q = q.ilike('name', f'%{word}%')

        response = q.order('name').limit(limit).execute()
        return [self._row_to_player(row) for row in response.data]

    def get_player(self, player_id: int) -> Optional[Dict[str, Any]]:
        """Get a single player by ID (minimal data - no stats)."""
        client = self._get_client()
        response = (
            client.table('sp_players')
            .select('id, name, team_ids, league_ids, season_ids')
            .eq('id', player_id)
            .execute()
        )
        if response.data:
            return self._row_to_player(response.data[0])
        return None

    def _row_to_player(self, row: Dict[str, Any]) -> Dict[str, Any]:
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
        client = self._get_client()

        rows = [
            {
                'id': lg.get('id'),
                'name': lg.get('name', ''),
                'slug': lg.get('slug', ''),
                'data': json.dumps(lg, ensure_ascii=False),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            for lg in leagues if lg.get('id')
        ]

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            client.table('sp_leagues').upsert(batch, on_conflict='id').execute()

        return len(leagues)

    def save_sportspress_teams(self, teams: List[Dict[str, Any]]) -> int:
        """Save SportsPress teams."""
        client = self._get_client()

        rows = [
            {
                'id': t.get('id'),
                'name': t.get('name', ''),
                'slug': t.get('slug', ''),
                'data': json.dumps(t, ensure_ascii=False),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            for t in teams if t.get('id')
        ]

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            client.table('sp_teams').upsert(batch, on_conflict='id').execute()

        return len(teams)

    def save_sportspress_seasons(self, seasons: List[Dict[str, Any]]) -> int:
        """Save SportsPress seasons."""
        client = self._get_client()

        rows = [
            {
                'id': s.get('id'),
                'name': s.get('name', ''),
                'slug': s.get('slug', ''),
                'data': json.dumps(s, ensure_ascii=False),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            for s in seasons if s.get('id')
        ]

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            client.table('sp_seasons').upsert(batch, on_conflict='id').execute()

        return len(seasons)

    def get_sportspress_leagues(self) -> List[Dict[str, Any]]:
        """Get all SportsPress leagues."""
        client = self._get_client()
        response = (
            client.table('sp_leagues')
            .select('id, name, slug')
            .order('name')
            .execute()
        )
        return [{'id': r['id'], 'name': r['name'], 'slug': r['slug']} for r in response.data]

    def get_sportspress_teams(self) -> List[Dict[str, Any]]:
        """Get all SportsPress teams."""
        client = self._get_client()
        response = (
            client.table('sp_teams')
            .select('id, name, slug')
            .order('name')
            .execute()
        )
        return [{'id': r['id'], 'name': r['name'], 'slug': r['slug']} for r in response.data]

    def get_sportspress_seasons(self) -> List[Dict[str, Any]]:
        """Get all SportsPress seasons."""
        client = self._get_client()
        response = (
            client.table('sp_seasons')
            .select('id, name, slug')
            .order('name', desc=True)
            .execute()
        )
        return [{'id': r['id'], 'name': r['name'], 'slug': r['slug']} for r in response.data]
