"""
SportsPress REST API Client for ibasketball.co.il

Fetches player data from the WordPress SportsPress plugin REST API.
No authentication required - public API access.

API Base: https://ibasketball.co.il/wp-json/sportspress/v2

Data Strategy:
- Store minimal player data (id, name, teams, leagues, seasons) ~98 bytes/player
- Fetch full statistics on-demand when player is selected
- Filter by current season to reduce data volume
"""

import requests
import time
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.base import DatabaseInterface


class SportsPress:
    """
    Client for the SportsPress WordPress REST API.

    Fetches player, team, league, and season data from ibasketball.co.il.
    All endpoints are public and require no authentication.

    Uses minimal data storage strategy:
    - Cache only essential player fields (id, name, teams, leagues)
    - Fetch statistics on-demand when player is selected
    """

    BASE_URL = "https://ibasketball.co.il/wp-json/sportspress/v2"

    # Current season ID (2025-2026)
    CURRENT_SEASON_ID = 119472

    def __init__(self, database: Optional["DatabaseInterface"] = None):
        """
        Initialize the SportsPress API client.

        Args:
            database: Optional database interface for saving data
        """
        self.db = database
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "iBasketCal/1.0"
        })
        self._current_season_id: Optional[int] = None

    def _api_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        retry_count: int = 3,
        timeout: int = 60
    ) -> Any:
        """
        Make an API request with retry logic.

        Args:
            endpoint: API endpoint (e.g., 'players', 'teams')
            params: Query parameters
            retry_count: Number of retries on failure
            timeout: Request timeout in seconds

        Returns:
            JSON response data (list or dict)
        """
        url = f"{self.BASE_URL}/{endpoint}"

        for attempt in range(retry_count):
            try:
                response = self.session.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                if attempt < retry_count - 1:
                    print(f"[!] API request failed for {endpoint}, retrying... ({e})")
                    time.sleep(1 * (attempt + 1))  # Exponential backoff
                else:
                    print(f"[!] API request failed for {endpoint}: {e}")
                    return [] if endpoint in ['players', 'teams', 'leagues', 'seasons'] else {}

    def get_current_season_id(self) -> int:
        """
        Get the current season ID (highest year).

        Fetches all seasons and returns the one with the highest year in its name.
        Caches the result for subsequent calls.

        Returns:
            Season ID for the current season
        """
        if self._current_season_id:
            return self._current_season_id

        print("[*] Determining current season...")
        seasons = self._api_request("seasons", {"per_page": 100})

        if not seasons:
            print(f"[!] Could not fetch seasons, using default: {self.CURRENT_SEASON_ID}")
            return self.CURRENT_SEASON_ID

        # Find season with highest year in name (e.g., "2025-2026")
        current = None
        current_year = 0

        for season in seasons:
            name = season.get('name', '')
            # Extract first year from name like "2025-2026"
            try:
                year = int(name.split('-')[0])
                if year > current_year:
                    current_year = year
                    current = season
            except (ValueError, IndexError):
                continue

        if current:
            self._current_season_id = current.get('id')
            print(f"[+] Current season: {current.get('name')} (ID: {self._current_season_id})")
            return self._current_season_id

        print(f"[!] Could not determine current season, using default: {self.CURRENT_SEASON_ID}")
        return self.CURRENT_SEASON_ID

    def get_player_stats(self, player_id: int) -> Dict[str, Any]:
        """
        Fetch full player data including statistics on-demand.

        This is used when a player is selected to get their complete stats.

        Args:
            player_id: The player's ID

        Returns:
            Full player dictionary with statistics
        """
        print(f"[*] Fetching stats for player {player_id}...")
        player = self._api_request(f"players/{player_id}")

        if not player:
            return {}

        # Extract and return the data we need
        title = player.get('title', {})
        name = title.get('rendered', '') if isinstance(title, dict) else str(title)

        return {
            'id': player.get('id'),
            'name': name,
            'teams': player.get('current_teams', []),
            'past_teams': player.get('past_teams', []),
            'leagues': player.get('leagues', []),
            'seasons': player.get('seasons', []),
            'statistics': player.get('statistics', {}),
            'link': player.get('link', '')
        }

    def _extract_minimal_player(self, player: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract minimal player data for storage.

        Args:
            player: Full player data from API

        Returns:
            Minimal player dict with only essential fields
        """
        title = player.get('title', {})
        name = title.get('rendered', '') if isinstance(title, dict) else str(title)

        return {
            'id': player.get('id'),
            'name': name,
            'teams': player.get('current_teams', []),
            'leagues': player.get('leagues', []),
            'seasons': player.get('seasons', [])
        }

    def get_all_players(
        self,
        season_id: Optional[int] = None,
        per_page: int = 100,
        minimal: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch all players with pagination, optionally filtered by season.

        Args:
            season_id: Optional season ID to filter players
            per_page: Number of players per page (max 100)
            minimal: If True, extract only minimal data (default True)

        Returns:
            List of player dictionaries (minimal or full based on flag)
        """
        if season_id:
            print(f"[*] Fetching players for season {season_id}...")
        else:
            print("[*] Fetching all players from SportsPress API...")

        all_players = []
        page = 1

        while True:
            print(f"    [*] Fetching page {page}...")

            params = {
                "per_page": per_page,
                "page": page
            }
            if season_id:
                params["seasons"] = season_id

            players = self._api_request("players", params)

            if not players:
                break

            # Extract minimal data if requested
            if minimal:
                players = [self._extract_minimal_player(p) for p in players]

            all_players.extend(players)
            print(f"    [+] Got {len(players)} players (total: {len(all_players)})")

            # If we got fewer than per_page, we've reached the end
            if len(players) < per_page:
                break

            page += 1
            time.sleep(0.1)  # Rate limiting

        print(f"[+] Total players fetched: {len(all_players)}")
        return all_players

    def get_player(self, player_id: int) -> Dict[str, Any]:
        """
        Fetch a single player by ID.

        Args:
            player_id: The player's ID

        Returns:
            Player dictionary with full details
        """
        return self._api_request(f"players/{player_id}")

    def get_all_leagues(self, per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch all leagues/competitions.

        Returns:
            List of league dictionaries
        """
        print("[*] Fetching all leagues from SportsPress API...")
        all_leagues = []
        page = 1

        while True:
            print(f"    [*] Fetching leagues page {page}...")
            leagues = self._api_request("leagues", {
                "per_page": per_page,
                "page": page
            }, timeout=90)

            if not leagues:
                break

            all_leagues.extend(leagues)
            print(f"    [+] Got {len(leagues)} leagues (total: {len(all_leagues)})")

            if len(leagues) < per_page:
                break

            page += 1
            time.sleep(0.2)

        print(f"[+] Total leagues fetched: {len(all_leagues)}")
        return all_leagues

    def get_all_teams(self, per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch all teams.

        Returns:
            List of team dictionaries
        """
        print("[*] Fetching all teams from SportsPress API...")
        all_teams = []
        page = 1

        while True:
            print(f"    [*] Fetching teams page {page}...")
            teams = self._api_request("teams", {
                "per_page": per_page,
                "page": page
            }, timeout=90)

            if not teams:
                break

            all_teams.extend(teams)
            print(f"    [+] Got {len(teams)} teams (total: {len(all_teams)})")

            if len(teams) < per_page:
                break

            page += 1
            time.sleep(0.2)  # Slightly longer delay for teams

        print(f"[+] Total teams fetched: {len(all_teams)}")
        return all_teams

    def get_all_seasons(self, per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch all seasons.

        Returns:
            List of season dictionaries
        """
        print("[*] Fetching all seasons from SportsPress API...")
        seasons = self._api_request("seasons", {"per_page": per_page})
        print(f"[+] Total seasons fetched: {len(seasons) if seasons else 0}")
        return seasons if seasons else []

    def scrape_players(self) -> Dict[str, Any]:
        """
        Fetch minimal player data for current season only.

        This is optimized for storage efficiency:
        - Only fetches players from the current season
        - Stores minimal data (id, name, teams, leagues, seasons)
        - Skips fetching all leagues/teams (reduces API calls significantly)

        Returns:
            Dictionary with 'players', 'season_id', 'elapsed' keys
        """
        print("[*] Starting SportsPress player data fetch (minimal mode)...")
        start_time = time.time()

        # Get current season ID
        season_id = self.get_current_season_id()

        # Fetch only players from current season with minimal data
        players = self.get_all_players(season_id=season_id, minimal=True)

        # Save to database if available
        if self.db:
            print("[*] Saving players to database...")
            self.db.save_players(players)
            print("[+] Players saved to database")

        elapsed = time.time() - start_time
        print(f"[+] SportsPress scrape complete in {elapsed:.1f}s")
        print(f"    Season: {season_id}")
        print(f"    Players: {len(players)}")

        return {
            'players': players,
            'season_id': season_id,
            'elapsed': elapsed
        }


# CLI entry point for testing
if __name__ == '__main__':
    client = SportsPress()

    print("=== Testing SportsPress API ===\n")

    # Test fetching seasons
    print("--- Seasons ---")
    seasons = client.get_all_seasons()
    for s in seasons[:5]:
        print(f"  - {s.get('name', 'Unknown')} (ID: {s.get('id')})")

    # Test fetching leagues
    print("\n--- Leagues (first 10) ---")
    leagues = client.get_all_leagues()
    for lg in leagues[:10]:
        print(f"  - {lg.get('name', 'Unknown')} (ID: {lg.get('id')})")

    # Test fetching a few players
    print("\n--- Players (first 10) ---")
    players = client._api_request("players", {"per_page": 10, "page": 1})
    for p in players[:10]:
        title = p.get('title', {})
        name = title.get('rendered', 'Unknown') if isinstance(title, dict) else title
        print(f"  - {name} (ID: {p.get('id')})")
        print(f"      Teams: {p.get('current_teams', [])}")
        print(f"      Leagues: {p.get('leagues', [])}")
