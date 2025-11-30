"""
Abstract base class defining the database interface.

All database implementations must inherit from this class and implement
all abstract methods. This ensures consistent behavior across backends.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class DatabaseInterface(ABC):
    """
    Abstract interface for basketball data storage.

    All methods must be implemented by concrete database classes.
    Methods should be thread-safe where applicable.
    """

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the database connection and schema.

        Called once when the database is first created.
        Should create tables/collections if they don't exist.
        Should be idempotent (safe to call multiple times).
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close database connections and clean up resources.

        Should be called when the application shuts down.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the database connection is healthy.

        Returns:
            True if database is accessible, False otherwise
        """
        pass

    # =========================================================================
    # WRITE OPERATIONS
    # =========================================================================

    @abstractmethod
    def save_seasons(self, seasons: List[Dict[str, Any]]) -> int:
        """
        Save or update seasons.

        Args:
            seasons: List of season dictionaries from the API
                    Each must have '_id' or 'id', 'name', optionally 'startDate', 'endDate'

        Returns:
            Number of seasons saved

        Behavior:
            - Insert new seasons
            - Update existing seasons (upsert)
        """
        pass

    @abstractmethod
    def save_competitions(self, season_id: str, competitions: List[Dict[str, Any]]) -> int:
        """
        Save or update competitions and their groups for a season.

        Args:
            season_id: The season these competitions belong to
            competitions: List of competition dictionaries
                         Each contains 'name' and 'groups' array

        Returns:
            Number of competitions saved

        Behavior:
            - Insert new competitions and groups
            - Update existing ones (upsert)
            - Groups are nested within competitions
        """
        pass

    @abstractmethod
    def save_matches(
        self,
        group_id: str,
        calendar_data: Dict[str, Any],
        competition_name: str = '',
        group_name: str = '',
        season_id: str = ''
    ) -> int:
        """
        Save or update matches from calendar data.

        Args:
            group_id: The competition group these matches belong to
            calendar_data: Calendar response containing 'rounds' array
                          Each round contains 'matches' array
            competition_name: Name of the competition (for denormalization)
            group_name: Name of the group (for denormalization)
            season_id: Season ID (for denormalization)

        Returns:
            Number of matches saved

        Behavior:
            - Extract matches from calendar_data['rounds'][*]['matches']
            - Extract team information and save to teams table
            - Denormalize competition/group/season info into each match
            - Upsert matches by ID
        """
        pass

    @abstractmethod
    def save_standings(self, group_id: str, standings: List[Dict[str, Any]]) -> int:
        """
        Save or update standings for a competition group.

        Args:
            group_id: The competition group
            standings: List of standing entries with 'teamId', 'position', etc.

        Returns:
            Number of standing entries saved
        """
        pass

    @abstractmethod
    def update_scrape_timestamp(self) -> None:
        """
        Record that a scrape just completed successfully.

        Updates metadata to current UTC timestamp.
        Used to determine cache freshness.
        """
        pass

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    @abstractmethod
    def get_seasons(self) -> List[Dict[str, Any]]:
        """
        Get all seasons, ordered by name descending (newest first).

        Returns:
            List of season dictionaries with full API data
        """
        pass

    @abstractmethod
    def get_competitions(self, season_id: str) -> List[Dict[str, Any]]:
        """
        Get competitions for a specific season.

        Args:
            season_id: The season to filter by

        Returns:
            List of competition dictionaries, ordered by name
        """
        pass

    @abstractmethod
    def get_all_competitions(self) -> List[Dict[str, Any]]:
        """
        Get all competitions across all seasons.

        Returns:
            List of competition dictionaries with '_season_id' added
        """
        pass

    @abstractmethod
    def get_matches(
        self,
        season_id: Optional[str] = None,
        competition_name: Optional[str] = None,
        team_name: Optional[str] = None,
        group_id: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get matches with flexible filtering.

        All filters are optional and combined with AND logic.
        String filters (competition_name, team_name) use partial matching.

        Args:
            season_id: Exact match on season
            competition_name: Partial match on competition name
            team_name: Partial match on either home or away team name
            group_id: Exact match on competition group
            status: Exact match on status (NOT_STARTED, LIVE, CLOSED)
            date_from: Matches on or after this ISO date
            date_to: Matches on or before this ISO date
            limit: Maximum number of matches to return

        Returns:
            List of match dictionaries, ordered by date ascending
        """
        pass

    @abstractmethod
    def get_teams(self, season_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all unique teams.

        Args:
            season_id: If provided, only teams that played in this season

        Returns:
            List of team dictionaries with 'id', 'name', 'logo'
            Ordered by name
        """
        pass

    @abstractmethod
    def search_teams(self, query: str, season_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search teams by name.

        Args:
            query: Partial name to search for
            season_id: If provided, only search teams from this season

        Returns:
            List of matching team dictionaries
        """
        pass

    @abstractmethod
    def get_standings(self, group_id: str) -> List[Dict[str, Any]]:
        """
        Get standings for a competition group.

        Args:
            group_id: The competition group

        Returns:
            List of standing entries, ordered by position
        """
        pass

    # =========================================================================
    # CACHE & METADATA
    # =========================================================================

    @abstractmethod
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the cache/data status.

        Returns:
            Dictionary with:
            - exists: bool - Whether any data has been scraped
            - stale: bool - Whether data is older than CACHE_TTL_MINUTES
            - last_updated: Optional[str] - ISO timestamp of last scrape
            - age_minutes: Optional[int] - Minutes since last scrape
            - stats: Dict[str, int] - Counts per table/collection
        """
        pass

    @abstractmethod
    def get_database_size(self) -> int:
        """
        Get the approximate database size in bytes.

        Returns:
            Size in bytes (0 if not applicable or unknown)
        """
        pass

    # =========================================================================
    # MAINTENANCE
    # =========================================================================

    @abstractmethod
    def clear_all(self) -> None:
        """
        Delete all data from the database.

        Used for testing or complete refresh.
        Does not drop tables/schema, just data.
        """
        pass

    @abstractmethod
    def vacuum(self) -> None:
        """
        Optimize database storage.

        Implementation depends on backend:
        - SQLite: VACUUM command
        - Turso: May be no-op (handled by service)
        - Supabase: VACUUM via SQL (not available via REST)
        """
        pass

    # =========================================================================
    # SPORTSPRESS PLAYER DATA
    # =========================================================================

    @abstractmethod
    def save_players(self, players: List[Dict[str, Any]]) -> int:
        """
        Save or update players from SportsPress API.

        Args:
            players: List of player dictionaries from SportsPress API
                    Each contains 'id', 'title', 'leagues', 'teams', etc.

        Returns:
            Number of players saved
        """
        pass

    @abstractmethod
    def get_players(
        self,
        team_id: Optional[int] = None,
        league_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get players with optional filters.

        Args:
            team_id: Filter by team ID
            league_id: Filter by league ID
            limit: Maximum number of players to return

        Returns:
            List of player dictionaries
        """
        pass

    @abstractmethod
    def search_players(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search players by name.

        Args:
            query: Search query (partial name match)
            limit: Maximum number of results

        Returns:
            List of matching player dictionaries
        """
        pass

    @abstractmethod
    def get_player(self, player_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single player by ID with full details.

        Args:
            player_id: The player's ID

        Returns:
            Player dictionary or None if not found
        """
        pass

    @abstractmethod
    def save_sportspress_leagues(self, leagues: List[Dict[str, Any]]) -> int:
        """
        Save SportsPress league metadata.

        Args:
            leagues: List of league dictionaries from SportsPress API

        Returns:
            Number of leagues saved
        """
        pass

    @abstractmethod
    def save_sportspress_teams(self, teams: List[Dict[str, Any]]) -> int:
        """
        Save SportsPress team metadata.

        Args:
            teams: List of team dictionaries from SportsPress API

        Returns:
            Number of teams saved
        """
        pass

    @abstractmethod
    def save_sportspress_seasons(self, seasons: List[Dict[str, Any]]) -> int:
        """
        Save SportsPress season metadata.

        Args:
            seasons: List of season dictionaries from SportsPress API

        Returns:
            Number of seasons saved
        """
        pass

    @abstractmethod
    def get_sportspress_leagues(self) -> List[Dict[str, Any]]:
        """
        Get all SportsPress leagues.

        Returns:
            List of league dictionaries with 'id' and 'name'
        """
        pass

    @abstractmethod
    def get_sportspress_teams(self) -> List[Dict[str, Any]]:
        """
        Get all SportsPress teams.

        Returns:
            List of team dictionaries with 'id' and 'name'
        """
        pass

    @abstractmethod
    def get_sportspress_seasons(self) -> List[Dict[str, Any]]:
        """
        Get all SportsPress seasons.

        Returns:
            List of season dictionaries with 'id' and 'name'
        """
        pass
