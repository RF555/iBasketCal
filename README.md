# Israeli Basketball Calendar (iBasketCal)

A web application that provides subscribable ICS calendars for Israeli basketball games. Subscribe to your favorite teams and competitions directly in Google Calendar, Apple Calendar, Outlook, or any calendar app that supports ICS feeds.

## Features

- **Subscribable Calendars** - Generate ICS feeds via URL that auto-update
- **Flexible Filtering** - Filter by season, competition, team, date range, and match status
- **Hebrew Support** - Full RTL and Hebrew text support
- **Fast** - In-memory caching minimizes API latency
- **Mobile-Friendly** - Responsive web interface
- **Docker Ready** - Easy deployment with Docker

## Quick Start

### Prerequisites

- Python 3.11+
- NBN23 API key (contact ibasketball.co.il)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ibasketcal.git
cd ibasketcal
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env and add your NBN23_API_KEY
```

4. Run the application:
```bash
uvicorn src.main:app --reload
```

5. Open http://localhost:8000 in your browser

### Using Docker

```bash
# Build and run
docker-compose up -d

# Or build manually
docker build -t ibasketcal .
docker run -p 8000:8000 -e NBN23_API_KEY=your-key ibasketcal
```

## Usage

### Web Interface

1. Visit the web app at http://localhost:8000
2. Select a season from the dropdown
3. (Optional) Filter by competition checkboxes
4. (Optional) Enter a team name to filter
5. Select date range (7/14/30/90 days or all)
6. Choose match status (all, upcoming, or finished)
7. Click "Generate Calendar URL"
8. Copy the URL or click "Add to Google Calendar"

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Web UI for calendar configuration |
| `GET /api/seasons` | List all available seasons |
| `GET /api/competitions/{season_id}` | List competitions for a season |
| `GET /api/teams/{season_id}` | List all teams in a season |
| `GET /calendar.ics` | Generate ICS calendar feed |
| `GET /health` | Health check endpoint |

### Calendar URL Parameters

```
GET /calendar.ics?season=2025/2026&competition=ליגת על&team=מכבי&days=30&status=upcoming
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `season` | Season name (e.g., "2025/2026") | Current season |
| `competition` | Filter by competition name (partial match) | All |
| `team` | Filter by team name (partial match) | All |
| `days` | Include games within N days | All |
| `status` | "all", "upcoming", or "finished" | "all" |

### Example URLs

- All games for current season:
  ```
  /calendar.ics
  ```

- Maccabi Tel Aviv games for next 30 days:
  ```
  /calendar.ics?team=מכבי תל אביב&days=30&status=upcoming
  ```

- Super League finished games:
  ```
  /calendar.ics?competition=ליגת על&status=finished
  ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | 8000 |
| `HOST` | Server host | 0.0.0.0 |
| `NBN23_API_KEY` | API key for NBN23 (required) | - |
| `NBN23_PROJECT_KEY` | Project key for NBN23 | ibba |
| `CACHE_SEASONS_TTL` | Cache TTL for seasons (seconds) | 3600 |
| `CACHE_COMPETITIONS_TTL` | Cache TTL for competitions | 1800 |
| `CACHE_CALENDAR_TTL` | Cache TTL for calendar data | 900 |
| `LOG_LEVEL` | Logging level | INFO |
| `CORS_ORIGINS` | Allowed CORS origins | * |

## Project Structure

```
ibasketcal/
├── src/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── api/
│   │   ├── routes.py        # API endpoints
│   │   └── dependencies.py  # DI dependencies
│   ├── clients/
│   │   └── nbn23.py         # NBN23 API client
│   ├── models/
│   │   ├── match.py         # Match, Team, Score models
│   │   ├── competition.py   # Competition model
│   │   └── season.py        # Season model
│   ├── services/
│   │   ├── calendar.py      # ICS generation
│   │   └── cache.py         # Caching service
│   └── utils/
│       └── ics.py           # ICS format utilities
├── static/
│   ├── index.html           # Web UI
│   ├── style.css            # Styles
│   └── app.js               # Frontend JS
├── tests/                   # Test files
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_calendar.py -v
```

### Code Quality

```bash
# Format code
black src tests

# Lint
ruff check src tests

# Type check
mypy src
```

## Data Source

This application uses the NBN23 SWISH API to fetch basketball data from ibasketball.co.il (Israeli Basketball Association). The API provides:

- Season information
- Competition/league data
- Match schedules and results
- Team information
- Standings

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Data provided by [Israeli Basketball Association](https://ibasketball.co.il)
- Powered by [NBN23 SWISH API](https://nbn23.com)
