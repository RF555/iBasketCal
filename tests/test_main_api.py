"""Tests for FastAPI endpoints."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from src.main import app, RateLimiter, data_service, calendar_service, refresh_rate_limiter
from src.storage import reset_database
from src import config


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
                team_name=None,
                group_id=None,
                team_id=None
            )

    def test_get_matches_endpoint_with_competition_filter(self):
        """Filter by competition (deprecated, backward compatible)."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?competition=Premier")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id=None,
                competition_name='Premier',
                team_name=None,
                group_id=None,
                team_id=None
            )

    def test_get_matches_endpoint_with_team_filter(self):
        """Filter by team name (deprecated, backward compatible)."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?team=Maccabi")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id=None,
                competition_name=None,
                team_name='Maccabi',
                group_id=None,
                team_id=None
            )

    def test_get_matches_endpoint_with_multiple_filters(self):
        """Combine filters."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?season=s1&competition=Premier&team=Maccabi")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id='s1',
                competition_name='Premier',
                team_name='Maccabi',
                group_id=None,
                team_id=None
            )

    def test_get_matches_endpoint_with_group_id(self):
        """Filter by group_id (ID-based, preferred)."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?group_id=grp123")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id=None,
                competition_name=None,
                team_name=None,
                group_id='grp123',
                team_id=None
            )

    def test_get_matches_endpoint_with_team_id(self):
        """Filter by team_id (ID-based, preferred)."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?team_id=team456")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id=None,
                competition_name=None,
                team_name=None,
                group_id=None,
                team_id='team456'
            )

    def test_get_matches_endpoint_with_id_filters(self):
        """Filter using ID-based parameters (preferred over name-based)."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?season=s1&group_id=grp123&team_id=team456")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id='s1',
                competition_name=None,
                team_name=None,
                group_id='grp123',
                team_id='team456'
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

    def test_get_teams_endpoint_with_group_id(self):
        """GET /api/teams?group_id=X uses get_teams_by_group (preferred)."""
        mock_teams = [
            {'id': 't1', 'name': 'Team A', 'logo': 'a.png'},
            {'id': 't2', 'name': 'Team B', 'logo': 'b.png'}
        ]

        with patch.object(data_service, 'get_teams_by_group', return_value=mock_teams):
            response = client.get("/api/teams?group_id=grp123")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            data_service.get_teams_by_group.assert_called_once_with('grp123')

    def test_get_teams_endpoint_group_id_takes_priority(self):
        """group_id takes priority over q (search)."""
        mock_teams = [{'id': 't1', 'name': 'Team A', 'logo': 'a.png'}]

        with patch.object(data_service, 'get_teams_by_group', return_value=mock_teams):
            # Even with q parameter, group_id should be used
            response = client.get("/api/teams?group_id=grp123&q=Maccabi")

            assert response.status_code == 200
            # Should call get_teams_by_group, not search_teams
            data_service.get_teams_by_group.assert_called_once_with('grp123')


class TestCalendarUrlEndpoint:
    """Tests for calendar URL generation endpoint."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_get_calendar_url_endpoint_basic(self):
        """GET /api/calendar-url returns all URL fields."""
        response = client.get("/api/calendar-url")

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        assert 'ics_url' in data
        assert 'webcal_url' in data
        assert 'google_url' in data
        assert 'outlook365_url' in data
        assert 'outlook_url' in data

    def test_get_calendar_url_endpoint_with_filters(self):
        """Calendar URL endpoint includes filter parameters."""
        response = client.get("/api/calendar-url?season=s1&group_id=grp123&team_id=team456")

        assert response.status_code == 200
        data = response.json()

        # Verify parameters are included in URLs
        assert 'season=s1' in data['ics_url']
        assert 'group_id=grp123' in data['ics_url']
        assert 'team_id=team456' in data['ics_url']

    def test_get_calendar_url_endpoint_player_mode(self):
        """Calendar URL endpoint includes player mode parameters."""
        response = client.get("/api/calendar-url?mode=player&prep=90&tf=12h&tz=America/New_York")

        assert response.status_code == 200
        data = response.json()

        # Verify player mode parameters are included
        assert 'mode=player' in data['ics_url']
        assert 'prep=90' in data['ics_url']
        assert 'tf=12h' in data['ics_url']
        # URL-encoded timezone
        assert 'tz=America' in data['ics_url']

    def test_get_calendar_url_endpoint_fan_mode_no_extra_params(self):
        """Fan mode (default) does not include player mode parameters."""
        response = client.get("/api/calendar-url?season=s1")

        assert response.status_code == 200
        data = response.json()

        # Should not include player mode params
        assert 'mode=' not in data['ics_url']
        assert 'prep=' not in data['ics_url']
        assert 'tf=' not in data['ics_url']

    def test_get_calendar_url_endpoint_webcal_protocol(self):
        """webcal_url uses webcal:// protocol."""
        response = client.get("/api/calendar-url")

        assert response.status_code == 200
        data = response.json()

        assert data['webcal_url'].startswith('webcal://')
        assert '/calendar.ics' in data['webcal_url']

    def test_get_calendar_url_endpoint_google_url_format(self):
        """Google URL uses correct format."""
        response = client.get("/api/calendar-url")

        assert response.status_code == 200
        data = response.json()

        assert data['google_url'].startswith('https://calendar.google.com/calendar/r?cid=')
        # webcal URL should be encoded in the cid parameter
        assert 'webcal%3A%2F%2F' in data['google_url']

    def test_get_calendar_url_endpoint_outlook365_url_format(self):
        """Outlook 365 URL uses correct format."""
        response = client.get("/api/calendar-url")

        assert response.status_code == 200
        data = response.json()

        assert data['outlook365_url'].startswith('https://outlook.office.com/calendar/0/addfromweb?url=')

    def test_get_calendar_url_endpoint_outlook_url_format(self):
        """Outlook.com URL uses correct format."""
        response = client.get("/api/calendar-url")

        assert response.status_code == 200
        data = response.json()

        assert data['outlook_url'].startswith('https://outlook.live.com/calendar/0/addfromweb?url=')

    def test_get_calendar_url_endpoint_url_encoding(self):
        """URLs are properly encoded for special characters."""
        # Test with parameters that contain special characters
        response = client.get("/api/calendar-url?season=test%20season")

        assert response.status_code == 200
        data = response.json()

        # The season parameter should be in the URL (encoded)
        assert 'season=' in data['ics_url']

    def test_get_calendar_url_endpoint_prep_validation(self):
        """Prep time validation (15-180 minutes)."""
        # Too low
        response_low = client.get("/api/calendar-url?mode=player&prep=5")
        assert response_low.status_code == 422

        # Too high
        response_high = client.get("/api/calendar-url?mode=player&prep=200")
        assert response_high.status_code == 422

        # Valid
        response_valid = client.get("/api/calendar-url?mode=player&prep=60")
        assert response_valid.status_code == 200


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
        """Calendar with name-based filters (backward compatible)."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/calendar.ics?team=Maccabi&competition=Premier")

            assert response.status_code == 200
            # Verify filters were passed
            data_service.get_all_matches.assert_called_once_with(
                season_id=None,
                competition_name='Premier',
                team_name='Maccabi',
                group_id=None,
                team_id=None
            )

    def test_get_calendar_endpoint_with_id_filters(self):
        """Calendar with ID-based filters (preferred)."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/calendar.ics?season=s1&group_id=grp123&team_id=team456")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id='s1',
                competition_name=None,
                team_name=None,
                group_id='grp123',
                team_id='team456'
            )

    def test_get_calendar_endpoint_cache_headers(self):
        """Cache-Control headers present."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/calendar.ics")

            assert response.status_code == 200
            assert 'cache-control' in response.headers
            assert 'max-age=900' in response.headers['cache-control']


class TestCalendarEndpointPlayerMode:
    """Tests for calendar endpoint with player mode."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_calendar_endpoint_default_fan_mode(self):
        """Default mode is fan."""
        sample_matches = [{
            'id': 'm1',
            'date': '2024-10-15T20:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            response = client.get("/calendar.ics")

            assert response.status_code == 200
            # Should NOT have time prefix in fan mode
            assert 'SUMMARY:A vs B' in response.text

    def test_calendar_endpoint_player_mode(self):
        """Player mode works correctly."""
        sample_matches = [{
            'id': 'm1',
            'date': '2024-10-15T20:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            # Use tz=UTC to test player mode without timezone conversion
            response = client.get("/calendar.ics?mode=player&prep=60&tz=UTC")

            assert response.status_code == 200
            # Should have time prefix in player mode (20:00 UTC)
            assert '20:00' in response.text

    def test_calendar_endpoint_invalid_mode_defaults_to_fan(self):
        """Invalid mode defaults to fan."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/calendar.ics?mode=invalid")

            assert response.status_code == 200

    def test_calendar_endpoint_prep_time_validation_too_low(self):
        """Prep time must be at least 15."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/calendar.ics?mode=player&prep=5")

            # FastAPI validation should reject
            assert response.status_code == 422

    def test_calendar_endpoint_prep_time_validation_too_high(self):
        """Prep time must be at most 180."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/calendar.ics?mode=player&prep=200")

            # FastAPI validation should reject
            assert response.status_code == 422

    def test_calendar_endpoint_valid_prep_times(self):
        """Valid prep times work correctly."""
        sample_matches = [{
            'id': 'm1',
            'date': '2024-10-15T20:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            # Test minimum valid prep time
            response_15 = client.get("/calendar.ics?mode=player&prep=15")
            assert response_15.status_code == 200

            # Test maximum valid prep time
            response_180 = client.get("/calendar.ics?mode=player&prep=180")
            assert response_180.status_code == 200

    def test_calendar_endpoint_player_mode_calendar_name(self):
        """Player mode includes 'Player' in calendar name."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/calendar.ics?mode=player&prep=60")

            assert response.status_code == 200
            assert 'Player' in response.text


class TestCalendarEndpointTimeFormat:
    """Tests for calendar endpoint with time format parameter."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_calendar_endpoint_time_format_default_24h(self):
        """Default time format is 24h."""
        sample_matches = [{
            'id': 'm1',
            'date': '2024-10-15T21:00:00Z',  # 9 PM UTC
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            response = client.get("/calendar.ics?mode=player&prep=60&tz=UTC")

            assert response.status_code == 200
            assert '21:00' in response.text

    def test_calendar_endpoint_time_format_24h_explicit(self):
        """24h time format when explicitly specified."""
        sample_matches = [{
            'id': 'm1',
            'date': '2024-10-15T14:30:00Z',  # 2:30 PM UTC
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            response = client.get("/calendar.ics?mode=player&prep=60&tf=24h&tz=UTC")

            assert response.status_code == 200
            assert '14:30' in response.text

    def test_calendar_endpoint_time_format_12h(self):
        """12h time format works correctly."""
        sample_matches = [{
            'id': 'm1',
            'date': '2024-10-15T21:00:00Z',  # 9 PM UTC
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            response = client.get("/calendar.ics?mode=player&prep=60&tf=12h&tz=UTC")

            assert response.status_code == 200
            assert '9:00 PM' in response.text

    def test_calendar_endpoint_time_format_invalid_defaults_to_24h(self):
        """Invalid time format defaults to 24h."""
        sample_matches = [{
            'id': 'm1',
            'date': '2024-10-15T21:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            response = client.get("/calendar.ics?mode=player&prep=60&tf=invalid&tz=UTC")

            assert response.status_code == 200
            # Should use 24h format as fallback
            assert '21:00' in response.text

    def test_calendar_endpoint_time_format_fan_mode_ignored(self):
        """Time format in fan mode doesn't affect output."""
        sample_matches = [{
            'id': 'm1',
            'date': '2024-10-15T21:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            response = client.get("/calendar.ics?tf=12h")

            assert response.status_code == 200
            # Fan mode should NOT have time prefix
            assert 'SUMMARY:A vs B' in response.text
            assert '9:00 PM' not in response.text


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


class TestAllCompetitionsEndpoint:
    """Tests for GET /api/competitions (all competitions)."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_get_all_competitions_success(self, sample_competition_data):
        """GET /api/competitions returns list from data_service.get_all_competitions()."""
        with patch.object(data_service, 'get_all_competitions', return_value=sample_competition_data):
            response = client.get("/api/competitions")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2

    def test_get_all_competitions_error(self):
        """Service throws exception returns 500."""
        with patch.object(data_service, 'get_all_competitions', side_effect=Exception("DB Connection Failed")):
            response = client.get("/api/competitions")

            assert response.status_code == 500
            assert "DB Connection Failed" in response.json()["detail"]


class TestMatchesFilterCombinations:
    """Tests for matches endpoint with various filter combinations."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_matches_with_group_id_filter(self):
        """Group_id param passed to get_all_matches."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?group_id=grp999")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id=None,
                competition_name=None,
                team_name=None,
                group_id='grp999',
                team_id=None
            )

    def test_matches_with_team_id_filter(self):
        """Team_id param passed to get_all_matches."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?team_id=team888")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id=None,
                competition_name=None,
                team_name=None,
                group_id=None,
                team_id='team888'
            )

    def test_matches_with_all_filters(self):
        """Season + competition + team + group_id + team_id all passed."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            response = client.get("/api/matches?season=s2024&competition=Liga&team=Hapoel&group_id=g100&team_id=t200")

            assert response.status_code == 200
            data_service.get_all_matches.assert_called_once_with(
                season_id='s2024',
                competition_name='Liga',
                team_name='Hapoel',
                group_id='g100',
                team_id='t200'
            )

    def test_matches_service_error(self):
        """Data_service raises exception returns 500."""
        with patch.object(data_service, 'get_all_matches', side_effect=RuntimeError("Query failed")):
            response = client.get("/api/matches")

            assert response.status_code == 500
            assert "Query failed" in response.json()["detail"]


class TestTeamsEndpointPaths:
    """Tests for teams endpoint with different filtering paths."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_teams_by_group_id(self):
        """When group_id provided, calls get_teams_by_group."""
        mock_teams = [
            {'id': 't1', 'name': 'Team Alpha', 'logo': 'alpha.png'},
            {'id': 't2', 'name': 'Team Beta', 'logo': 'beta.png'}
        ]

        with patch.object(data_service, 'get_teams_by_group', return_value=mock_teams):
            response = client.get("/api/teams?group_id=grp456")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            data_service.get_teams_by_group.assert_called_once_with('grp456')

    def test_teams_search_query(self):
        """When q provided, calls search_teams."""
        mock_teams = [{'id': 't1', 'name': 'Maccabi Tel Aviv', 'logo': 'm.png'}]

        with patch.object(data_service, 'search_teams', return_value=mock_teams):
            response = client.get("/api/teams?q=Maccabi")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            data_service.search_teams.assert_called_once_with('Maccabi', season_id=None)

    def test_teams_search_with_season(self):
        """Q + season, calls search_teams with season_id."""
        mock_teams = [{'id': 't1', 'name': 'Hapoel', 'logo': 'h.png'}]

        with patch.object(data_service, 'search_teams', return_value=mock_teams):
            response = client.get("/api/teams?q=Hapoel&season=s2023")

            assert response.status_code == 200
            data_service.search_teams.assert_called_once_with('Hapoel', season_id='s2023')

    def test_teams_all_with_season(self):
        """Season only, calls get_teams with season_id."""
        mock_teams = [
            {'id': 't1', 'name': 'Team A', 'logo': 'a.png'},
            {'id': 't2', 'name': 'Team B', 'logo': 'b.png'}
        ]

        with patch.object(data_service, 'get_teams', return_value=mock_teams):
            response = client.get("/api/teams?season=s2024")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            data_service.get_teams.assert_called_once_with(season_id='s2024')

    def test_teams_service_error(self):
        """Service throws exception returns 500."""
        with patch.object(data_service, 'get_teams', side_effect=Exception("Teams query error")):
            response = client.get("/api/teams")

            assert response.status_code == 500
            assert "Teams query error" in response.json()["detail"]


class TestCalendarUrlPlayerMode:
    """Tests for calendar URL endpoint with player mode parameters."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_calendar_url_fan_mode_default(self):
        """No mode param (fan default) - no mode/prep/tf/tz in ICS URL params."""
        response = client.get("/api/calendar-url?season=s1&group_id=g1")

        assert response.status_code == 200
        data = response.json()

        # Should have season and group_id
        assert 'season=s1' in data['ics_url']
        assert 'group_id=g1' in data['ics_url']

        # Should NOT have player mode params
        assert 'mode=' not in data['ics_url']
        assert 'prep=' not in data['ics_url']
        assert 'tf=' not in data['ics_url']

    def test_calendar_url_player_mode(self):
        """Mode=player includes mode, prep, tf, tz in URL params."""
        response = client.get("/api/calendar-url?mode=player&prep=90&tf=12h&tz=Europe/London")

        assert response.status_code == 200
        data = response.json()

        # All player mode params should be in the URL
        assert 'mode=player' in data['ics_url']
        assert 'prep=90' in data['ics_url']
        assert 'tf=12h' in data['ics_url']
        assert 'tz=Europe' in data['ics_url']  # URL-encoded timezone

    def test_calendar_url_custom_headers(self):
        """X-Forwarded-Proto and X-Forwarded-Host used in URL construction."""
        response = client.get(
            "/api/calendar-url",
            headers={
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "example.com"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should use forwarded headers
        assert data['ics_url'].startswith("https://example.com/calendar.ics")
        assert data['webcal_url'].startswith("webcal://example.com/calendar.ics")

    def test_calendar_url_all_params(self):
        """Season + group_id + team_id + mode=player + custom prep/tf/tz."""
        response = client.get("/api/calendar-url?season=s2024&group_id=g100&team_id=t200&mode=player&prep=120&tf=12h&tz=America/New_York")

        assert response.status_code == 200
        data = response.json()

        # All params should be included
        assert 'season=s2024' in data['ics_url']
        assert 'group_id=g100' in data['ics_url']
        assert 'team_id=t200' in data['ics_url']
        assert 'mode=player' in data['ics_url']
        assert 'prep=120' in data['ics_url']
        assert 'tf=12h' in data['ics_url']
        assert 'tz=America' in data['ics_url']


class TestCalendarIcsEndpoint:
    """Tests for calendar.ics endpoint with mode/time format validation."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_calendar_ics_fan_mode(self):
        """Default mode, verify generate_ics called with player_mode=False."""
        sample_matches = [{
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            with patch.object(calendar_service, 'generate_ics', return_value='BEGIN:VCALENDAR\nEND:VCALENDAR') as mock_gen:
                response = client.get("/calendar.ics")

                assert response.status_code == 200
                # Verify generate_ics called with player_mode=False
                mock_gen.assert_called_once()
                call_args = mock_gen.call_args
                assert call_args[1]['player_mode'] is False
                assert call_args[1]['prep_time_minutes'] == 0

    def test_calendar_ics_player_mode(self):
        """Mode=player, verify generate_ics called with player_mode=True, prep_time_minutes, time_format, display_timezone."""
        sample_matches = [{
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }]

        with patch.object(data_service, 'get_all_matches', return_value=sample_matches):
            with patch.object(calendar_service, 'generate_ics', return_value='BEGIN:VCALENDAR\nEND:VCALENDAR') as mock_gen:
                response = client.get("/calendar.ics?mode=player&prep=90&tf=12h&tz=Europe/Paris")

                assert response.status_code == 200
                # Verify generate_ics called with player mode params
                call_args = mock_gen.call_args
                assert call_args[1]['player_mode'] is True
                assert call_args[1]['prep_time_minutes'] == 90
                assert call_args[1]['time_format'] == '12h'
                assert call_args[1]['display_timezone'] == 'Europe/Paris'

    def test_calendar_ics_invalid_mode_defaults(self):
        """Mode=invalid defaults to 'fan'."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            with patch.object(calendar_service, 'generate_ics', return_value='BEGIN:VCALENDAR\nEND:VCALENDAR') as mock_gen:
                response = client.get("/calendar.ics?mode=invalid")

                assert response.status_code == 200
                # Should default to fan mode
                call_args = mock_gen.call_args
                assert call_args[1]['player_mode'] is False

    def test_calendar_ics_invalid_tf_defaults(self):
        """Tf=invalid defaults to '24h'."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            with patch.object(calendar_service, 'generate_ics', return_value='BEGIN:VCALENDAR\nEND:VCALENDAR') as mock_gen:
                response = client.get("/calendar.ics?mode=player&prep=60&tf=invalid")

                assert response.status_code == 200
                # Should default to 24h
                call_args = mock_gen.call_args
                assert call_args[1]['time_format'] == '24h'

    def test_calendar_ics_content_type(self):
        """Response has text/calendar content-type."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            with patch.object(calendar_service, 'generate_ics', return_value='BEGIN:VCALENDAR\nEND:VCALENDAR'):
                response = client.get("/calendar.ics")

                assert response.status_code == 200
                assert 'text/calendar' in response.headers['content-type']

    def test_calendar_ics_cache_control(self):
        """Response has Cache-Control header."""
        with patch.object(data_service, 'get_all_matches', return_value=[]):
            with patch.object(calendar_service, 'generate_ics', return_value='BEGIN:VCALENDAR\nEND:VCALENDAR'):
                response = client.get("/calendar.ics")

                assert response.status_code == 200
                assert 'cache-control' in response.headers
                assert 'max-age=900' in response.headers['cache-control']


class TestRefreshStatusEndpoint:
    """Tests for GET /api/refresh-status endpoint."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_refresh_status_not_scraping(self):
        """Returns is_scraping=False, cache info, last_error=None."""
        mock_cache = {
            'exists': True,
            'stale': False,
            'last_updated': '2024-10-15T12:00:00Z'
        }

        with patch.object(data_service, 'is_scraping', return_value=False):
            with patch.object(data_service, 'get_cache_info', return_value=mock_cache):
                with patch.object(data_service, 'get_last_scrape_error', return_value=None):
                    response = client.get("/api/refresh-status")

                    assert response.status_code == 200
                    data = response.json()
                    assert data['is_scraping'] is False
                    assert data['cache']['exists'] is True
                    assert data['last_error'] is None

    def test_refresh_status_during_scrape(self):
        """Is_scraping=True returned."""
        mock_cache = {'exists': True, 'stale': True}

        with patch.object(data_service, 'is_scraping', return_value=True):
            with patch.object(data_service, 'get_cache_info', return_value=mock_cache):
                with patch.object(data_service, 'get_last_scrape_error', return_value=None):
                    response = client.get("/api/refresh-status")

                    assert response.status_code == 200
                    data = response.json()
                    assert data['is_scraping'] is True


class TestHealthEndpoint:
    """Tests for GET /health endpoint with detailed validation."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_health_full_response(self):
        """Verify status, is_scraping, cache, database_size_mb fields."""
        mock_cache = {
            'exists': True,
            'stale': False,
            'last_updated': '2024-10-15T10:00:00Z',
            'stats': {'seasons': 2}
        }

        with patch.object(data_service, 'get_cache_info', return_value=mock_cache):
            with patch.object(data_service, 'is_scraping', return_value=False):
                with patch.object(data_service.db, 'get_database_size', return_value=5242880):  # 5 MB
                    response = client.get("/health")

                    assert response.status_code == 200
                    data = response.json()

                    # Verify all required fields
                    assert data['status'] == 'ok'
                    assert 'is_scraping' in data
                    assert data['is_scraping'] is False
                    assert 'cache' in data
                    assert data['cache']['exists'] is True
                    assert 'database_size_mb' in data
                    assert data['database_size_mb'] == 5.0

    def test_health_with_scraping(self):
        """During scrape, is_scraping=True in response."""
        mock_cache = {'exists': True, 'stale': True}

        with patch.object(data_service, 'get_cache_info', return_value=mock_cache):
            with patch.object(data_service, 'is_scraping', return_value=True):
                with patch.object(data_service.db, 'get_database_size', return_value=1024000):
                    response = client.get("/health")

                    assert response.status_code == 200
                    data = response.json()
                    assert data['is_scraping'] is True


class TestRefreshScenarios:
    """Tests for POST /api/refresh endpoint scenarios."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()
        refresh_rate_limiter.reset()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()
        refresh_rate_limiter.reset()

    def test_refresh_already_scraping(self):
        """Is_scraping=True returns status=in_progress."""
        with patch.object(data_service, 'is_scraping', return_value=True):
            response = client.post("/api/refresh")

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'in_progress'
            assert 'already in progress' in data['message'].lower()

    def test_refresh_rate_limited(self):
        """Second call within cooldown returns status=rate_limited with retry_after."""
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
                assert 'retry_after' in data
                assert data['retry_after'] > 0
                assert data['retry_after'] <= config.REFRESH_COOLDOWN_SECONDS


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
