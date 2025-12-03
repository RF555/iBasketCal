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

        # Scraper (lazy initialization)
        self._scraper: Optional[NBN23Scraper] = None

        # Scraping state
        self._scrape_lock = threading.Lock()
        self._is_scraping = False
        self._last_scrape_error: Optional[str] = None
        self._executor = ThreadPoolExecutor(max_workers=1)

        # Match refresh state
        self._refresh_type: Optional[str] = None  # "full" | "matches" | None
        self._refresh_result: Optional[Dict[str, Any]] = None

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
        Start a background full scrape.

        Returns:
            True if started, False if already running
        """
        with self._scrape_lock:
            if self._is_scraping:
                return False
            self._is_scraping = True
            self._refresh_type = "full"
            self._last_scrape_error = None
            self._refresh_result = None

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
                self._refresh_type = None

        self._executor.submit(do_scrape)
        return True

    def refresh_matches_async(self) -> tuple:
        """
        Start a background match-only refresh.

        Returns:
            Tuple of (started: bool, reason: str)
            - (True, "started") - Refresh started
            - (False, "in_progress") - Already scraping
            - (False, "no_data") - No groups in database
        """
        # Check for existing groups
        group_ids = self.db.get_all_group_ids()
        if not group_ids:
            return False, "no_data"

        with self._scrape_lock:
            if self._is_scraping:
                return False, "in_progress"
            self._is_scraping = True
            self._refresh_type = "matches"
            self._last_scrape_error = None
            self._refresh_result = None

        def do_match_scrape():
            try:
                print("[*] Background match refresh started...")
                known_team_ids = self.db.get_all_team_ids()
                result = self.scraper.scrape_matches_only(
                    group_ids=group_ids,
                    known_team_ids=known_team_ids
                )
                self._refresh_result = result
                print("[+] Background match refresh completed")
            except Exception as e:
                self._last_scrape_error = str(e)
                print(f"[!] Background match refresh failed: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self._is_scraping = False
                self._refresh_type = None

        self._executor.submit(do_match_scrape)
        return True, "started"

    def get_refresh_type(self) -> Optional[str]:
        """Get the type of current/last refresh ("full" | "matches" | None)."""
        return self._refresh_type

    def get_refresh_result(self) -> Optional[Dict[str, Any]]:
        """Get the result of the last match refresh (missing data info)."""
        return self._refresh_result

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
