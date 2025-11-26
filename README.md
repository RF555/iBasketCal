# Israeli Basketball Calendar

A web application that provides subscribable ICS calendars for Israeli basketball games. Subscribe once and your calendar automatically updates with game schedules, scores, and venue information.

## Features

- **Subscribable Calendars** - Add to Google Calendar, Apple Calendar, Outlook, or any calendar app
- **Auto-Updates** - Calendars refresh automatically with new games and scores
- **Hebrew Support** - Full Hebrew text support for team names and venues
- **Flexible Filtering** - Filter by season, league, and team with cascading dropdowns
- **Game Details** - Includes venues, final scores, and competition info
- **Web Interface** - Easy-to-use Hebrew RTL interface for generating calendar URLs

## How It Works

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Playwright Scraper │────▶│   Local Cache    │────▶│   FastAPI App   │
│  (Background Job)   │     │   (JSON/SQLite)  │     │   (ICS Server)  │
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
4. Cache the data locally (23,000+ matches across 283 competition groups)
5. Serve ICS calendars from cached data

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
| `GET /api/cache-info` | Cache status |
| `POST /api/refresh` | Force data refresh |
| `GET /health` | Health check |
| `GET /docs` | API documentation (Swagger) |

### Calendar URL Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `season` | Filter by season ID | `?season=686e1422dd2c672160d5ca4b` |
| `competition` | Filter by competition name | `?competition=ליגת על` |
| `team` | Filter by team name (partial match) | `?team=מכבי` |

### Example Calendar URLs

```
# All games (current season Premier League)
http://localhost:8000/calendar.ics?season=686e1422dd2c672160d5ca4b&competition=ליגת על

# Maccabi Tel Aviv games
http://localhost:8000/calendar.ics?competition=ליגת על&team=מכבי תל אביב

# Women's Premier League
http://localhost:8000/calendar.ics?competition=ליגת על נשים

# National League
http://localhost:8000/calendar.ics?competition=לאומית
```

### Adding to Calendar Apps

#### Google Calendar
1. Open Google Calendar
2. Click the `+` next to "Other calendars"
3. Select "From URL"
4. Paste the calendar URL
5. Click "Add calendar"

#### Apple Calendar
1. Open Calendar app
2. File → New Calendar Subscription
3. Paste the calendar URL
4. Click Subscribe

#### Outlook
1. Open Outlook Calendar
2. Add calendar → From Internet
3. Paste the calendar URL
4. Click Subscribe

## Development

### Project Structure

```
iBasketCal/
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── nbn23_scraper.py       # Playwright-based scraper
│   │   └── scheduler.py           # Background refresh scheduler
│   └── services/
│       ├── __init__.py
│       ├── data_service.py        # Data access layer
│       └── calendar_service.py    # ICS calendar generation
├── static/
│   ├── index.html                 # Hebrew RTL web UI
│   ├── style.css                  # Styling
│   └── app.js                     # Frontend JavaScript
├── cache/                         # Scraped data cache
├── tests/
│   └── __init__.py
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
3. Fetches all seasons, competitions, and calendars
4. Takes approximately 2 minutes to complete
5. Captures 23,000+ matches across 283 competition groups

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

Copy `.env.example` to `.env` and configure:

```env
# Server Settings
PORT=8000
HOST=0.0.0.0

# Scraper Settings
SCRAPER_HEADLESS=true

# Cache Settings (in minutes)
CACHE_TTL_MINUTES=30

# Scheduler Settings (in minutes)
REFRESH_INTERVAL_MINUTES=30
```

## Data Sources

- **ibasketball.co.il** - Official Israeli Basketball Association website
- **NBN23 SWISH Widget** - Embedded widget providing game data

### Available Competitions

The scraper captures data for all Israeli basketball competitions including:
- Premier League (ליגת על)
- National League (לאומית)
- Women's Premier League (ליגת על נשים)
- State Cup (גביע המדינה)
- Youth leagues
- And more...

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

### Calendar Issues

**"Calendar not updating"**
- Calendar apps typically refresh subscribed calendars every few hours.
- Force refresh in your calendar app settings.
- Check `/api/cache-info` to see when data was last updated.

**"Hebrew text not displaying correctly"**
- Ensure your calendar app supports UTF-8.
- The ICS file uses proper encoding for Hebrew text.

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [ibasketball.co.il](https://ibasketball.co.il) - Data source
- [NBN23](https://nbn23.com) - Widget provider
- [Playwright](https://playwright.dev) - Browser automation
- [FastAPI](https://fastapi.tiangolo.com) - Web framework
