"""
Type definitions for Israeli Basketball Calendar.

Provides TypedDict classes for structured data validation and IDE support.
"""

from typing import TypedDict, Optional, List


class TeamDict(TypedDict, total=False):
    """Team information."""
    id: str
    name: str
    logo: Optional[str]


class CourtDict(TypedDict, total=False):
    """Venue/court information."""
    place: Optional[str]
    address: Optional[str]
    town: Optional[str]


class ScoreTotalDict(TypedDict):
    """Score for one team."""
    teamId: str
    total: int


class ScoreDict(TypedDict, total=False):
    """Match score."""
    totals: List[ScoreTotalDict]


class MatchDict(TypedDict, total=False):
    """
    Match/game data.

    Core fields from API plus metadata fields added by our service.
    """
    # Core fields
    id: str
    date: str
    status: str  # NOT_STARTED, LIVE, CLOSED
    homeTeam: TeamDict
    awayTeam: TeamDict
    score: ScoreDict
    court: CourtDict

    # Metadata added by DataService
    _competition: str
    _group: str
    _group_id: str
    _season: str
    _season_id: str


class GroupDict(TypedDict, total=False):
    """Competition group/division."""
    id: str
    name: str
    type: str  # LEAGUE, PLAYOFF, etc.
    order: int


class CompetitionDict(TypedDict, total=False):
    """Competition/league."""
    id: str
    name: str
    projectKey: str
    groups: List[GroupDict]
    _season_id: str  # Added by service


class SeasonDict(TypedDict, total=False):
    """Season."""
    _id: str
    id: str
    name: str
    startDate: str
    endDate: str


class StandingEntryDict(TypedDict, total=False):
    """Standing entry for a team in a group."""
    teamId: str
    name: str
    position: int
    logo: str
    stats: dict  # Complex nested stats


class CacheStatsDict(TypedDict, total=False):
    """Statistics about cached data."""
    seasons: int
    competitions: int
    groups: int
    matches: int
    teams: int


class CacheInfoDict(TypedDict, total=False):
    """Cache status information."""
    exists: bool
    stale: bool
    last_updated: Optional[str]
    age_minutes: Optional[int]
    stats: CacheStatsDict
    is_scraping: bool
    database_size_mb: float


class RefreshResponseDict(TypedDict, total=False):
    """Response from /api/refresh endpoint."""
    status: str  # started, in_progress, rate_limited
    message: str
    retry_after: int  # Only present when rate_limited


class ScrapeResultDict(TypedDict):
    """Result from scraper.scrape()."""
    seasons: int
    groups: int
    matches: int
    elapsed: float
