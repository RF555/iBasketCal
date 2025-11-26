"""
NBN23 API Scraper using Playwright for token extraction and direct API calls.

Extracts the authorization token by intercepting widget API requests,
then uses the token to directly call all API endpoints for comprehensive data.
"""

from playwright.sync_api import sync_playwright
import requests
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import time


class NBN23Scraper:
    """
    Scrapes Israeli basketball data from the NBN23 API.

    Process:
    1. Load widget page to extract the authorization token
    2. Use token to directly call API endpoints for all data
    3. Cache results locally
    """

    WIDGET_URL = "https://ibasketball.co.il/swish/"
    API_BASE = "https://api.swish.nbn23.com"
    ORIGIN = "https://ibasketball.co.il"

    def __init__(self, headless: bool = True, cache_dir: str = "cache"):
        self.headless = headless
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.token: Optional[str] = None
        self.session: Optional[requests.Session] = None

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
                # Use headless="new" for better headless compatibility
                # Add args to make headless mode less detectable
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
                # Create context with realistic browser settings
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

                # Intercept API requests to capture the auth token
                page.route("**/api.swish.nbn23.com/**", handle_route)

                try:
                    print(f"[*] Loading {self.WIDGET_URL}...")
                    page.goto(self.WIDGET_URL, wait_until='domcontentloaded', timeout=45000)
                    # Wait for widget to initialize and make API calls
                    print("[*] Waiting for widget to initialize...")
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

    def _init_session(self):
        """Initialize HTTP session with auth headers."""
        if not self.token:
            self._extract_token()

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": self.token,
            "Origin": self.ORIGIN,
            "Accept": "application/json"
        })

    def _api_request(self, endpoint: str, params: dict = None) -> dict:
        """
        Make authenticated API request.

        Args:
            endpoint: API endpoint (e.g., 'seasons', 'competitions')
            params: Query parameters

        Returns:
            JSON response data
        """
        if not self.session:
            self._init_session()

        url = f"{self.API_BASE}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"[!] API request failed for {endpoint}: {e}")
            return {} if endpoint in ['calendar', 'standings'] else []

    def scrape(self, interact: bool = True) -> dict:
        """
        Main scraping method. Fetches all data via direct API calls.

        Args:
            interact: Ignored (kept for backward compatibility)

        Returns:
            Organized data dictionary with seasons, competitions, calendars, standings

        Raises:
            RuntimeError: If token extraction fails
        """
        print(f"[*] Starting scrape at {datetime.now()}")
        start_time = time.time()

        # Step 1: Extract token - let the error propagate so caller knows it failed
        self._extract_token()

        # Step 2: Initialize session
        self._init_session()

        # Step 3: Fetch seasons
        print("[*] Fetching seasons...")
        seasons = self._api_request("seasons")
        print(f"[+] Found {len(seasons)} seasons")

        # Step 4: Fetch competitions for each season
        print("[*] Fetching competitions...")
        competitions = {}
        for season in seasons:
            season_id = season.get('_id')
            if season_id:
                comps = self._api_request("competitions", {"seasonId": season_id})
                competitions[season_id] = comps
                print(f"  [+] Season {season.get('name', season_id)}: {len(comps)} competitions")

        # Step 5: Collect all group IDs
        all_groups = []
        for season_id, comps in competitions.items():
            for comp in comps:
                for group in comp.get('groups', []):
                    group_id = group.get('id')
                    if group_id:
                        all_groups.append({
                            'id': group_id,
                            'season_id': season_id,
                            'competition_name': comp.get('name', ''),
                            'group_name': group.get('name', '')
                        })

        print(f"[*] Found {len(all_groups)} total groups across all seasons")

        # Step 6: Fetch calendars and standings for groups
        # Focus on current season (first one) to avoid too many requests
        current_season_id = seasons[0]['_id'] if seasons else None
        current_season_groups = [g for g in all_groups if g['season_id'] == current_season_id]

        print(f"[*] Fetching calendars for {len(current_season_groups)} groups in current season...")
        calendars = {}
        standings = {}

        for i, group_info in enumerate(current_season_groups):
            group_id = group_info['id']
            comp_name = group_info['competition_name']

            # Progress indicator
            if (i + 1) % 10 == 0 or i == 0:
                print(f"  [*] Processing group {i + 1}/{len(current_season_groups)}...")

            # Fetch calendar
            calendar = self._api_request("calendar", {"groupId": group_id})
            if calendar:
                calendars[group_id] = calendar
                # Count matches
                match_count = sum(
                    len(r.get('matches', []))
                    for r in calendar.get('rounds', [])
                )
                if match_count > 0:
                    print(f"  [+] {comp_name}: {match_count} matches")

            # Fetch standings
            standing = self._api_request("standings", {"groupId": group_id})
            if standing:
                standings[group_id] = standing

            # Small delay to be nice to the API
            time.sleep(0.1)

        # Build final data structure
        data = {
            'seasons': seasons,
            'competitions': competitions,
            'calendars': calendars,
            'standings': standings,
            'scraped_at': datetime.now(timezone.utc).isoformat()
        }

        # Save to cache
        self._save_cache(data)

        elapsed = time.time() - start_time
        print(f"[*] Scrape complete in {elapsed:.1f}s")
        print(f"    Seasons: {len(seasons)}")
        print(f"    Competitions: {sum(len(c) for c in competitions.values())}")
        print(f"    Calendars: {len(calendars)}")
        print(f"    Standings: {len(standings)}")

        return data

    def _save_cache(self, data: dict) -> None:
        """Save scraped data to cache file."""
        cache_file = self.cache_dir / 'nbn23_data.json'
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[*] Cache saved to {cache_file}")

    def load_cache(self) -> Optional[dict]:
        """Load data from cache."""
        cache_file = self.cache_dir / 'nbn23_data.json'
        if not cache_file.exists():
            return None

        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _empty_data(self) -> dict:
        """Return empty data structure."""
        return {
            'seasons': [],
            'competitions': {},
            'calendars': {},
            'standings': {},
            'scraped_at': datetime.now(timezone.utc).isoformat()
        }


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

    scraper = NBN23Scraper(headless=args.headless, cache_dir=args.cache_dir)
    data = scraper.scrape()

    print("\n=== Summary ===")
    print(f"Seasons: {len(data.get('seasons', []))}")
    print(f"Competition sets: {len(data.get('competitions', {}))}")
    print(f"Calendars: {len(data.get('calendars', {}))}")
    print(f"Standings: {len(data.get('standings', {}))}")
