"""
NBN23 API Scraper using Playwright for token extraction and direct API calls.

Extracts the authorization token by intercepting widget API requests,
then uses the token to directly call all API endpoints for comprehensive data.
Saves data directly to SQLite database instead of JSON file.
Includes automatic token refresh on 401 errors.
"""

from playwright.sync_api import sync_playwright
import requests
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union, Dict, List, Any, TYPE_CHECKING
import time

if TYPE_CHECKING:
    from ..storage.database import Database


class NBN23Scraper:
    """
    Scrapes Israeli basketball data from the NBN23 API.

    Process:
    1. Load widget page to extract the authorization token
    2. Use token to directly call API endpoints for all data
    3. Save results directly to SQLite database
    """

    WIDGET_URL = "https://ibasketball.co.il/swish/"
    API_BASE = "https://api.swish.nbn23.com"
    ORIGIN = "https://ibasketball.co.il"

    def __init__(
        self,
        headless: bool = True,
        cache_dir: str = "cache",
        database: Optional["Database"] = None
    ):
        self.headless = headless
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.token: Optional[str] = None
        self.session: Optional[requests.Session] = None
        self.db = database

    def _extract_token(self) -> str:
        """
        Extract the API authorization token by intercepting widget requests.

        Returns:
            The authorization token string

        Raises:
            RuntimeError: If token extraction fails
        """
        print("[*] Extracting API token from widget...")
        token = None
        page_error = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 900},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='he-IL',
                    timezone_id='Asia/Jerusalem'
                )
                page = context.new_page()

                def handle_route(route, request):
                    nonlocal token
                    auth = request.headers.get('authorization')
                    if auth and not token:
                        token = auth
                        print(f"[+] Token captured: {token[:20]}...")
                    route.continue_()

                page.route("**/api.swish.nbn23.com/**", handle_route)

                try:
                    print(f"[*] Loading {self.WIDGET_URL}...")
                    page.goto(self.WIDGET_URL, wait_until='domcontentloaded', timeout=45000)
                    page.wait_for_timeout(10000)
                except Exception as e:
                    page_error = str(e)
                    print(f"[!] Page load error: {e}")
                finally:
                    context.close()
                    browser.close()
        except Exception as e:
            print(f"[!] Playwright error: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Playwright error: {e}")

        if not token:
            error_msg = "Failed to extract API token from widget"
            if page_error:
                error_msg += f" (page error: {page_error})"
            raise RuntimeError(error_msg)

        self.token = token
        return token

    def _init_session(self) -> None:
        """Initialize HTTP session with auth headers."""
        if not self.token:
            self._extract_token()

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": self.token,
            "Origin": self.ORIGIN,
            "Accept": "application/json"
        })

    def _api_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        retry: bool = True
    ) -> Union[Dict, List]:
        """
        Make authenticated API request with automatic token refresh on 401.

        Args:
            endpoint: API endpoint (e.g., 'seasons', 'competitions')
            params: Query parameters
            retry: Whether to retry on 401 (set False to prevent infinite loop)

        Returns:
            JSON response data (dict or list)
        """
        if not self.session:
            self._init_session()

        url = f"{self.API_BASE}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)

            # Handle token expiration
            if response.status_code == 401 and retry:
                print("[!] Token expired (401), re-extracting...")
                self.token = None
                self.session = None
                self._init_session()
                return self._api_request(endpoint, params, retry=False)

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            print(f"[!] API request failed for {endpoint}: {e}")
            # Return empty structure based on expected type
            return {} if endpoint in ['calendar', 'standings'] else []

    def scrape(self) -> Dict[str, Any]:
        """
        Main scraping method. Fetches all data and saves to SQLite.

        Returns:
            Summary dict with counts and timing

        Raises:
            RuntimeError: If token extraction fails
        """
        print("[*] Starting data refresh...")
        start_time = time.time()

        # Step 1: Extract token
        self._extract_token()
        self._init_session()

        # Step 2: Fetch and save seasons
        print("[*] Fetching seasons...")
        seasons = self._api_request("seasons")
        if self.db:
            self.db.save_seasons(seasons)
        print(f"    [+] Saved {len(seasons)} seasons")

        # Step 3: Fetch and save competitions for each season
        all_groups = []
        for season in seasons:
            season_id = season.get('_id')
            if not season_id:
                continue

            season_name = season.get('name', season_id)
            print(f"[*] Fetching competitions for {season_name}...")
            comps = self._api_request("competitions", {"seasonId": season_id})

            if self.db:
                self.db.save_competitions(season_id, comps)

            # Collect group info for calendar fetching
            for comp in comps:
                for group in comp.get('groups', []):
                    group_id = group.get('id')
                    if group_id:
                        all_groups.append({
                            'id': group_id,
                            'season_id': season_id,
                            'season_name': season_name,
                            'competition_name': comp.get('name', ''),
                            'group_name': group.get('name', '')
                        })

        print(f"    [+] Found {len(all_groups)} total groups")

        # Step 4: Fetch calendars and standings for all groups
        total_matches = 0
        for i, group_info in enumerate(all_groups):
            group_id = group_info['id']
            if not group_id:
                continue

            # Progress indicator
            if (i + 1) % 50 == 0 or i == 0:
                print(f"    [*] Processing group {i + 1}/{len(all_groups)}...")

            # Fetch calendar
            calendar = self._api_request("calendar", {"groupId": group_id})
            if calendar and self.db:
                count = self.db.save_matches(
                    group_id=group_id,
                    calendar_data=calendar,
                    competition_name=group_info['competition_name'],
                    group_name=group_info['group_name'],
                    season_id=group_info['season_id']
                )
                total_matches += count

            # Fetch standings
            standings = self._api_request("standings", {"groupId": group_id})
            if standings and self.db:
                self.db.save_standings(group_id, standings)

            # Small delay to be nice to the API
            time.sleep(0.05)

        # Step 5: Update scrape timestamp
        if self.db:
            self.db.update_scrape_timestamp()

        elapsed = time.time() - start_time
        print(f"[+] Data refresh complete in {elapsed:.1f}s")
        print(f"    Seasons: {len(seasons)}")
        print(f"    Groups: {len(all_groups)}")
        print(f"    Matches: {total_matches}")

        return {
            'seasons': len(seasons),
            'groups': len(all_groups),
            'matches': total_matches,
            'elapsed': elapsed
        }

    # =========================================================================
    # LEGACY METHODS (for backward compatibility during migration)
    # =========================================================================

    def load_cache(self) -> Optional[Dict]:
        """
        Load data from JSON cache (legacy).
        Returns None if database is being used.
        """
        if self.db:
            # Using database, return None to trigger DB read
            return None

        cache_file = self.cache_dir / 'nbn23_data.json'
        if not cache_file.exists():
            return None

        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)


# CLI entry point
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Scrape NBN23 basketball data')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode (default: True)')
    parser.add_argument('--no-headless', dest='headless', action='store_false',
                        help='Run browser with visible window')
    parser.add_argument('--cache-dir', default='cache',
                        help='Directory to store cached data')

    args = parser.parse_args()

    # Import database for CLI usage
    from ..storage.database import get_database

    db = get_database(f"{args.cache_dir}/basketball.db")
    scraper = NBN23Scraper(
        headless=args.headless,
        cache_dir=args.cache_dir,
        database=db
    )

    result = scraper.scrape()

    print("\n=== Summary ===")
    print(f"Seasons: {result['seasons']}")
    print(f"Groups: {result['groups']}")
    print(f"Matches: {result['matches']}")
    print(f"Time: {result['elapsed']:.1f}s")

    print("\n=== Database Stats ===")
    print(db.get_cache_info())
