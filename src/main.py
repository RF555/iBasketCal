"""
Israeli Basketball Calendar - FastAPI Application

Provides REST API and ICS calendar endpoints for Israeli basketball games.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Query, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pathlib import Path
import os
import threading

from .services.data_service import DataService
from .services.calendar_service import CalendarService
from . import config

# Ensure cache directory exists
Path(config.CACHE_DIR).mkdir(parents=True, exist_ok=True)
print(f"[*] Using cache directory: {config.CACHE_DIR}")

# Initialize services with configured cache directory
data_service = DataService(cache_dir=config.CACHE_DIR)
calendar_service = CalendarService()


# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    """Simple rate limiter for refresh endpoint."""

    def __init__(self, cooldown_seconds: int = 300):
        """
        Initialize rate limiter.

        Args:
            cooldown_seconds: Minimum seconds between allowed requests (default 5 min)
        """
        self.cooldown_seconds = cooldown_seconds
        self._last_request: Optional[datetime] = None
        self._lock = threading.Lock()

    def try_acquire(self) -> tuple[bool, int]:
        """
        Try to acquire rate limit.

        Returns:
            Tuple of (allowed: bool, wait_seconds: int)
            - If allowed, wait_seconds is 0
            - If not allowed, wait_seconds is how long to wait
        """
        with self._lock:
            now = datetime.now()

            if self._last_request is None:
                self._last_request = now
                return True, 0

            elapsed = (now - self._last_request).total_seconds()

            if elapsed >= self.cooldown_seconds:
                self._last_request = now
                return True, 0

            wait_seconds = int(self.cooldown_seconds - elapsed)
            return False, wait_seconds

    def reset(self) -> None:
        """Reset the rate limiter (for testing)."""
        with self._lock:
            self._last_request = None


# Rate limiter for refresh endpoint
refresh_rate_limiter = RateLimiter(cooldown_seconds=config.REFRESH_COOLDOWN_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: Check cache status
    # - If no cache exists: don't auto-scrape (too memory-intensive for free tier)
    # - If cache is stale: auto-refresh in background (lighter operation)
    print("[*] Checking cache status...")
    cache_info = data_service.get_cache_info()

    if not cache_info['exists']:
        print("[*] No cache found. Run initial scrape locally or via POST /api/refresh")
    elif cache_info['stale']:
        print(f"[*] Cache is stale (last updated: {cache_info['last_updated']})")
        print("[*] Starting background refresh...")
        data_service.refresh_async()
    else:
        print(f"[+] Cache is fresh (last updated: {cache_info['last_updated']})")

    print("[*] App is ready.")

    yield

    print("[*] Shutting down...")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Israeli Basketball Calendar",
    description="Subscribable ICS calendars for Israeli basketball games",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if directory exists
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the main web UI."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return HTMLResponse(
            content="""
            <html>
            <head><title>Israeli Basketball Calendar</title></head>
            <body style="font-family: sans-serif; padding: 40px;">
                <h1>Israeli Basketball Calendar</h1>
                <p>API is running. Static files not found.</p>
                <h2>API Endpoints:</h2>
                <ul>
                    <li><a href="/api/seasons">GET /api/seasons</a> - List seasons</li>
                    <li><a href="/api/competitions">GET /api/competitions</a> - List competitions</li>
                    <li><a href="/api/matches">GET /api/matches</a> - List matches</li>
                    <li><a href="/api/teams">GET /api/teams</a> - List teams</li>
                    <li><a href="/calendar.ics">GET /calendar.ics</a> - ICS calendar feed</li>
                    <li><a href="/api/cache-info">GET /api/cache-info</a> - Cache status</li>
                    <li><a href="/docs">API Documentation</a></li>
                </ul>
            </body>
            </html>
            """,
            status_code=200
        )


@app.get("/api/seasons")
async def get_seasons():
    """Get all available seasons."""
    try:
        seasons = data_service.get_seasons()
        return seasons
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/competitions")
async def get_all_competitions():
    """Get all competitions across all seasons."""
    try:
        competitions = data_service.get_all_competitions()
        return competitions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/competitions/{season_id}")
async def get_competitions(season_id: str):
    """Get competitions for a specific season."""
    try:
        competitions = data_service.get_competitions(season_id)
        return competitions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/matches")
async def get_matches(
    season: Optional[str] = Query(None, description="Season ID"),
    competition: Optional[str] = Query(None, description="Competition name filter"),
    team: Optional[str] = Query(None, description="Team name filter")
):
    """Get matches with optional filters."""
    try:
        matches = data_service.get_all_matches(
            season_id=season,
            competition_name=competition,
            team_name=team
        )
        return matches
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams")
async def get_teams(
    season: Optional[str] = Query(None, description="Season ID"),
    q: Optional[str] = Query(None, description="Search query")
):
    """Get teams with optional search."""
    try:
        if q:
            teams = data_service.search_teams(q, season_id=season)
        else:
            teams = data_service.get_teams(season_id=season)
        return teams
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/calendar.ics")
async def get_calendar(
    season: Optional[str] = Query(None, description="Season ID"),
    competition: Optional[str] = Query(None, description="Competition name filter"),
    team: Optional[str] = Query(None, description="Team name filter"),
    mode: Optional[str] = Query("fan", description="Calendar mode: 'fan' or 'player'"),
    prep: Optional[int] = Query(60, ge=15, le=180, description="Prep time in minutes for player mode (15-180)"),
    tf: Optional[str] = Query("24h", description="Time format in event title: '24h' or '12h'"),
    tz: Optional[str] = Query("Asia/Jerusalem", description="Timezone for displayed times in player mode (IANA format)")
):
    """
    Generate ICS calendar feed with all season games.

    Args:
        season: Filter by season ID
        competition: Filter by competition name
        team: Filter by team name
        mode: 'fan' (default) - events at game time, 'player' - events include prep time
        prep: Prep time in minutes for player mode (15-180, default 60)
        tf: Time format for event title: '24h' (default) or '12h' (AM/PM)
        tz: Timezone for displayed times in player mode (IANA format, default 'Asia/Jerusalem')

    Example URLs:
    - /calendar.ics - All games for the season (fan mode)
    - /calendar.ics?mode=player&prep=60 - Player mode with 60 min prep time
    - /calendar.ics?mode=player&prep=90&tf=12h&tz=America/New_York - Player mode with 12h time format in NY timezone
    """
    try:
        # Validate mode
        if mode not in ('fan', 'player'):
            mode = 'fan'

        # Validate time format
        if tf not in ('24h', '12h'):
            tf = '24h'

        # Get matches with filters
        matches = data_service.get_all_matches(
            season_id=season,
            competition_name=competition,
            team_name=team
        )

        # Generate calendar name
        name_parts = ["Israeli Basketball"]
        if competition:
            name_parts.append(competition)
        if team:
            name_parts.append(team)
        if mode == 'player':
            name_parts.append("Player")
        calendar_name = " - ".join(name_parts)

        # Generate ICS content with mode parameters
        ics_content = calendar_service.generate_ics(
            matches,
            calendar_name,
            player_mode=(mode == 'player'),
            prep_time_minutes=prep if mode == 'player' else 0,
            time_format=tf,
            display_timezone=tz if mode == 'player' else "Asia/Jerusalem"
        )

        return Response(
            content=ics_content,
            media_type="text/calendar; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=basketball.ics",
                "Cache-Control": "public, max-age=900"  # 15 min cache
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cache-info")
async def get_cache_info():
    """Get information about the data cache."""
    try:
        info = data_service.get_cache_info()
        info['is_scraping'] = data_service.is_scraping()
        info['database_size_mb'] = round(
            data_service.db.get_database_size() / (1024 * 1024), 2
        )
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/refresh")
async def refresh_data():
    """
    Start a background refresh of cached data.

    Rate limited to once per 5 minutes to prevent abuse.
    """
    try:
        # Check if already scraping
        if data_service.is_scraping():
            return {
                "status": "in_progress",
                "message": "Refresh already in progress"
            }

        # Check rate limit
        allowed, wait_seconds = refresh_rate_limiter.try_acquire()
        if not allowed:
            return {
                "status": "rate_limited",
                "message": f"Please wait {wait_seconds} seconds before refreshing again",
                "retry_after": wait_seconds
            }

        # Start background refresh
        started = data_service.refresh_async()
        if started:
            return {
                "status": "started",
                "message": "Data refresh started in background. This may take several minutes."
            }
        else:
            return {
                "status": "in_progress",
                "message": "Refresh already in progress"
            }

    except Exception as e:
        print(f"[API] Error in /api/refresh: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/refresh-status")
async def refresh_status():
    """Check if a refresh is currently in progress."""
    return {
        "is_scraping": data_service.is_scraping(),
        "cache": data_service.get_cache_info(),
        "last_error": data_service.get_last_scrape_error()
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    cache_info = data_service.get_cache_info()
    is_scraping = data_service.is_scraping()
    return {
        "status": "ok",
        "is_scraping": is_scraping,
        "cache": cache_info,
        "database_size_mb": round(
            data_service.db.get_database_size() / (1024 * 1024), 2
        )
    }


# Run with: uvicorn src.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
