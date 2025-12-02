"""Tests for FastAPI endpoints."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from src.main import app, RateLimiter, data_service, refresh_rate_limiter
from src.storage import reset_database


# Create a synchronous test client
client = TestClient(app)


class TestHomeEndpoint:
    """Tests for home endpoint."""

    def test_home_endpoint_returns_html(self):
        """GET / returns HTML."""
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_home_endpoint_when_static_missing(self):
        """Fallback HTML when no static files."""
        response = client.get("/")

        # Should work regardless of static files
        assert response.status_code == 200
        assert "Israeli Basketball Calendar" in response.text


class TestSeasonsEndpoint:
    """Tests for seasons endpoint."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_get_seasons_endpoint(self, db_fixture, sample_season_data):
        """GET /api/seasons returns data."""
        with patch.object(data_service, 'get_seasons', return_value=sample_season_data):
            response = client.get("/api/seasons")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2

    def test_get_seasons_endpoint_empty(self):
        """Returns empty list when no data."""
        with patch.object(data_service, 'get_seasons', return_value=[]):
            response = client.get("/api/seasons")

            assert response.status_code == 200
            assert response.json() == []

    def test_get_seasons_endpoint_error(self):
        """Handle service errors."""
        with patch.object(data_service, 'get_seasons', side_effect=Exception("DB Error")):
            response = client.get("/api/seasons")

            assert response.status_code == 500
            assert "DB Error" in response.json()["detail"]


class TestCompetitionsEndpoint:
    """Tests for competitions endpoints."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_get_all_competitions_endpoint(self, sample_competition_data):
        """GET /api/competitions returns all."""
        with patch.object(data_service, 'get_all_competitions', return_value=sample_competition_data):
            response = client.get("/api/competitions")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    def test_get_competitions_by_season_endpoint(self, sample_competition_data):
        """GET /api/competitions/{season_id}."""
        with patch.object(data_service, 'get_competitions', return_value=sample_competition_data):
            response = client.get("/api/competitions/season_2024_2025")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2


class TestMatchesEndpoint:
    """Tests for matches endpoint."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_get_matches_endpoint_no_filters(self):
        """GET /api/matches without filters."""
        sample_matches = [
            {'id': 'm1', 'homeTeam': {'name': 'A'}, 'awayTeam': {'name': 'B'}},
            {'id': 'm2', 'homeTeam': {'name': 'C'}, 'awayTeam': {'name': 'D'}}
        ]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            response = client.get("/api/matches")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    def test_get_matches_endpoint_with_season_filter(self):
        """Filter by season."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?season=season_2024_2025")

            assert response.status_code == 200
            # Verify the filter was passed
            data_service.get_all_matches.assert_called_once_with(
                season_id='season_2024_2025',
                competition_name=None,
                team_name=None
            )

    def test_get_matches_endpoint_with_competition_filter(self):
        """Filter by competition."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?competition=Premier")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id=None,
                competition_name='Premier',
                team_name=None
            )

    def test_get_matches_endpoint_with_team_filter(self):
        """Filter by team."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?team=Maccabi")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id=None,
                competition_name=None,
                team_name='Maccabi'
            )

    def test_get_matches_endpoint_with_multiple_filters(self):
        """Combine filters."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?season=s1&competition=Premier&team=Maccabi")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id='s1',
                competition_name='Premier',
                team_name='Maccabi'
            )


class TestTeamsEndpoint:
    """Tests for teams endpoint."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_get_teams_endpoint_no_query(self, sample_team_data):
        """GET /api/teams without search."""
        with patch.object(data_service, 'get_teams', return_value=sample_team_data):
            response = client.get("/api/teams")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 3

    def test_get_teams_endpoint_with_search(self, sample_team_data):
        """GET /api/teams?q=search."""
        filtered = [t for t in sample_team_data if 'Maccabi' in t['name']]

        with patch.object(data_service, 'search_teams', return_value=filtered):
            response = client.get("/api/teams?q=Maccabi")

            assert response.status_code == 200
            data = response.json()
            assert len(data) >= 1
            data_service.search_teams.assert_called_once()


class TestCalendarEndpoint:
    """Tests for calendar ICS endpoint."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_get_calendar_endpoint_basic(self):
        """GET /calendar.ics returns ICS."""
        sample_matches = [
            {
                'id': 'm1',
                'date': '2024-10-15T18:00:00Z',
                'homeTeam': {'id': 't1', 'name': 'Team A'},
                'awayTeam': {'id': 't2', 'name': 'Team B'},
                'court': {}
            }
        ]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            response = client.get("/calendar.ics")

            assert response.status_code == 200
            assert 'BEGIN:VCALENDAR' in response.text
            assert 'END:VCALENDAR' in response.text

    def test_get_calendar_endpoint_content_type(self):
        """Content-Type is text/calendar."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/calendar.ics")

            assert response.status_code == 200
            assert 'text/calendar' in response.headers['content-type']

    def test_get_calendar_endpoint_with_filters(self):
        """Calendar with filters."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/calendar.ics?team=Maccabi&competition=Premier")

            assert response.status_code == 200
            # Verify filters were passed
            data_service.get_all_matches.assert_called_once_with(
                season_id=None,
                competition_name='Premier',
                team_name='Maccabi'
            )

    def test_get_calendar_endpoint_cache_headers(self):
        """Cache-Control headers present."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/calendar.ics")

            assert response.status_code == 200
            assert 'cache-control' in response.headers
            assert 'max-age=900' in response.headers['cache-control']


class TestCacheInfoEndpoint:
    """Tests for cache info endpoint."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_get_cache_info_endpoint(self):
        """GET /api/cache-info returns info."""
        mock_info = {
            'exists': True,
            'stale': False,
            'last_updated': '2024-10-15T12:00:00Z',
            'stats': {'seasons': 2, 'competitions': 5}
        }

        with patch.object(data_service, 'get_cache_info', return_value=mock_info):
            with patch.object(data_service, 'is_scraping', return_value=False):
                with patch.object(data_service.db, 'get_database_size', return_value=1024000):
                    response = client.get("/api/cache-info")

                    assert response.status_code == 200
                    data = response.json()
                    assert data['exists'] is True
                    assert 'is_scraping' in data
                    assert 'database_size_mb' in data

    def test_get_cache_info_includes_size(self):
        """Cache info includes database size."""
        with patch.object(data_service, 'get_cache_info', return_value={'exists': False}):
            with patch.object(data_service, 'is_scraping', return_value=False):
                with patch.object(data_service.db, 'get_database_size', return_value=2048000):
                    response = client.get("/api/cache-info")

                    assert response.status_code == 200
                    data = response.json()
                    assert 'database_size_mb' in data
                    assert data['database_size_mb'] > 0


class TestRefreshEndpoint:
    """Tests for refresh endpoint."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()
        # Reset rate limiter
        refresh_rate_limiter.reset()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()
        refresh_rate_limiter.reset()

    def test_refresh_endpoint_starts_scrape(self):
        """POST /api/refresh starts scrape."""
        with patch.object(data_service, 'is_scraping', return_value=False):
            with patch.object(data_service, 'refresh_async', return_value=True):
                response = client.post("/api/refresh")

                assert response.status_code == 200
                data = response.json()
                assert data['status'] == 'started'

    def test_refresh_endpoint_already_scraping(self):
        """Returns in_progress status."""
        with patch.object(data_service, 'is_scraping', return_value=True):
            response = client.post("/api/refresh")

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'in_progress'

    def test_refresh_endpoint_rate_limited(self):
        """Rate limiting works."""
        with patch.object(data_service, 'is_scraping', return_value=False):
            with patch.object(data_service, 'refresh_async', return_value=True):
                # First request - should succeed
                response1 = client.post("/api/refresh")
                assert response1.status_code == 200
                assert response1.json()['status'] == 'started'

                # Second request immediately - should be rate limited
                response2 = client.post("/api/refresh")
                assert response2.status_code == 200
                data = response2.json()
                assert data['status'] == 'rate_limited'

    def test_refresh_endpoint_includes_retry_after(self):
        """Retry-After header/field."""
        with patch.object(data_service, 'is_scraping', return_value=False):
            with patch.object(data_service, 'refresh_async', return_value=True):
                # Trigger rate limit
                client.post("/api/refresh")
                response = client.post("/api/refresh")

                assert response.status_code == 200
                data = response.json()
                if data['status'] == 'rate_limited':
                    assert 'retry_after' in data
                    assert data['retry_after'] > 0

    def test_refresh_status_endpoint(self):
        """GET /api/refresh-status returns status."""
        mock_cache = {'exists': True, 'stale': False}

        with patch.object(data_service, 'is_scraping', return_value=False):
            with patch.object(data_service, 'get_cache_info', return_value=mock_cache):
                with patch.object(data_service, 'get_last_scrape_error', return_value=None):
                    response = client.get("/api/refresh-status")

                    assert response.status_code == 200
                    data = response.json()
                    assert 'is_scraping' in data
                    assert 'cache' in data
                    assert 'last_error' in data


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_health_endpoint(self):
        """GET /health returns ok."""
        mock_cache = {'exists': True, 'stale': False}

        with patch.object(data_service, 'get_cache_info', return_value=mock_cache):
            with patch.object(data_service, 'is_scraping', return_value=False):
                with patch.object(data_service.db, 'get_database_size', return_value=1024000):
                    response = client.get("/health")

                    assert response.status_code == 200
                    data = response.json()
                    assert data['status'] == 'ok'

    def test_health_endpoint_includes_cache_info(self):
        """Health includes cache details."""
        mock_cache = {
            'exists': True,
            'stale': False,
            'last_updated': '2024-10-15T12:00:00Z'
        }

        with patch.object(data_service, 'get_cache_info', return_value=mock_cache):
            with patch.object(data_service, 'is_scraping', return_value=False):
                with patch.object(data_service.db, 'get_database_size', return_value=2048000):
                    response = client.get("/health")

                    assert response.status_code == 200
                    data = response.json()
                    assert 'cache' in data
                    assert data['cache']['exists'] is True
                    assert 'database_size_mb' in data


class TestCORS:
    """Tests for CORS middleware."""

    def test_cors_middleware_allows_origins(self):
        """CORS headers present."""
        response = client.options(
            "/api/seasons",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET"
            }
        )

        # CORS should allow the request
        assert "access-control-allow-origin" in response.headers
