"""API route definitions."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, HTTPException
from fastapi.responses import JSONResponse

from src.api.dependencies import get_client, get_calendar_service
from src.clients.nbn23 import NBN23Client, MatchFilters
from src.services.calendar import CalendarService
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/api/seasons")
async def list_seasons(
    client: NBN23Client = Depends(get_client),
) -> JSONResponse:
    """List all available seasons.

    Returns:
        List of seasons with id and name
    """
    try:
        seasons = await client.get_seasons()
        return JSONResponse(
            content=[
                {
                    "id": s.id,
                    "name": s.name,
                    "startDate": s.start_date.isoformat(),
                    "endDate": s.end_date.isoformat(),
                    "isCurrent": s.is_current(),
                }
                for s in seasons
            ]
        )
    except Exception as e:
        logger.error(f"Error fetching seasons: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch seasons")


@router.get("/api/competitions/{season_id}")
async def list_competitions(
    season_id: str,
    client: NBN23Client = Depends(get_client),
) -> JSONResponse:
    """List all competitions for a season.

    Args:
        season_id: The season ID

    Returns:
        List of competitions with groups
    """
    try:
        competitions = await client.get_competitions(season_id)
        return JSONResponse(
            content=[
                {
                    "id": c.id,
                    "name": c.name,
                    "groups": [
                        {"id": g.id, "name": g.name, "type": g.type}
                        for g in c.groups
                    ],
                }
                for c in competitions
            ]
        )
    except Exception as e:
        logger.error(f"Error fetching competitions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch competitions")


@router.get("/api/teams/{season_id}")
async def list_teams(
    season_id: str,
    client: NBN23Client = Depends(get_client),
) -> JSONResponse:
    """List all teams for a season.

    Args:
        season_id: The season ID

    Returns:
        List of teams with id, name, and logo
    """
    try:
        teams = await client.get_all_teams(season_id)
        # Sort by name
        teams.sort(key=lambda t: t.name)
        return JSONResponse(
            content=[
                {"id": t.id, "name": t.name, "logo": t.logo}
                for t in teams
            ]
        )
    except Exception as e:
        logger.error(f"Error fetching teams: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch teams")


@router.get("/api/competitions-by-name/{season_name:path}")
async def list_competitions_by_season_name(
    season_name: str,
    client: NBN23Client = Depends(get_client),
) -> JSONResponse:
    """List all competitions for a season by season name.

    Args:
        season_name: The season name (e.g., "2025/2026")

    Returns:
        List of competitions with groups
    """
    try:
        season_id = await client.get_season_id(season_name)
        if not season_id:
            raise HTTPException(status_code=404, detail=f"Season '{season_name}' not found")

        competitions = await client.get_competitions(season_id)
        return JSONResponse(
            content=[
                {
                    "id": c.id,
                    "name": c.name,
                    "groups": [
                        {"id": g.id, "name": g.name, "type": g.type}
                        for g in c.groups
                    ],
                }
                for c in competitions
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching competitions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch competitions")


@router.get("/api/teams-by-name/{season_name:path}")
async def list_teams_by_season_name(
    season_name: str,
    client: NBN23Client = Depends(get_client),
) -> JSONResponse:
    """List all teams for a season by season name.

    Args:
        season_name: The season name (e.g., "2025/2026")

    Returns:
        List of teams with id, name, and logo
    """
    try:
        season_id = await client.get_season_id(season_name)
        if not season_id:
            raise HTTPException(status_code=404, detail=f"Season '{season_name}' not found")

        teams = await client.get_all_teams(season_id)
        teams.sort(key=lambda t: t.name)
        return JSONResponse(
            content=[
                {"id": t.id, "name": t.name, "logo": t.logo}
                for t in teams
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching teams: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch teams")


@router.get("/calendar.ics")
async def get_calendar(
    season: str = Query(default=None, description="Season name (e.g., 2025/2026)"),
    competition: Optional[str] = Query(default=None, description="Competition name filter"),
    team: Optional[str] = Query(default=None, description="Team name filter"),
    days: Optional[int] = Query(default=None, ge=1, le=365, description="Days range"),
    status: str = Query(default="all", description="Status filter: all, upcoming, finished"),
    client: NBN23Client = Depends(get_client),
    calendar_service: CalendarService = Depends(get_calendar_service),
) -> Response:
    """Generate an ICS calendar feed.

    Args:
        season: Season name (defaults to current season)
        competition: Filter by competition name (partial match)
        team: Filter by team name (partial match)
        days: Only include games within N days from now
        status: Filter by status: "upcoming", "finished", "all"

    Returns:
        ICS calendar file
    """
    try:
        # Use default season if not specified
        if not season:
            season = settings.DEFAULT_SEASON

        # Get season ID
        season_id = await client.get_season_id(season)
        if not season_id:
            raise HTTPException(status_code=404, detail=f"Season '{season}' not found")

        # Build filters
        filters = MatchFilters(
            competition=competition,
            team=team,
            days=days,
            status=status,
        )

        # Fetch matches
        matches = await client.get_all_matches(season_id, filters)

        # Generate calendar name
        calendar_name = calendar_service.generate_calendar_name(
            competition=competition,
            team=team,
        )

        # Generate ICS
        ics_content = calendar_service.generate_ics(matches, calendar_name)

        # Return as ICS file
        return Response(
            content=ics_content,
            media_type="text/calendar; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=calendar.ics",
                "Cache-Control": "max-age=900",  # 15 minutes
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating calendar: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate calendar")


@router.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint.

    Returns:
        Health status
    """
    return JSONResponse(content={"status": "healthy", "version": "1.0.0"})


@router.get("/api/cache/stats")
async def cache_stats() -> JSONResponse:
    """Get cache statistics.

    Returns:
        Cache statistics
    """
    from src.services.cache import get_cache_service
    cache = get_cache_service()
    return JSONResponse(content=cache.stats())
