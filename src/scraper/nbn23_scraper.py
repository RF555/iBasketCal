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
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Union, Dict, List, Any, TYPE_CHECKING
import time

if TYPE_CHECKING:
    from ..storage.base import DatabaseInterface


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

    # How long to wait for the widget to issue its first API call after the
    # simulated interaction, and how often to check.
    INTERACTION_TIMEOUT_MS = 20000
    POLL_INTERVAL_MS = 500

    # Backoff applied when the API answers 429; doubles on each attempt.
    RATE_LIMIT_MAX_RETRIES = 4
    RATE_LIMIT_BACKOFF_SECONDS = 2.0

    # Pause between per-group requests to stay under the API rate limit.
    REQUEST_DELAY_SECONDS = 0.25

    def __init__(
        self,
        headless: bool = True,
        cache_dir: str = "cache",
        database: Optional["DatabaseInterface"] = None
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

                    # The host defers the widget script with LiteSpeed Cache
                    # (type="litespeed/javascript" + data-src). LiteSpeed only
                    # swaps in the real <script> after a genuine user
                    # interaction, so without this the widget never boots and
                    # no API request is ever made.
                    self._wake_deferred_scripts(page, lambda: token)

                    # Fall back to the widget's static apiKey, which the page
                    # embeds inline in its swish_widget_app.init(...) call.
                    if not token:
                        token = self._token_from_page_source(page)
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

    def _wake_deferred_scripts(self, page, get_token):
        """
        Simulate user interaction so LiteSpeed Cache loads the deferred widget
        script, then poll until the widget issues its first API request.

        Args:
            page: Playwright page already navigated to the widget URL
            get_token: Callable returning the token captured so far (or None)

        Returns:
            The captured token, or None if the widget never called the API.
        """
        print("[*] Simulating user interaction to load deferred widget...")
        page.mouse.move(400, 400)
        page.mouse.move(650, 520)
        page.mouse.wheel(0, 600)
        try:
            page.keyboard.press('ArrowDown')
        except Exception:
            pass  # Keyboard input is best-effort; mouse events usually suffice.

        # Poll instead of sleeping a fixed interval so a fast widget returns
        # quickly and a slow one still gets the full budget.
        waited = 0
        while waited < self.INTERACTION_TIMEOUT_MS:
            token = get_token()
            if token:
                return token
            page.wait_for_timeout(self.POLL_INTERVAL_MS)
            waited += self.POLL_INTERVAL_MS

        return get_token()

    def _token_from_page_source(self, page) -> Optional[str]:
        """
        Read the widget's API key straight from the page HTML.

        The page bootstraps the widget with an inline
        swish_widget_app.init({apiKey:"..."}) call, and that key is what the
        widget sends as its Authorization header. Used as a fallback when the
        widget fails to boot and issue a request of its own.

        Returns:
            The API key, or None if it is not present in the page.
        """
        try:
            html = page.content()
        except Exception as e:
            print(f"[!] Could not read page content: {e}")
            return None

        match = re.search(r"""apiKey\s*:\s*["']([^"']+)["']""", html)
        if match:
            key = match.group(1)
            print(f"[+] Token recovered from page source: {key[:20]}...")
            return key

        print("[!] No apiKey found in page source")
        return None

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

            # Back off and retry when rate limited, otherwise the caller gets
            # an empty result and the data for that group is silently lost.
            if response.status_code == 429:
                for attempt in range(self.RATE_LIMIT_MAX_RETRIES):
                    delay = self.RATE_LIMIT_BACKOFF_SECONDS * (2 ** attempt)
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            delay = max(delay, float(retry_after))
                        except ValueError:
                            pass
                    print(f"[!] Rate limited on {endpoint}, waiting {delay:.1f}s "
                          f"(attempt {attempt + 1}/{self.RATE_LIMIT_MAX_RETRIES})...")
                    time.sleep(delay)

                    response = self.session.get(url, params=params, timeout=30)
                    if response.status_code != 429:
                        break

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            print(f"[!] API request failed for {endpoint}: {e}")
            # Return empty structure based on expected type
            return {} if endpoint in ['calendar', 'standings'] else []

    def scrape(self) -> Dict[str, Any]:
        """
        Main scraping method. Fetches data and saves to SQLite.
        Optimized to only process active or recent seasons.

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

        # FILTER: Define "recent" as ended less than 45 days ago
        # This allows catching up on final games/playoffs of a just-finished season
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=45)
        
        active_seasons = []
        for season in seasons:
            end_date_str = season.get('endDate')
            
            # Always include if no end date (assumed ongoing)
            if not end_date_str:
                active_seasons.append(season)
                continue

            try:
                # Handle ISO format dates (e.g., "2024-06-30T23:59:59.000Z")
                normalized_end_date_str = end_date_str.replace('Z', '+00:00')
                end_date = datetime.fromisoformat(normalized_end_date_str)

                if end_date > cutoff_date:
                    active_seasons.append(season)
                else:
                    print(f"    [-] Skipping season '{season.get('name')}' (ended {end_date_str})")
            except ValueError:
                print(f"    [!] Could not parse date '{end_date_str}', including season {season.get('name')}")
                active_seasons.append(season)

        print(f"    [*] filtered to {len(active_seasons)} active/recent seasons (out of {len(seasons)})")

        # Step 3: Fetch and save competitions ONLY for active seasons
        all_groups = []
        for season in active_seasons:
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

        print(f"    [+] Found {len(all_groups)} total groups for the seasons")

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
            time.sleep(self.REQUEST_DELAY_SECONDS)

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
    from ..storage import get_database

    db = get_database()
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
