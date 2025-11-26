# NBN23 Widget Scraping Research
## Complete Analysis for Israeli Basketball Calendar Project

---

## The Problem

The NBN23 SWISH API at `https://api.swish.nbn23.com` requires authentication that is tied to the widget's origin. When we call the API directly without the proper context (without being embedded in the ibasketball.co.il website), the requests fail.

The API appears to validate:
1. The `Origin` header must match an authorized domain
2. The `apiKey` parameter in widget initialization
3. Possibly additional CORS or token-based authentication

---

## Solution: Browser-Based Scraping with Network Interception

The most reliable approach is to use **Playwright** to:
1. Load the actual ibasketball.co.il/swish/ page in a real browser
2. Intercept the API calls the widget makes
3. Extract the JSON data from the responses
4. Cache the data locally for our calendar generation

This works because:
- The widget runs in a legitimate browser context
- The browser handles all authentication automatically
- We capture the raw API responses before they're processed by React

---

## Technical Implementation

### Approach 1: Network Response Interception (Recommended)

```python
from playwright.sync_api import sync_playwright
import json

def scrape_nbn23_data():
    """Intercept NBN23 API responses from the widget page"""
    
    captured_data = {
        'seasons': [],
        'competitions': [],
        'calendars': [],
        'standings': []
    }
    
    def handle_response(response):
        """Capture API responses"""
        url = response.url
        
        if 'api.swish.nbn23.com' not in url:
            return
            
        try:
            if response.status == 200:
                data = response.json()
                
                if '/seasons' in url:
                    captured_data['seasons'] = data
                    print(f"✓ Captured seasons: {len(data)} items")
                    
                elif '/competitions' in url:
                    captured_data['competitions'].append({
                        'url': url,
                        'data': data
                    })
                    print(f"✓ Captured competitions: {len(data)} items")
                    
                elif '/calendar' in url:
                    captured_data['calendars'].append({
                        'url': url,
                        'data': data
                    })
                    print(f"✓ Captured calendar data")
                    
                elif '/standings' in url:
                    captured_data['standings'].append({
                        'url': url,
                        'data': data
                    })
                    print(f"✓ Captured standings")
                    
        except Exception as e:
            print(f"Error parsing response from {url}: {e}")
    
    with sync_playwright() as p:
        # Launch browser (use headless=True for production)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            locale='he-IL',
            timezone_id='Asia/Jerusalem'
        )
        page = context.new_page()
        
        # Set up response interception BEFORE navigation
        page.on('response', handle_response)
        
        # Navigate to the widget page
        print("Loading ibasketball.co.il/swish/...")
        page.goto('https://ibasketball.co.il/swish/', wait_until='networkidle')
        
        # Wait for widget to fully load
        page.wait_for_timeout(3000)
        
        # Interact with the widget to trigger more API calls
        # Click on different competitions, dates, etc.
        
        # Example: Click on various elements to load more data
        # This needs to be customized based on widget structure
        
        browser.close()
    
    return captured_data


if __name__ == '__main__':
    data = scrape_nbn23_data()
    
    # Save to file
    with open('nbn23_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\nData saved to nbn23_data.json")
```

### Approach 2: Full Widget Interaction Scraping

```python
from playwright.sync_api import sync_playwright
import json
import time

class NBN23Scraper:
    """Scraper that interacts with the NBN23 widget to collect all data"""
    
    def __init__(self, headless=True):
        self.headless = headless
        self.data = {
            'seasons': [],
            'competitions': {},
            'calendars': {},
            'standings': {},
            'teams': {}
        }
        self.captured_responses = []
    
    def _handle_response(self, response):
        """Intercept and store API responses"""
        if 'api.swish.nbn23.com' not in response.url:
            return
        
        if response.status != 200:
            return
            
        try:
            json_data = response.json()
            self.captured_responses.append({
                'url': response.url,
                'data': json_data,
                'timestamp': time.time()
            })
        except:
            pass
    
    def scrape_all(self):
        """Main scraping routine"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                viewport={'width': 1280, 'height': 900},
                locale='he-IL',
                timezone_id='Asia/Jerusalem'
            )
            page = context.new_page()
            
            # Set up interception
            page.on('response', self._handle_response)
            
            # Load page
            page.goto('https://ibasketball.co.il/swish/')
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)
            
            # Get initial data (seasons, default competitions)
            print("Captured initial page load data")
            
            # Find and click on season selector to get all seasons
            self._scrape_seasons(page)
            
            # For each season, get competitions
            self._scrape_competitions(page)
            
            # For each competition group, get calendar and standings
            self._scrape_calendars_and_standings(page)
            
            browser.close()
        
        return self._process_captured_data()
    
    def _scrape_seasons(self, page):
        """Click on season dropdown to capture season data"""
        # Find season selector - adjust selector based on actual widget HTML
        try:
            # Look for season dropdown
            season_selector = page.query_selector('[data-testid="season-select"]')
            if season_selector:
                season_selector.click()
                page.wait_for_timeout(500)
                
                # Click each season option to trigger API calls
                options = page.query_selector_all('[data-testid="season-option"]')
                for option in options:
                    option.click()
                    page.wait_for_timeout(1000)
        except Exception as e:
            print(f"Season scraping: {e}")
    
    def _scrape_competitions(self, page):
        """Navigate through competitions"""
        try:
            # Find competition list items
            comp_items = page.query_selector_all('.competition-item, [data-competition-id]')
            for item in comp_items:
                item.click()
                page.wait_for_timeout(1000)
        except Exception as e:
            print(f"Competition scraping: {e}")
    
    def _scrape_calendars_and_standings(self, page):
        """Get calendar and standings for each competition"""
        try:
            # Click on calendar tab
            calendar_tab = page.query_selector('[data-tab="calendar"], .calendar-tab')
            if calendar_tab:
                calendar_tab.click()
                page.wait_for_timeout(1000)
            
            # Click on standings tab
            standings_tab = page.query_selector('[data-tab="standings"], .standings-tab')
            if standings_tab:
                standings_tab.click()
                page.wait_for_timeout(1000)
        except Exception as e:
            print(f"Calendar/standings scraping: {e}")
    
    def _process_captured_data(self):
        """Process all captured responses into organized data"""
        for response in self.captured_responses:
            url = response['url']
            data = response['data']
            
            if '/seasons' in url:
                self.data['seasons'] = data
            elif '/competitions' in url:
                # Extract seasonId from URL
                import re
                match = re.search(r'seasonId=([^&]+)', url)
                if match:
                    season_id = match.group(1)
                    self.data['competitions'][season_id] = data
            elif '/calendar' in url:
                match = re.search(r'groupId=([^&]+)', url)
                if match:
                    group_id = match.group(1)
                    self.data['calendars'][group_id] = data
            elif '/standings' in url:
                match = re.search(r'groupId=([^&]+)', url)
                if match:
                    group_id = match.group(1)
                    self.data['standings'][group_id] = data
        
        return self.data


# Usage
if __name__ == '__main__':
    scraper = NBN23Scraper(headless=False)  # Set True for production
    data = scraper.scrape_all()
    
    with open('basketball_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
```

---

## Key Technical Details

### Widget Structure (from HAR analysis)

The NBN23 widget makes these API calls:

1. **GET /seasons** - Returns all available seasons
2. **GET /competitions?seasonId=X** - Returns competitions for a season
3. **GET /calendar?groupId=X** - Returns matches for a competition group
4. **GET /standings?groupId=X** - Returns standings for a competition group

### Known Season IDs
```
2025/2026: 686e1422dd2c672160d5ca4b
2024/2025: 668ba5c2ceb8a7aa70c41ae2
2023/2024: 648068e5f237bcc9c859a66a
2022/2023: 61ee7ed011e06ff312049ae1
```

### Data Structures

**Match Object:**
```json
{
  "id": "68cc83769569a17980f47dbf",
  "homeTeam": {
    "id": "68cc83769569a17980f47db5",
    "name": "בני יהודה תל אביב",
    "logo": "..."
  },
  "awayTeam": {
    "id": "68cc83769569a17980f47db6",
    "name": "הפועל הוד השרון",
    "logo": "..."
  },
  "date": "2025-10-28T19:00:00.000Z",
  "score": {
    "totals": [
      {"teamId": "...", "total": 66},
      {"teamId": "...", "total": 59}
    ]
  },
  "status": "CLOSED",
  "court": {
    "place": "אולם ספורט...",
    "address": null,
    "town": null
  }
}
```

**Status Values:** `NOT_STARTED`, `LIVE`, `CLOSED`

---

## Implementation Recommendations

### 1. Scheduled Data Collection
- Run the scraper every 15-30 minutes
- Store data in a local database (SQLite) or JSON files
- Serve calendar data from cached local data

### 2. Caching Strategy
```python
import os
import json
from datetime import datetime, timedelta

CACHE_DIR = 'cache'
CACHE_TTL_MINUTES = 15

def get_cached_data(key):
    """Get data from cache if fresh"""
    cache_file = os.path.join(CACHE_DIR, f'{key}.json')
    
    if not os.path.exists(cache_file):
        return None
    
    # Check age
    file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
    if datetime.now() - file_time > timedelta(minutes=CACHE_TTL_MINUTES):
        return None
    
    with open(cache_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_to_cache(key, data):
    """Save data to cache"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f'{key}.json')
    
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
```

### 3. Background Scraper Service
```python
import schedule
import time

def scrape_job():
    """Background job to refresh data"""
    print(f"[{datetime.now()}] Starting data refresh...")
    scraper = NBN23Scraper(headless=True)
    data = scraper.scrape_all()
    save_to_cache('all_data', data)
    print(f"[{datetime.now()}] Data refresh complete")

# Schedule every 15 minutes
schedule.every(15).minutes.do(scrape_job)

# Run initial scrape
scrape_job()

# Keep running
while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## Requirements

```txt
# requirements.txt
playwright>=1.40.0
schedule>=1.2.0
```

Install Playwright browsers:
```bash
pip install playwright
playwright install chromium
```

---

## Alternative Approaches Considered

### ❌ Direct API Access
- Fails due to CORS/Origin validation
- API requires requests to come from authorized widget domains

### ❌ Proxying Through ibasketball.co.il
- Not possible without server access
- Would require modifying their site

### ✅ Browser Automation (Selected)
- Works because browser handles all auth
- Reliable and maintainable
- Can capture all API responses

### ❌ HTML DOM Scraping
- Widget uses React, DOM is complex
- Data not always in DOM (may be in React state)
- Network interception is cleaner

---

## Widget HTML Structure Notes

The NBN23 widget mounts to a div and renders React components:

```html
<div id="nbn23">
  <!-- Widget renders here -->
  <div class="swish-app">
    <div class="header">
      <!-- Season selector -->
    </div>
    <div class="competition-list">
      <!-- Competition items -->
    </div>
    <div class="calendar-view">
      <!-- Match cards -->
    </div>
    <div class="standings-view">
      <!-- Standings table -->
    </div>
  </div>
</div>
```

Key interaction points:
- Season dropdown: Changes which season's data is loaded
- Competition list: Clicking loads that competition's calendar
- Tab navigation: Calendar / Standings / Teams tabs
- Date navigation: Forward/back to load different date ranges

---

## Next Steps for Claude Code

1. **Create scraper module** with Playwright network interception
2. **Build caching layer** to store scraped data
3. **Create FastAPI endpoints** to serve cached data
4. **Generate ICS calendars** from cached match data
5. **Add scheduled background job** to refresh data periodically
6. **Build simple web UI** for calendar URL generation

The web application will:
- NOT call the NBN23 API directly
- Serve data from locally cached JSON
- Run Playwright scraper on a schedule to refresh cache
- Generate ICS feeds dynamically from cached data
