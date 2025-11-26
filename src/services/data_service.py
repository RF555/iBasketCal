"""
Data Service - Provides access to basketball data from cache.

Manages caching and provides query methods for seasons, competitions, and matches.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import threading
from typing import Optional
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

from ..scraper.nbn23_scraper import NBN23Scraper


class DataService:
    """
    Service layer for accessing basketball data.
    Manages caching and provides query methods.
    """

    CACHE_TTL_MINUTES = 30

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.scraper = NBN23Scraper(headless=True, cache_dir=cache_dir)
        self._data: Optional[dict] = None
        self._scrape_lock = threading.Lock()
        self._is_scraping = False
        self._executor = ThreadPoolExecutor(max_workers=1)

    def get_data(self, force_refresh: bool = False) -> dict:
        """Get data, refreshing if stale or forced."""
        if force_refresh:
            self._run_scrape()
        elif self._data is None:
            self._data = self.scraper.load_cache()
            if self._data is None:
                self._run_scrape()

        return self._data or self._empty_data()

    def _run_scrape(self) -> None:
        """Run the scraper (blocking)."""
        with self._scrape_lock:
            if self._is_scraping:
                print("[*] Scrape already in progress, skipping...")
                return
            self._is_scraping = True

        try:
            print("[*] Starting scrape in background thread...")
            self._data = self.scraper.scrape()
            print("[+] Scrape completed successfully")
        except Exception as e:
            print(f"[!] Scrape failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._is_scraping = False

    def refresh_async(self) -> bool:
        """
        Start a background scrape. Returns True if started, False if already running.
        """
        with self._scrape_lock:
            if self._is_scraping:
                return False
            self._is_scraping = True
            self._last_scrape_error = None

        def do_scrape():
            try:
                print("[*] Background scrape thread started...")
                new_data = self.scraper.scrape()
                # Only update data if scrape was successful (has seasons)
                if new_data.get('seasons'):
                    self._data = new_data
                    print("[+] Background scrape completed successfully")
                else:
                    self._last_scrape_error = "Scrape returned empty data"
                    print("[!] Background scrape returned empty data - keeping old cache")
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
        return getattr(self, '_last_scrape_error', None)

    def is_scraping(self) -> bool:
        """Check if a scrape is currently in progress."""
        return self._is_scraping

    def _empty_data(self) -> dict:
        """Return empty data structure."""
        return {
            'seasons': [],
            'competitions': {},
            'calendars': {},
            'standings': {},
            'scraped_at': None
        }

    def _is_cache_stale(self) -> bool:
        """Check if cache is older than TTL."""
        cache_file = self.cache_dir / 'nbn23_data.json'
        if not cache_file.exists():
            return True

        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        return datetime.now() - mtime > timedelta(minutes=self.CACHE_TTL_MINUTES)

    def get_cache_info(self) -> dict:
        """Get information about the cache status."""
        cache_file = self.cache_dir / 'nbn23_data.json'

        if not cache_file.exists():
            return {
                'exists': False,
                'stale': True,
                'last_updated': None,
                'age_minutes': None
            }

        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        age = datetime.now() - mtime

        return {
            'exists': True,
            'stale': age > timedelta(minutes=self.CACHE_TTL_MINUTES),
            'last_updated': mtime.isoformat(),
            'age_minutes': int(age.total_seconds() / 60)
        }

    def get_seasons(self) -> list:
        """Get all seasons."""
        data = self.get_data()
        return data.get('seasons', [])

    def get_competitions(self, season_id: str) -> list:
        """Get competitions for a season."""
        data = self.get_data()
        return data.get('competitions', {}).get(season_id, [])

    def get_all_competitions(self) -> list:
        """Get all competitions across all seasons."""
        data = self.get_data()
        all_comps = []

        for season_id, comps in data.get('competitions', {}).items():
            if isinstance(comps, list):
                for comp in comps:
                    comp_copy = deepcopy(comp)
                    comp_copy['_season_id'] = season_id
                    all_comps.append(comp_copy)

        return all_comps

    def get_matches(self, group_id: str) -> list:
        """Get all matches for a competition group."""
        data = self.get_data()
        calendar = data.get('calendars', {}).get(group_id, {})

        matches = []
        rounds = calendar.get('rounds', [])
        if isinstance(rounds, list):
            for round_data in rounds:
                if isinstance(round_data, dict):
                    round_matches = round_data.get('matches', [])
                    if isinstance(round_matches, list):
                        matches.extend(round_matches)

        return matches

    def get_all_matches(
        self,
        season_id: Optional[str] = None,
        competition_name: Optional[str] = None,
        team_name: Optional[str] = None
    ) -> list:
        """
        Get all matches with optional filters.

        Args:
            season_id: Filter by season ID
            competition_name: Filter by competition name (partial match, case-insensitive)
            team_name: Filter by team name (partial match, case-insensitive)

        Returns:
            List of match dictionaries with added metadata
        """
        data = self.get_data()
        all_matches = []

        # Determine which seasons to process
        seasons = data.get('seasons', [])
        if season_id:
            seasons = [s for s in seasons if s.get('_id') == season_id]

        for season in seasons:
            sid = season.get('_id', '')
            season_name = season.get('name', '')
            competitions = data.get('competitions', {}).get(sid, [])

            if not isinstance(competitions, list):
                continue

            for comp in competitions:
                comp_name = comp.get('name', '')

                # Filter by competition name
                if competition_name and competition_name.lower() not in comp_name.lower():
                    continue

                groups = comp.get('groups', [])
                if not isinstance(groups, list):
                    continue

                for group in groups:
                    gid = group.get('id', '')
                    group_name = group.get('name', '')
                    calendar = data.get('calendars', {}).get(gid, {})

                    rounds = calendar.get('rounds', [])
                    if not isinstance(rounds, list):
                        continue

                    for round_data in rounds:
                        if not isinstance(round_data, dict):
                            continue

                        round_matches = round_data.get('matches', [])
                        if not isinstance(round_matches, list):
                            continue

                        for match in round_matches:
                            if not isinstance(match, dict):
                                continue

                            # Filter by team name
                            if team_name:
                                home_team = match.get('homeTeam', {})
                                away_team = match.get('awayTeam', {})
                                home = home_team.get('name', '') if isinstance(home_team, dict) else ''
                                away = away_team.get('name', '') if isinstance(away_team, dict) else ''

                                if (team_name.lower() not in home.lower() and
                                    team_name.lower() not in away.lower()):
                                    continue

                            # Create a copy and add metadata
                            match_copy = deepcopy(match)
                            match_copy['_competition'] = comp_name
                            match_copy['_group'] = group_name
                            match_copy['_season'] = season_name
                            match_copy['_season_id'] = sid
                            match_copy['_group_id'] = gid

                            all_matches.append(match_copy)

        # Sort by date
        all_matches.sort(key=lambda m: m.get('date', '') or '')

        return all_matches

    def get_teams(self, season_id: Optional[str] = None) -> list:
        """
        Get all unique teams from matches.

        Args:
            season_id: Filter by season ID

        Returns:
            List of unique team dictionaries
        """
        matches = self.get_all_matches(season_id=season_id)
        teams_dict = {}

        for match in matches:
            for team_key in ['homeTeam', 'awayTeam']:
                team = match.get(team_key, {})
                if isinstance(team, dict) and team.get('id'):
                    team_id = team['id']
                    if team_id not in teams_dict:
                        teams_dict[team_id] = {
                            'id': team_id,
                            'name': team.get('name', ''),
                            'logo': team.get('logo', '')
                        }

        # Sort by name
        teams = list(teams_dict.values())
        teams.sort(key=lambda t: t.get('name', ''))

        return teams

    def search_teams(self, query: str, season_id: Optional[str] = None) -> list:
        """
        Search for teams by name.

        Args:
            query: Search query (case-insensitive partial match)
            season_id: Filter by season ID

        Returns:
            List of matching team dictionaries
        """
        teams = self.get_teams(season_id=season_id)
        query_lower = query.lower()

        return [t for t in teams if query_lower in t.get('name', '').lower()]


# CLI entry point for testing
if __name__ == '__main__':
    service = DataService()

    print("=== Cache Info ===")
    print(service.get_cache_info())

    print("\n=== Seasons ===")
    seasons = service.get_seasons()
    for s in seasons[:5]:
        print(f"  - {s.get('name', 'Unknown')} ({s.get('_id', '')})")

    print("\n=== Teams (first 10) ===")
    teams = service.get_teams()
    for t in teams[:10]:
        print(f"  - {t.get('name', 'Unknown')}")

    print("\n=== Recent Matches (first 5) ===")
    matches = service.get_all_matches()
    for m in matches[:5]:
        home = m.get('homeTeam', {}).get('name', 'TBD')
        away = m.get('awayTeam', {}).get('name', 'TBD')
        date = m.get('date', 'TBD')
        print(f"  - {home} vs {away} ({date})")
