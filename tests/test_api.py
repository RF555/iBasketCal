"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.main import app


class TestAPIEndpoints:
    """Tests for API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_list_seasons(self, client):
        """Test seasons endpoint."""
        response = client.get("/api/seasons")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        season = data[0]
        assert "id" in season
        assert "name" in season
        assert "startDate" in season
        assert "endDate" in season

    def test_list_competitions(self, client):
        """Test competitions endpoint."""
        # Use known season ID
        season_id = "686e1422dd2c672160d5ca4b"
        response = client.get(f"/api/competitions/{season_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        if len(data) > 0:
            comp = data[0]
            assert "id" in comp
            assert "name" in comp
            assert "groups" in comp

    def test_list_competitions_by_name(self, client):
        """Test competitions by season name endpoint."""
        response = client.get("/api/competitions-by-name/2025/2026")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_teams(self, client):
        """Test teams endpoint."""
        season_id = "686e1422dd2c672160d5ca4b"
        response = client.get(f"/api/teams/{season_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        if len(data) > 0:
            team = data[0]
            assert "id" in team
            assert "name" in team

    def test_calendar_endpoint(self, client):
        """Test calendar ICS endpoint."""
        response = client.get("/calendar.ics?season=2025/2026")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/calendar")

        content = response.text
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content

    def test_calendar_with_filters(self, client):
        """Test calendar endpoint with filters."""
        response = client.get(
            "/calendar.ics",
            params={
                "season": "2025/2026",
                "days": 30,
                "status": "upcoming",
            },
        )

        assert response.status_code == 200
        assert "text/calendar" in response.headers["content-type"]

    def test_calendar_invalid_season(self, client):
        """Test calendar endpoint with invalid season."""
        response = client.get("/calendar.ics?season=invalid")

        assert response.status_code == 404

    def test_cache_stats(self, client):
        """Test cache stats endpoint."""
        response = client.get("/api/cache/stats")

        assert response.status_code == 200
        data = response.json()
        assert "seasons" in data
        assert "competitions" in data
        assert "calendar" in data

    def test_index_page(self, client):
        """Test index page serves HTML."""
        response = client.get("/")

        assert response.status_code == 200
        # Either HTML or JSON depending on static file presence
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type or "application/json" in content_type


class TestCacheService:
    """Tests for cache service."""

    def test_cache_get_set(self):
        """Test cache get and set."""
        from src.services.cache import CacheService

        cache = CacheService()

        cache.set("test_key", "test_value", "calendar")
        result = cache.get("test_key", "calendar")

        assert result == "test_value"

    def test_cache_miss(self):
        """Test cache miss."""
        from src.services.cache import CacheService

        cache = CacheService()
        result = cache.get("nonexistent", "calendar")

        assert result is None

    def test_cache_clear(self):
        """Test cache clear."""
        from src.services.cache import CacheService

        cache = CacheService()

        cache.set("key1", "value1", "calendar")
        cache.clear("calendar")
        result = cache.get("key1", "calendar")

        assert result is None
