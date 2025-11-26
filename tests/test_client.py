"""Tests for the NBN23 API client."""

import pytest
from datetime import datetime

from src.clients.nbn23 import NBN23Client, MatchFilters
from src.models import Season, Competition, Match, Team


class TestNBN23Client:
    """Tests for NBN23Client."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return NBN23Client()

    @pytest.mark.asyncio
    async def test_get_seasons(self, client):
        """Test fetching seasons from API."""
        seasons = await client.get_seasons()

        assert isinstance(seasons, list)
        assert len(seasons) > 0

        # Check first season has expected fields
        season = seasons[0]
        assert isinstance(season, Season)
        assert season.id
        assert season.name
        assert isinstance(season.start_date, datetime)
        assert isinstance(season.end_date, datetime)

    @pytest.mark.asyncio
    async def test_get_season_id_known(self, client):
        """Test getting known season ID."""
        season_id = await client.get_season_id("2025/2026")

        assert season_id == "686e1422dd2c672160d5ca4b"

    @pytest.mark.asyncio
    async def test_get_season_id_unknown(self, client):
        """Test getting unknown season ID returns None."""
        season_id = await client.get_season_id("1999/2000")

        assert season_id is None

    @pytest.mark.asyncio
    async def test_get_competitions(self, client):
        """Test fetching competitions."""
        season_id = "686e1422dd2c672160d5ca4b"  # 2025/2026
        competitions = await client.get_competitions(season_id)

        assert isinstance(competitions, list)
        assert len(competitions) > 0

        comp = competitions[0]
        assert isinstance(comp, Competition)
        assert comp.id
        assert comp.name
        assert isinstance(comp.groups, list)

    @pytest.mark.asyncio
    async def test_get_all_matches(self, client):
        """Test fetching all matches."""
        season_id = "686e1422dd2c672160d5ca4b"
        matches = await client.get_all_matches(season_id)

        assert isinstance(matches, list)
        # Should have some matches
        if len(matches) > 0:
            match = matches[0]
            assert isinstance(match, Match)
            assert match.id
            assert isinstance(match.home_team, Team)
            assert isinstance(match.away_team, Team)

    @pytest.mark.asyncio
    async def test_match_filters_by_team(self, client):
        """Test filtering matches by team."""
        season_id = "686e1422dd2c672160d5ca4b"
        filters = MatchFilters(team="מכבי")

        matches = await client.get_all_matches(season_id, filters)

        for match in matches:
            team_names = match.home_team.name + match.away_team.name
            assert "מכבי" in team_names.lower()

    @pytest.mark.asyncio
    async def test_match_filters_by_status(self, client):
        """Test filtering matches by status."""
        season_id = "686e1422dd2c672160d5ca4b"
        filters = MatchFilters(status="finished")

        matches = await client.get_all_matches(season_id, filters)

        for match in matches:
            assert match.status == "CLOSED"


class TestMatchFilters:
    """Tests for MatchFilters."""

    def test_default_filters(self):
        """Test default filter values."""
        filters = MatchFilters()

        assert filters.competition is None
        assert filters.team is None
        assert filters.days is None
        assert filters.status == "all"

    def test_custom_filters(self):
        """Test custom filter values."""
        filters = MatchFilters(
            competition="ליגת על",
            team="מכבי",
            days=30,
            status="upcoming",
        )

        assert filters.competition == "ליגת על"
        assert filters.team == "מכבי"
        assert filters.days == 30
        assert filters.status == "upcoming"
