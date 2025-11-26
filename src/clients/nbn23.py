"""NBN23 SWISH API client for Israeli basketball data."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from functools import lru_cache

import httpx

from src.config import get_settings
from src.models import Season, Competition, Group, Match, Team, Score, Court
from src.models.match import ScoreTotal
from src.services.cache import get_cache_service

logger = logging.getLogger(__name__)


class MatchFilters:
    """Filters for querying matches."""

    def __init__(
        self,
        competition: Optional[str] = None,
        team: Optional[str] = None,
        days: Optional[int] = None,
        status: str = "all",
    ):
        self.competition = competition
        self.team = team
        self.days = days
        self.status = status  # "upcoming", "finished", "all"


class NBN23Client:
    """Async client for the NBN23 SWISH API."""

    def __init__(self) -> None:
        """Initialize the API client."""
        self.settings = get_settings()
        self.base_url = self.settings.NBN23_BASE_URL
        self.cache = get_cache_service()
        self.headers = {
            "Accept": "*/*",
            "Origin": "https://ibasketball.co.il",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        # Add authorization header if API key is configured
        if self.settings.NBN23_API_KEY:
            self.headers["Authorization"] = f"Bearer {self.settings.NBN23_API_KEY}"

    async def _request(self, endpoint: str, params: Optional[dict] = None) -> dict | list:
        """Make an async HTTP request to the API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        # Add project key to all requests
        if params is None:
            params = {}
        params["projectKey"] = self.settings.NBN23_PROJECT_KEY

        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def get_seasons(self) -> list[Season]:
        """Fetch all available seasons.

        Returns:
            List of Season objects
        """
        cache_key = "all_seasons"
        cached = self.cache.get(cache_key, "seasons")
        if cached:
            logger.debug("Returning cached seasons")
            return cached

        logger.info("Fetching seasons from API")
        data = await self._request("/seasons")

        seasons = [Season.model_validate(s) for s in data]
        self.cache.set(cache_key, seasons, "seasons")
        return seasons

    async def get_season_by_name(self, name: str) -> Optional[Season]:
        """Get a season by its name.

        Args:
            name: Season name (e.g., "2025/2026")

        Returns:
            Season object or None if not found
        """
        seasons = await self.get_seasons()
        for season in seasons:
            if season.name == name:
                return season
        return None

    async def get_season_id(self, name: str) -> Optional[str]:
        """Get season ID by name, using known IDs as fallback.

        Args:
            name: Season name (e.g., "2025/2026")

        Returns:
            Season ID or None if not found
        """
        # First try known seasons
        if name in self.settings.KNOWN_SEASONS:
            return self.settings.KNOWN_SEASONS[name]

        # Fallback to API
        season = await self.get_season_by_name(name)
        return season.id if season else None

    async def get_competitions(self, season_id: str) -> list[Competition]:
        """Fetch all competitions for a season.

        Args:
            season_id: The season ID

        Returns:
            List of Competition objects
        """
        cache_key = f"competitions_{season_id}"
        cached = self.cache.get(cache_key, "competitions")
        if cached:
            logger.debug(f"Returning cached competitions for season {season_id}")
            return cached

        logger.info(f"Fetching competitions for season {season_id}")
        data = await self._request("/competitions", {"seasonId": season_id})

        competitions = [Competition.model_validate(c) for c in data]
        self.cache.set(cache_key, competitions, "competitions")
        return competitions

    async def get_calendar(self, group_id: str) -> dict:
        """Fetch calendar/matches for a competition group.

        Args:
            group_id: The group ID

        Returns:
            Calendar data with rounds and matches
        """
        cache_key = f"calendar_{group_id}"
        cached = self.cache.get(cache_key, "calendar")
        if cached:
            logger.debug(f"Returning cached calendar for group {group_id}")
            return cached

        logger.info(f"Fetching calendar for group {group_id}")
        data = await self._request("/calendar", {"groupId": group_id})

        self.cache.set(cache_key, data, "calendar")
        return data

    async def get_standings(self, group_id: str) -> list[dict]:
        """Fetch standings for a competition group.

        Args:
            group_id: The group ID

        Returns:
            List of standing entries
        """
        cache_key = f"standings_{group_id}"
        cached = self.cache.get(cache_key, "standings")
        if cached:
            logger.debug(f"Returning cached standings for group {group_id}")
            return cached

        logger.info(f"Fetching standings for group {group_id}")
        data = await self._request("/standings", {"groupId": group_id})

        self.cache.set(cache_key, data, "standings")
        return data

    async def get_all_teams(self, season_id: str) -> list[Team]:
        """Get all unique teams from a season's competitions.

        Args:
            season_id: The season ID

        Returns:
            List of unique Team objects
        """
        teams_dict: dict[str, Team] = {}

        competitions = await self.get_competitions(season_id)
        for competition in competitions:
            for group in competition.groups:
                try:
                    calendar = await self.get_calendar(group.id)
                    for round_data in calendar.get("rounds", []):
                        for match_data in round_data.get("matches", []):
                            home = match_data.get("homeTeam", {})
                            away = match_data.get("awayTeam", {})

                            if home.get("id"):
                                teams_dict[home["id"]] = Team(
                                    id=home["id"],
                                    name=home.get("name", ""),
                                    logo=home.get("logo"),
                                )
                            if away.get("id"):
                                teams_dict[away["id"]] = Team(
                                    id=away["id"],
                                    name=away.get("name", ""),
                                    logo=away.get("logo"),
                                )
                except Exception as e:
                    logger.warning(f"Error fetching calendar for group {group.id}: {e}")
                    continue

        return list(teams_dict.values())

    def _parse_match(
        self, match_data: dict, competition_name: str, group_name: str
    ) -> Match:
        """Parse match data from API response.

        Args:
            match_data: Raw match data from API
            competition_name: Name of the competition
            group_name: Name of the group/stage

        Returns:
            Match object
        """
        home_team_data = match_data.get("homeTeam", {})
        away_team_data = match_data.get("awayTeam", {})

        home_team = Team(
            id=home_team_data.get("id", ""),
            name=home_team_data.get("name", "Unknown"),
            logo=home_team_data.get("logo"),
        )

        away_team = Team(
            id=away_team_data.get("id", ""),
            name=away_team_data.get("name", "Unknown"),
            logo=away_team_data.get("logo"),
        )

        # Parse score
        score_data = match_data.get("score", {})
        score = None
        if score_data:
            totals = []
            for total in score_data.get("totals", []):
                totals.append(ScoreTotal(
                    teamId=total.get("teamId", ""),
                    total=total.get("total", 0)
                ))
            score = Score(totals=totals)

        # Parse court
        court_data = match_data.get("court", {})
        court = None
        if court_data:
            court = Court(
                place=court_data.get("place"),
                address=court_data.get("address"),
                town=court_data.get("town"),
            )

        # Parse date
        date_str = match_data.get("date", "")
        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            date = datetime.utcnow()

        return Match(
            id=match_data.get("id", ""),
            date=date,
            status=match_data.get("status", "NOT_STARTED"),
            homeTeam=home_team,
            awayTeam=away_team,
            score=score,
            court=court,
            competition_name=competition_name,
            group_name=group_name,
        )

    async def get_all_matches(
        self, season_id: str, filters: Optional[MatchFilters] = None
    ) -> list[Match]:
        """Fetch all matches for a season with optional filtering.

        Args:
            season_id: The season ID
            filters: Optional filters for competition, team, days, status

        Returns:
            List of Match objects matching the filters
        """
        filters = filters or MatchFilters()
        all_matches: list[Match] = []

        competitions = await self.get_competitions(season_id)

        for competition in competitions:
            # Filter by competition name if specified
            if filters.competition:
                if filters.competition.lower() not in competition.name.lower():
                    continue

            for group in competition.groups:
                try:
                    calendar = await self.get_calendar(group.id)

                    for round_data in calendar.get("rounds", []):
                        for match_data in round_data.get("matches", []):
                            match = self._parse_match(
                                match_data, competition.name, group.name
                            )

                            # Apply filters
                            if self._match_passes_filters(match, filters):
                                all_matches.append(match)

                except Exception as e:
                    logger.warning(
                        f"Error fetching calendar for {competition.name}/{group.name}: {e}"
                    )
                    continue

        # Sort by date
        all_matches.sort(key=lambda m: m.date)
        return all_matches

    def _match_passes_filters(self, match: Match, filters: MatchFilters) -> bool:
        """Check if a match passes the given filters.

        Args:
            match: The match to check
            filters: The filters to apply

        Returns:
            True if match passes all filters
        """
        # Team filter
        if filters.team:
            team_lower = filters.team.lower()
            if (
                team_lower not in match.home_team.name.lower()
                and team_lower not in match.away_team.name.lower()
            ):
                return False

        # Status filter
        if filters.status == "upcoming":
            if match.status == "CLOSED":
                return False
        elif filters.status == "finished":
            if match.status != "CLOSED":
                return False

        # Days filter
        if filters.days:
            now = datetime.utcnow()
            future_limit = now + timedelta(days=filters.days)
            past_limit = now - timedelta(days=filters.days)

            # For upcoming, only check future
            if filters.status == "upcoming":
                if match.date > future_limit:
                    return False
            # For finished, only check past
            elif filters.status == "finished":
                if match.date < past_limit:
                    return False
            # For all, check both directions
            else:
                if match.date > future_limit or match.date < past_limit:
                    return False

        return True


# Global client instance
_client: Optional[NBN23Client] = None


@lru_cache
def get_nbn23_client() -> NBN23Client:
    """Get the global NBN23 client instance."""
    global _client
    if _client is None:
        _client = NBN23Client()
    return _client
