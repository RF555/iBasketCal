# Israeli Basketball Calendar

A web application that provides subscribable ICS calendars for Israeli basketball games. Subscribe once and your calendar automatically updates with game schedules, scores, and venue information.

## Features

- **Subscribable Calendars** - Add to Google Calendar, Apple Calendar, Outlook, or any calendar app
- **Auto-Updates** - Calendars refresh automatically with new games and scores
- **Bilingual Interface** - Full English and Hebrew support with language auto-detection (English default)
- **Flexible Filtering** - Filter by season, league, and team with cascading dropdowns
- **Game Details** - Includes venues, final scores, and competition info
- **RTL/LTR Support** - Automatic direction switching based on selected language
- **Robust Error Handling** - Request timeouts, rate limiting feedback, and graceful error recovery
- **RFC 5545 Compliant** - ICS calendars with proper line folding for Hebrew text compatibility

## How It Works

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Playwright Scraper │────▶│  SQLite Database │────▶│   FastAPI App   │
│  (Token Extraction) │     │  (Indexed Cache) │     │   (ICS Server)  │
└─────────────────────┘     └──────────────────┘     └─────────────────┘
         │                                                    │
         ▼                                                    ▼
┌─────────────────────┐                           ┌─────────────────────┐
│ ibasketball.co.il   │                           │   Calendar Apps     │
│ (NBN23 Widget)      │                           │ (Google, Apple, etc)│
└─────────────────────┘                           └─────────────────────┘
```

The NBN23 API requires browser-based authentication, so we use Playwright to:
1. Load the ibasketball.co.il widget page
2. Intercept API requests to capture the authorization token
3. Use the token to directly call the API for all seasons, competitions, and calendars
4. Store data in SQLite database with indexed queries (108,000+ matches across 1,500+ groups)
5. Serve ICS calendars with fast filtered queries

## Quick Start

### Prerequisites

- Python 3.11+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/iBasketCal.git
cd iBasketCal

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Run setup (installs dependencies + Playwright browser)
python setup.py
```

### Running the Application

```bash
# Start the web server
uvicorn src.main:app --reload

# Open in browser
# http://localhost:8000
```

### Running with Docker

```bash
# Build and run
docker-compose up -d

# Access at http://localhost:8000
```

## Usage

### Web Interface

1. Open http://localhost:8000 in your browser
2. Select a season from the dropdown
3. Select a league (sorted alphabetically)
4. Optionally select a specific team
5. Copy the generated calendar URL
6. Add to your calendar app using "Subscribe to calendar" or "Add by URL"

The preview shows all matches for the season with dates, scores, and venue addresses.

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Web interface |
| `GET /calendar.ics` | ICS calendar feed |
| `GET /api/seasons` | List all seasons |
| `GET /api/competitions` | List all competitions |
| `GET /api/competitions/{season_id}` | Competitions for a season |
| `GET /api/matches` | List matches with filters |
| `GET /api/teams` | List all teams |
| `GET /api/cache-info` | Cache status (includes database size, scraping state) |
| `POST /api/refresh` | Force data refresh (rate limited: 5 min cooldown) |
| `GET /api/refresh-status` | Check refresh progress and errors |
| `GET /health` | Health check with database stats |
| `GET /docs` | API documentation (Swagger) |

### Calendar URL Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `season` | Filter by season ID | `?season=686e1422dd2c672160d5ca4b` |
| `competition` | Filter by competition name (partial match) | `?competition=Premier` |
| `team` | Filter by team name (partial match) | `?team=Maccabi` |

> **Note:** Competition and team names in the API are in Hebrew. Use partial matches (e.g., "Maccabi" matches teams containing that text) or copy the exact Hebrew names from the web interface.

### Example Calendar URLs

```
# All games (current season Premier League)
http://localhost:8000/calendar.ics?season=686e1422dd2c672160d5ca4b&competition=Premier

# Maccabi Tel Aviv games
http://localhost:8000/calendar.ics?competition=Premier&team=Maccabi

# Women's Premier League
http://localhost:8000/calendar.ics?competition=Women

# National League
http://localhost:8000/calendar.ics?competition=National
```

### Adding to Calendar Apps

The web interface provides one-click subscription buttons for all major calendar platforms:

#### Google Calendar

**Option 1: Use the "Add to Google Calendar" button** (recommended)
- Click the "Add to Google Calendar" button in the web interface
- Google Calendar will open with the subscription pre-configured

**Option 2: Manual subscription**
1. Open Google Calendar
2. Click the `+` next to "Other calendars"
3. Select "From URL"
4. Paste the calendar URL
5. Click "Add calendar"

#### Apple Calendar

**Option 1: Use the "Add to Apple Calendar" button** (recommended)
- Click the "Add to Apple Calendar" button in the web interface
- Calendar app will open with a subscription prompt
- Works on macOS, iPhone, and iPad

**Option 2: Manual subscription**
1. Open Calendar app
2. File → New Calendar Subscription (macOS) or Settings → Calendar → Accounts → Add Subscribed Calendar (iOS)
3. Paste the calendar URL
4. Click Subscribe

> **Note:** For iCloud sync across devices, subscribe on Mac and select "iCloud" as the location.

#### Microsoft Outlook

**Option 1: Use the "Add to Outlook" dropdown** (recommended)
- Click the "Add to Outlook" button in the web interface
- Select either:
  - **Outlook 365 (Work/School)** - for Office 365 accounts
  - **Outlook.com (Personal)** - for personal Microsoft accounts
- Outlook web will open with the subscription pre-configured

**Option 2: Manual subscription**
1. Open Outlook Calendar (web or desktop)
2. Add calendar → From Internet / Subscribe from web
3. Paste the calendar URL
4. Click Subscribe

> **Note:** Calendar updates may take up to 24 hours to sync, depending on your calendar app's refresh settings.

## Development

### Project Structure

```
iBasketCal/
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Configuration (env vars)
│   ├── types.py                   # TypedDict definitions
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── nbn23_scraper.py       # Playwright-based scraper
│   │   └── scheduler.py           # Background refresh scheduler
│   ├── services/
│   │   ├── __init__.py
│   │   ├── data_service.py        # Data access layer
│   │   └── calendar_service.py    # ICS calendar generation
│   └── storage/
│       ├── __init__.py            # Database interface exports
│       ├── base.py                # Abstract DatabaseInterface
│       ├── factory.py             # Database factory (singleton)
│       ├── exceptions.py          # Custom storage exceptions
│       ├── sqlite_db.py           # SQLite implementation (default)
│       ├── turso_db.py            # Turso cloud implementation
│       └── supabase_db.py         # Supabase implementation
├── static/
│   ├── index.html                 # Bilingual web UI (English default)
│   ├── style.css                  # Styling with RTL/LTR support
│   ├── app.js                     # Frontend JavaScript
│   └── i18n/                      # Internationalization
│       ├── i18n-config.js         # i18next configuration (English fallback)
│       └── locales/
│           ├── en.json            # English translations (default)
│           └── he.json            # Hebrew translations
├── cache/                         # SQLite database storage
│   └── basketball.db              # Main database file
├── scripts/
│   └── supabase_schema.sql        # Supabase migration script
├── tests/
│   ├── __init__.py
│   └── test_storage.py            # Storage layer tests
├── Dockerfile
├── docker-compose.yml
├── setup.py                       # Setup script
├── requirements.txt
├── .env.example
├── CLAUDE.md                      # Development documentation
└── README.md
```

### Manual Scraper Run

```bash
# Run scraper with visible browser (for debugging)
python -m src.scraper.nbn23_scraper --no-headless

# Run scraper in headless mode
python -m src.scraper.nbn23_scraper
```

The scraper:
1. Loads the widget page to capture the API authorization token
2. Uses the token to directly call the NBN23 API
3. Fetches all seasons, competitions, and calendars (4 seasons of historical data)
4. Stores data in SQLite database with indexed queries
5. Takes approximately 7-8 minutes to complete full scrape
6. Captures 108,000+ matches across 1,500+ competition groups

### Background Scheduler

For production, run the background scheduler to keep data fresh:

```bash
python -m src.scraper.scheduler
```

This refreshes data every 30 minutes.

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
# Format code
black src/

# Lint
ruff check src/
```

## Configuration

Configuration is managed via environment variables with sensible defaults. The configuration module is at `src/config.py`.

Copy `.env.example` to `.env` to customize:

```env
# Server Settings
PORT=8000
HOST=0.0.0.0

# Data Directory (for persistent storage)
# Used by Railway/container deployments to specify volume mount path
DATA_DIR=/data

# Scraper Settings
SCRAPER_HEADLESS=true
WIDGET_URL=https://ibasketball.co.il/swish/

# Cache Settings
# How long before cache is considered stale (in minutes)
# Default: 7 days (10080 minutes)
CACHE_TTL_MINUTES=10080

# Rate Limiting
# Cooldown between manual refresh requests (in seconds)
# Default: 5 minutes (300 seconds)
REFRESH_COOLDOWN_SECONDS=300

# Logging
LOG_LEVEL=INFO
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `8000` |
| `HOST` | Server host | `0.0.0.0` |
| `DB_TYPE` | Database backend (`sqlite`, `turso`, `supabase`) | `sqlite` |
| `DATA_DIR` | Directory for SQLite database | `cache/` (local) or `/app/cache` (container) |
| `RAILWAY_VOLUME_MOUNT_PATH` | Auto-set by Railway for volume mount | - |
| `SCRAPER_HEADLESS` | Run browser in headless mode | `true` |
| `WIDGET_URL` | NBN23 widget URL for token extraction | `https://ibasketball.co.il/swish/` |
| `CACHE_TTL_MINUTES` | Cache time-to-live before considered stale | `10080` (7 days) |
| `REFRESH_COOLDOWN_SECONDS` | Rate limit cooldown for manual refresh | `300` (5 minutes) |
| `LOG_LEVEL` | Logging level | `INFO` |

### Railway Deployment

For Railway deployment with persistent storage:

1. **Add a volume** in Railway dashboard
2. **Set mount path** to `/data`
3. **Set environment variable**: `DATA_DIR=/data`

The app automatically uses the volume for SQLite database storage, ensuring data persists across deployments.

**Important Docker Note:** Playwright browsers must be installed as the runtime user, not as root. The Dockerfile installs browsers after switching to `appuser` to ensure they're accessible at runtime.

### Render + Supabase Deployment (Recommended for Cloud)

Deploy to Render using Supabase as the database backend. This eliminates the need for persistent disk storage.

#### Step 1: Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Note your **Project URL** and **anon key** (Settings → API)
3. Run `scripts/supabase_schema.sql` in the SQL Editor

#### Step 2: Deploy to Render

1. Go to [render.com](https://render.com) and connect your GitHub repo
2. Render will auto-detect `render.yaml`
3. Set these environment variables in Render dashboard:

```env
DB_TYPE=supabase
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_KEY=your-anon-key
PORT=8000
SCRAPER_HEADLESS=true
CACHE_TTL_MINUTES=10080
REFRESH_COOLDOWN_SECONDS=300
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
```

4. Click **Create Web Service**

#### Step 3: Initial Data Load

After deployment, visit your app URL - it will auto-detect the empty database and start scraping (~2-3 minutes).

#### Cost

| Service | Plan | Monthly Cost |
|---------|------|--------------|
| Render | Starter | $7 |
| Render | Free (spins down) | $0 |
| Supabase | Free (500MB) | $0 |

For detailed instructions, see `.claude/markdowns/RENDER_SUPABASE_DEPLOYMENT.md`.

## Database Configuration

iBasketCal supports multiple database backends. Set the `DB_TYPE` environment variable to choose:

### SQLite (Default)

Local file-based database, perfect for development and self-hosted deployments. No additional setup required.

```env
DB_TYPE=sqlite
DATA_DIR=cache  # Optional, defaults to cache/
```

### Turso

Free cloud-hosted SQLite-compatible edge database. Great for serverless deployments.

1. Create account at https://turso.tech
2. Create database: `turso db create ibasketcal`
3. Get URL: `turso db show ibasketcal --url`
4. Get token: `turso db tokens create ibasketcal`

```env
DB_TYPE=turso
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your-token
```

Install the driver: `pip install libsql-experimental`

### Supabase

PostgreSQL-based cloud database with generous free tier.

1. Create account at https://supabase.com
2. Create new project
3. Run `scripts/supabase_schema.sql` in SQL Editor
4. Get URL and anon key from project settings

```env
DB_TYPE=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

Install the driver: `pip install supabase`

**Note:** For Supabase, you must run the schema migration in `scripts/supabase_schema.sql` before starting the application.

## Data Sources

- **ibasketball.co.il** - Official Israeli Basketball Association website
- **NBN23 SWISH Widget** - Embedded widget providing game data

### Available Competitions

The scraper captures data for all Israeli basketball competitions including:
- Premier League (ליגת על / Liga Leumit)
- National League (לאומית / Leumit)
- Women's Premier League (ליגת על נשים)
- State Cup (גביע המדינה)
- Youth leagues
- And more...

> **Note:** Competition names are stored in Hebrew in the database. Use partial English matches or the exact Hebrew names when filtering.

### Known Season IDs

| Season | ID |
|--------|-----|
| 2025/2026 | `686e1422dd2c672160d5ca4b` |
| 2024/2025 | `668ba5c2ceb8a7aa70c41ae2` |
| 2023/2024 | `648068e5f237bcc9c859a66a` |
| 2022/2023 | `61ee7ed011e06ff312049ae1` |

## Troubleshooting

### Scraper Issues

**"No data captured"**
- The widget page may have changed. Try running with `--no-headless` to see what's happening.
- Check your internet connection.

**"Playwright browser not found"**
- Run `playwright install chromium` to install the browser.
- In Docker, ensure browsers are installed as the runtime user (after `USER` directive), not as root.

**"Token expired (401)"**
- The scraper automatically retries with a fresh token when this happens.
- If persistent, the widget page authentication may have changed.

### Database Issues

**"Database not found"**
- Run the scraper to populate the database: `python -m src.scraper.nbn23_scraper`
- Check that `cache/basketball.db` exists.

**"Database locked"**
- SQLite uses WAL mode for concurrent access, but heavy writes may cause brief locks.
- Restart the application if issues persist.

### Calendar Issues

**"Calendar not updating"**
- Calendar apps typically refresh subscribed calendars every few hours.
- Force refresh in your calendar app settings.
- Check `/health` endpoint to see database stats and last update time.

**"Hebrew text not displaying correctly"**
- Ensure your calendar app supports UTF-8.
- The ICS file uses proper encoding for Hebrew text.

**"Scores appear swapped in RTL mode"**
- This was a known issue with bidirectional text rendering where scores (LTR numbers) appeared reversed in RTL Hebrew context.
- Fixed by using Unicode LTR marks (`\u200E`) around score displays to ensure correct ordering.

## Technical Details

### Storage Architecture
- **Multi-Database Support** - Pluggable backend via `DatabaseInterface` abstract class
- **SQLite (Default)** - Efficient indexed storage (~180MB for all data), WAL mode for concurrency
- **Turso** - Cloud SQLite-compatible edge database for serverless deployments
- **Supabase** - PostgreSQL cloud database with REST API
- **Factory Pattern** - Singleton instance created based on `DB_TYPE` environment variable
- **Cache TTL** - Data considered fresh for 7 days (configurable via `CACHE_TTL_MINUTES`)

### Data
- ~108,000 matches across all seasons
- ~1,500 competition groups
- Full history from 2022/2023 season
- 4 seasons of data

### Performance
- Indexed queries for fast filtering by season, competition, and team
- Rate limiting on refresh endpoint (5-minute cooldown)
- Frontend request timeouts (30 seconds)

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [ibasketball.co.il](https://ibasketball.co.il) - Data source
- [NBN23](https://nbn23.com) - Widget provider
- [Playwright](https://playwright.dev) - Browser automation
- [FastAPI](https://fastapi.tiangolo.com) - Web framework
