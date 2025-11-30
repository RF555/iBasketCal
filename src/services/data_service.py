"""
Data Service - Provides access to basketball data from the database.

Manages data access and provides query methods for seasons, competitions, and matches.
Supports multiple database backends via the DatabaseInterface abstraction.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from ..storage import get_database, DatabaseInterface
from ..scraper.nbn23_scraper import NBN23Scraper
from ..scraper.sportspress_api import SportsPress
from .. import config


class DataService:
    """
    Service layer for accessing basketball data.
    Uses the database interface for storage with the scraper for data refresh.
    Supports multiple database backends (SQLite, Turso, Supabase) via DB_TYPE env var.
    """

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Get database from factory (respects DB_TYPE env var)
        self.db: DatabaseInterface = get_database()

        # Scrapers (lazy initialization)
        self._scraper: Optional[NBN23Scraper] = None
        self._sportspress: Optional[SportsPress] = None

        # Scraping state
        self._scrape_lock = threading.Lock()
        self._is_scraping = False
        self._last_scrape_error: Optional[str] = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._shutdown = False

    @property
    def scraper(self) -> NBN23Scraper:
        """Lazy initialization of scraper with database."""
        if self._scraper is None:
            self._scraper = NBN23Scraper(
                headless=True,
                cache_dir=str(self.cache_dir),
                database=self.db
            )
        return self._scraper

    @property
    def sportspress(self) -> SportsPress:
        """Lazy initialization of SportsPress API client."""
        if self._sportspress is None:
            self._sportspress = SportsPress(database=self.db)
        return self._sportspress

    def shutdown(self) -> None:
        """
        Shutdown the data service and cleanup resources.
        Called during application shutdown.
        """
        self._shutdown = True
        self._executor.shutdown(wait=False, cancel_futures=True)
        print("[*] DataService shutdown complete")

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get data, refreshing if needed.

        For backward compatibility, returns dict with 'seasons' key.
        """
        if force_refresh:
            self._run_scrape()

        cache_info = self.db.get_cache_info()
        if not cache_info['exists']:
            self._run_scrape()

        return {'seasons': self.db.get_seasons()}

    def _run_scrape(self) -> None:
        """Run the scraper (blocking)."""
        with self._scrape_lock:
            if self._is_scraping:
                print("[*] Scrape already in progress, skipping...")
                return
            self._is_scraping = True
            self._last_scrape_error = None

        try:
            print("[*] Starting scrape...")
            self.scraper.scrape()
            print("[+] Scrape completed successfully")
        except Exception as e:
            self._last_scrape_error = str(e)
            print(f"[!] Scrape failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._is_scraping = False

    def refresh_async(self) -> bool:
        """
        Start a background scrape.

        Returns:
            True if started, False if already running
        """
        with self._scrape_lock:
            if self._is_scraping:
                return False
            self._is_scraping = True
            self._last_scrape_error = None

        def do_scrape():
            try:
                print("[*] Background scrape thread started...")
                self.scraper.scrape()
                print("[+] Background scrape completed successfully")
            except Exception as e:
                self._last_scrape_error = str(e)
                print(f"[!] Background scrape failed: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self._is_scraping = False

        self._executor.submit(do_scrape)
        return True

    def get_last_scrape_error(self) -> Optional[str]:
        """Get the last scrape error message, if any."""
        return self._last_scrape_error

    def is_scraping(self) -> bool:
        """Check if a scrape is currently in progress."""
        return self._is_scraping

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the cache status."""
        return self.db.get_cache_info()

    # =========================================================================
    # DATA ACCESS METHODS (delegate to database)
    # =========================================================================

    def get_seasons(self) -> List[Dict[str, Any]]:
        """Get all seasons."""
        return self.db.get_seasons()

    def get_competitions(self, season_id: str) -> List[Dict[str, Any]]:
        """Get competitions for a season."""
        return self.db.get_competitions(season_id)

    def get_all_competitions(self) -> List[Dict[str, Any]]:
        """Get all competitions across all seasons."""
        return self.db.get_all_competitions()

    def get_matches(self, group_id: str) -> List[Dict[str, Any]]:
        """Get all matches for a competition group."""
        return self.db.get_matches(group_id=group_id)

    def get_all_matches(
        self,
        season_id: Optional[str] = None,
        competition_name: Optional[str] = None,
        team_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all matches with optional filters.

        Args:
            season_id: Filter by season ID
            competition_name: Filter by competition name (partial match)
            team_name: Filter by team name (partial match, either team)

        Returns:
            List of match dictionaries with metadata
        """
        return self.db.get_matches(
            season_id=season_id,
            competition_name=competition_name,
            team_name=team_name
        )

    def get_teams(self, season_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all unique teams, optionally filtered by season."""
        return self.db.get_teams(season_id=season_id)

    def search_teams(
        self,
        query: str,
        season_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for teams by name."""
        return self.db.search_teams(query, season_id=season_id)

    # =========================================================================
    # SPORTSPRESS PLAYER METHODS
    # =========================================================================

    def refresh_players(self) -> Dict[str, Any]:
        """
        Fetch all players from SportsPress API and save to database.

        Returns:
            Dictionary with counts and elapsed time
        """
        print("[*] Starting player data refresh from SportsPress...")
        return self.sportspress.scrape_players()

    def refresh_players_async(self) -> bool:
        """
        Start a background player data refresh.

        Returns:
            True if started, False if already running
        """
        # Reuse the same lock to prevent concurrent refreshes
        with self._scrape_lock:
            if self._is_scraping:
                return False

        def do_refresh():
            try:
                print("[*] Background player refresh started...")
                self.sportspress.scrape_players()
                print("[+] Background player refresh completed")
            except Exception as e:
                print(f"[!] Background player refresh failed: {e}")
                import traceback
                traceback.print_exc()

        self._executor.submit(do_refresh)
        return True

    def search_players(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search players by name.

        Args:
            query: Search query (partial name match)
            limit: Maximum number of results

        Returns:
            List of player dictionaries
        """
        return self.db.search_players(query, limit=limit)

    def get_player(self, player_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single player by ID (minimal data from cache).

        Args:
            player_id: The player's ID

        Returns:
            Player dictionary with minimal data, or None
        """
        return self.db.get_player(player_id)

    def get_player_with_stats(self, player_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single player by ID with full statistics fetched on-demand.

        This method:
        1. Gets minimal player data from the database
        2. Fetches full player data (including stats) from SportsPress API
        3. Enriches with team/league names
        4. Returns combined data

        Args:
            player_id: The player's ID

        Returns:
            Player dictionary with stats and resolved names, or None
        """
        # First check if player exists in our cache
        cached_player = self.db.get_player(player_id)
        if not cached_player:
            return None

        # Fetch full player data with stats from API
        try:
            full_player = self.sportspress.get_player_stats(player_id)
            if not full_player:
                # API failed, return cached data without stats
                return self._enrich_player(cached_player)

            # Merge API data with enrichment
            return self._enrich_player(full_player)

        except Exception as e:
            print(f"[!] Error fetching player stats: {e}")
            # Return cached data without stats on error
            return self._enrich_player(cached_player)

    def get_player_leagues(self, player_id: int) -> List[Dict[str, Any]]:
        """
        Get all leagues for a player.

        Args:
            player_id: The player's ID

        Returns:
            List of league dictionaries with 'id' and 'name'
        """
        player = self.db.get_player(player_id)
        if not player:
            return []

        league_ids = player.get('leagues', [])
        all_leagues = self.db.get_sportspress_leagues()

        return [
            lg for lg in all_leagues
            if lg['id'] in league_ids
        ]

    def get_players(
        self,
        team_id: Optional[int] = None,
        league_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get players with optional filters.

        Args:
            team_id: Filter by team ID
            league_id: Filter by league ID
            limit: Maximum number of players

        Returns:
            List of player dictionaries
        """
        return self.db.get_players(team_id=team_id, league_id=league_id, limit=limit)

    def get_sportspress_leagues(self) -> List[Dict[str, Any]]:
        """Get all SportsPress leagues."""
        return self.db.get_sportspress_leagues()

    def get_sportspress_teams(self) -> List[Dict[str, Any]]:
        """Get all SportsPress teams."""
        return self.db.get_sportspress_teams()

    def _enrich_player(self, player: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich player data with resolved team and league names.

        Handles both minimal format (teams) and full API format (current_teams).

        Args:
            player: Raw player dictionary from database or API

        Returns:
            Player dictionary with added _teams, _leagues, _current_teams, _past_teams
        """
        # Get all leagues and teams for lookup
        all_leagues = {lg['id']: lg for lg in self.db.get_sportspress_leagues()}
        all_teams = {t['id']: t for t in self.db.get_sportspress_teams()}

        # Resolve current teams (handle both 'teams' and 'current_teams')
        current_team_ids = player.get('teams') or player.get('current_teams', [])
        current_teams = [
            all_teams.get(tid, {'id': tid, 'name': f'Team {tid}'})
            for tid in current_team_ids
        ]

        # Resolve past teams
        past_team_ids = player.get('past_teams', [])
        past_teams = [
            all_teams.get(tid, {'id': tid, 'name': f'Team {tid}'})
            for tid in past_team_ids
        ]

        # Resolve leagues
        league_ids = player.get('leagues', [])
        leagues = [
            all_leagues.get(lid, {'id': lid, 'name': f'League {lid}'})
            for lid in league_ids
        ]

        # Add enriched data
        enriched = {
            **player,
            '_current_teams': current_teams,
            '_past_teams': past_teams,
            '_leagues': leagues
        }

        return enriched


# CLI entry point for testing
if __name__ == '__main__':
    service = DataService()

    print("=== Cache Info ===")
    info = service.get_cache_info()
    print(f"Exists: {info['exists']}")
    print(f"Stale: {info['stale']}")
    print(f"Last updated: {info['last_updated']}")
    if info.get('stats'):
        print(f"Stats: {info['stats']}")

    print("\n=== Seasons ===")
    seasons = service.get_seasons()
    for s in seasons[:5]:
        print(f"  - {s.get('name', 'Unknown')} ({s.get('_id', '')})")

    print("\n=== Teams (first 10) ===")
    teams = service.get_teams()
    for t in teams[:10]:
        print(f"  - {t.get('name', 'Unknown')}")

    print("\n=== Sample Matches ===")
    matches = service.get_all_matches(team_name="Maccabi")
    print(f"Found {len(matches)} matches for 'Maccabi'")
    for m in matches[:3]:
        home = m.get('homeTeam', {}).get('name', 'TBD')
        away = m.get('awayTeam', {}).get('name', 'TBD')
        date = m.get('date', 'TBD')[:10]
        print(f"  - {home} vs {away} ({date})")
