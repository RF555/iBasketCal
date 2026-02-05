"""Tests for NBN23Scraper - token extraction and API scraping."""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timezone, timedelta
import requests

from src.scraper.nbn23_scraper import NBN23Scraper


class TestScraperInit:
    """Tests for scraper initialization."""

    def test_default_initialization(self, test_data_dir):
        """Default initialization with headless mode."""
        scraper = NBN23Scraper(cache_dir=test_data_dir)

        assert scraper.headless is True
        assert scraper.cache_dir == Path(test_data_dir)
        assert scraper.cache_dir.exists()
        assert scraper.token is None
        assert scraper.session is None
        assert scraper.db is None

    def test_custom_initialization(self, test_data_dir, db_fixture):
        """Custom initialization with all parameters."""
        scraper = NBN23Scraper(
            headless=False,
            cache_dir=test_data_dir,
            database=db_fixture
        )

        assert scraper.headless is False
        assert scraper.cache_dir == Path(test_data_dir)
        assert scraper.db is db_fixture

    def test_cache_dir_created_if_not_exists(self, test_data_dir):
        """Cache directory is created if it doesn't exist."""
        cache_path = Path(test_data_dir) / "new_cache_dir"
        assert not cache_path.exists()

        scraper = NBN23Scraper(cache_dir=str(cache_path))

        assert cache_path.exists()
        assert scraper.cache_dir == cache_path


class TestTokenExtraction:
    """Tests for token extraction from widget."""

    @patch('src.scraper.nbn23_scraper.sync_playwright')
    def test_token_extracted_successfully(self, mock_playwright, test_data_dir):
        """Token successfully extracted from intercepted request."""
        # Create mock hierarchy: sync_playwright -> playwright -> chromium -> browser -> context -> page
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_browser = MagicMock()
        mock_chromium = MagicMock()
        mock_p = MagicMock()

        # Setup the chain
        mock_p.chromium = mock_chromium
        mock_chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        # Mock the context manager
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_playwright.return_value.__exit__.return_value = None

        # Capture the route handler and simulate it being called
        captured_handler = None

        def capture_route_handler(pattern, handler):
            nonlocal captured_handler
            captured_handler = handler

        mock_page.route = capture_route_handler

        scraper = NBN23Scraper(headless=True, cache_dir=test_data_dir)

        # Patch the page.goto and wait_for_timeout methods
        mock_page.goto = MagicMock()
        mock_page.wait_for_timeout = MagicMock()

        # Start token extraction (async)
        def simulate_extraction():
            token = scraper._extract_token()
            return token

        # Simulate the request with auth token after goto is called
        mock_page.goto.side_effect = lambda *args, **kwargs: (
            captured_handler(
                MagicMock(**{'continue_': MagicMock()}),
                MagicMock(headers={'authorization': 'Bearer test_token_12345'})
            ) if captured_handler else None
        )

        token = simulate_extraction()

        assert token == 'Bearer test_token_12345'
        assert scraper.token == 'Bearer test_token_12345'
        mock_page.goto.assert_called_once()

    @patch('src.scraper.nbn23_scraper.sync_playwright')
    def test_token_extraction_failure_no_token(self, mock_playwright, test_data_dir):
        """Raises RuntimeError when no token captured."""
        # Setup minimal mock structure
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_browser = MagicMock()
        mock_chromium = MagicMock()
        mock_p = MagicMock()

        mock_p.chromium = mock_chromium
        mock_chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_playwright.return_value.__exit__.return_value = None

        # Route handler that doesn't capture any token
        mock_page.route = MagicMock()
        mock_page.goto = MagicMock()
        mock_page.wait_for_timeout = MagicMock()

        scraper = NBN23Scraper(headless=True, cache_dir=test_data_dir)

        with pytest.raises(RuntimeError, match="Failed to extract API token"):
            scraper._extract_token()

    @patch('src.scraper.nbn23_scraper.sync_playwright')
    def test_token_extraction_page_error_but_token_captured(self, mock_playwright, test_data_dir):
        """Token captured even when page load fails."""
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_browser = MagicMock()
        mock_chromium = MagicMock()
        mock_p = MagicMock()

        mock_p.chromium = mock_chromium
        mock_chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_playwright.return_value.__exit__.return_value = None

        captured_handler = None

        def capture_route_handler(pattern, handler):
            nonlocal captured_handler
            captured_handler = handler

        mock_page.route = capture_route_handler

        # Simulate page error but token still captured
        def goto_with_error(*args, **kwargs):
            # First call the handler to capture token
            if captured_handler:
                captured_handler(
                    MagicMock(**{'continue_': MagicMock()}),
                    MagicMock(headers={'authorization': 'Bearer token_despite_error'})
                )
            raise Exception("Page timeout")

        mock_page.goto = goto_with_error
        mock_page.wait_for_timeout = MagicMock()

        scraper = NBN23Scraper(headless=True, cache_dir=test_data_dir)

        # Should succeed because token was captured before error
        token = scraper._extract_token()
        assert token == 'Bearer token_despite_error'

    @patch('src.scraper.nbn23_scraper.sync_playwright')
    def test_token_extraction_page_error_no_token(self, mock_playwright, test_data_dir):
        """Raises RuntimeError with page error message when no token."""
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_browser = MagicMock()
        mock_chromium = MagicMock()
        mock_p = MagicMock()

        mock_p.chromium = mock_chromium
        mock_chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_playwright.return_value.__exit__.return_value = None

        mock_page.route = MagicMock()
        mock_page.goto = MagicMock(side_effect=Exception("Connection timeout"))
        mock_page.wait_for_timeout = MagicMock()

        scraper = NBN23Scraper(headless=True, cache_dir=test_data_dir)

        with pytest.raises(RuntimeError, match="Failed to extract API token.*Connection timeout"):
            scraper._extract_token()

    @patch('src.scraper.nbn23_scraper.sync_playwright')
    def test_playwright_crash(self, mock_playwright, test_data_dir):
        """Raises RuntimeError when playwright crashes."""
        mock_playwright.return_value.__enter__.side_effect = Exception("Playwright initialization failed")

        scraper = NBN23Scraper(headless=True, cache_dir=test_data_dir)

        with pytest.raises(RuntimeError, match="Playwright error"):
            scraper._extract_token()


class TestSessionInit:
    """Tests for session initialization."""

    def test_session_created_with_token(self, test_data_dir):
        """Session created with correct headers when token exists."""
        scraper = NBN23Scraper(cache_dir=test_data_dir)
        scraper.token = "Bearer test_token"

        scraper._init_session()

        assert scraper.session is not None
        assert isinstance(scraper.session, requests.Session)
        assert scraper.session.headers['Authorization'] == "Bearer test_token"
        assert scraper.session.headers['Origin'] == NBN23Scraper.ORIGIN
        assert scraper.session.headers['Accept'] == "application/json"

    def test_session_extracts_token_if_missing(self, test_data_dir):
        """Session initialization calls _extract_token when no token."""
        scraper = NBN23Scraper(cache_dir=test_data_dir)
        assert scraper.token is None

        # Mock _extract_token to set the token (mimicking real behavior)
        def mock_extract_token():
            scraper.token = "Bearer extracted_token"
            return "Bearer extracted_token"

        with patch.object(scraper, '_extract_token', side_effect=mock_extract_token) as mock_extract:
            scraper._init_session()

            mock_extract.assert_called_once()
            assert scraper.token == "Bearer extracted_token"
            assert scraper.session.headers['Authorization'] == "Bearer extracted_token"

    def test_session_headers(self, test_data_dir):
        """Verify all required session headers."""
        scraper = NBN23Scraper(cache_dir=test_data_dir)
        scraper.token = "Bearer test_token"

        scraper._init_session()

        headers = scraper.session.headers
        assert headers['Authorization'] == "Bearer test_token"
        assert headers['Origin'] == "https://ibasketball.co.il"
        assert headers['Accept'] == "application/json"


class TestApiRequest:
    """Tests for API request method."""

    def test_successful_request(self, test_data_dir):
        """Successful API request returns JSON data."""
        scraper = NBN23Scraper(cache_dir=test_data_dir)
        scraper.token = "Bearer test_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'id': 'season1', 'name': '2024'}]

        with patch.object(scraper, '_init_session'):
            scraper.session = Mock(spec=requests.Session)
            scraper.session.get.return_value = mock_response

            result = scraper._api_request("seasons")

            assert result == [{'id': 'season1', 'name': '2024'}]
            scraper.session.get.assert_called_once_with(
                f"{NBN23Scraper.API_BASE}/seasons",
                params=None,
                timeout=30
            )

    def test_401_triggers_token_refresh(self, test_data_dir):
        """401 response triggers token re-extraction and retry."""
        scraper = NBN23Scraper(cache_dir=test_data_dir)
        scraper.token = "Bearer old_token"

        # First call returns 401, second call succeeds
        mock_response_401 = Mock()
        mock_response_401.status_code = 401

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = [{'id': 'data'}]

        # Setup initial session
        mock_session = Mock(spec=requests.Session)
        mock_session.get.side_effect = [mock_response_401, mock_response_200]
        scraper.session = mock_session

        # Mock _init_session to restore session after refresh
        original_init_session = scraper._init_session
        def mock_init_session():
            scraper.token = "Bearer new_token"
            scraper.session = mock_session

        with patch.object(scraper, '_extract_token', return_value="Bearer new_token"):
            with patch.object(scraper, '_init_session', side_effect=mock_init_session):
                result = scraper._api_request("seasons", retry=True)

                # Should have refreshed token and retried
                assert scraper.token == "Bearer new_token"
                assert result == [{'id': 'data'}]
                assert mock_session.get.call_count == 2

    def test_401_no_retry_when_disabled(self, test_data_dir):
        """401 with retry=False returns empty data."""
        scraper = NBN23Scraper(cache_dir=test_data_dir)
        scraper.token = "Bearer test_token"

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.HTTPError()

        with patch.object(scraper, '_init_session'):
            scraper.session = Mock(spec=requests.Session)
            scraper.session.get.return_value = mock_response

            result = scraper._api_request("seasons", retry=False)

            # Should return empty list without retrying
            assert result == []
            scraper.session.get.assert_called_once()

    def test_network_error_returns_empty_list(self, test_data_dir):
        """Network error for list endpoints returns empty list."""
        scraper = NBN23Scraper(cache_dir=test_data_dir)
        scraper.token = "Bearer test_token"

        with patch.object(scraper, '_init_session'):
            scraper.session = Mock(spec=requests.Session)
            scraper.session.get.side_effect = requests.RequestException("Network error")

            result = scraper._api_request("seasons")

            assert result == []

    def test_network_error_returns_empty_dict(self, test_data_dir):
        """Network error for calendar/standings endpoints returns empty dict."""
        scraper = NBN23Scraper(cache_dir=test_data_dir)
        scraper.token = "Bearer test_token"

        with patch.object(scraper, '_init_session'):
            scraper.session = Mock(spec=requests.Session)
            scraper.session.get.side_effect = requests.RequestException("Network error")

            calendar_result = scraper._api_request("calendar", {"groupId": "123"})
            standings_result = scraper._api_request("standings", {"groupId": "123"})

            assert calendar_result == {}
            assert standings_result == {}

    def test_session_auto_initialized(self, test_data_dir):
        """API request auto-initializes session if None."""
        scraper = NBN23Scraper(cache_dir=test_data_dir)
        scraper.token = "Bearer test_token"
        assert scraper.session is None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        # Mock _init_session to create a session
        def create_session():
            mock_session = Mock(spec=requests.Session)
            mock_session.get.return_value = mock_response
            scraper.session = mock_session

        with patch.object(scraper, '_init_session', side_effect=create_session) as mock_init:
            result = scraper._api_request("seasons")

            # Should have called _init_session once
            mock_init.assert_called_once()
            # Session should now be set
            assert scraper.session is not None
            # Result should be the empty list
            assert result == []


class TestScrapeFlow:
    """Tests for full scrape workflow."""

    def test_full_scrape_with_database(self, test_data_dir, db_fixture):
        """Full scrape flow with database saves."""
        scraper = NBN23Scraper(cache_dir=test_data_dir, database=db_fixture)

        # Mock the scraper methods
        with patch.object(scraper, '_extract_token', return_value="Bearer token"):
            with patch.object(scraper, '_init_session'):
                with patch.object(scraper, '_api_request') as mock_api:
                    # Setup API responses
                    mock_api.side_effect = [
                        # seasons
                        [{'_id': 's1', 'name': '2024', 'startDate': '2024-09-01', 'endDate': None}],
                        # competitions for s1
                        [{'id': 'c1', 'name': 'League', 'groups': [{'id': 'g1', 'name': 'Group A'}]}],
                        # calendar for g1
                        {'rounds': [{'matches': [{'id': 'm1', 'date': '2024-10-15T18:00:00Z'}]}]},
                        # standings for g1
                        {'standings': []}
                    ]

                    # Mock database methods
                    db_fixture.save_seasons = Mock()
                    db_fixture.save_competitions = Mock()
                    db_fixture.save_matches = Mock(return_value=1)
                    db_fixture.save_standings = Mock()
                    db_fixture.update_scrape_timestamp = Mock()

                    result = scraper.scrape()

                    # Verify database methods called in order
                    db_fixture.save_seasons.assert_called_once()
                    db_fixture.save_competitions.assert_called_once()
                    db_fixture.save_matches.assert_called_once()
                    db_fixture.save_standings.assert_called_once()
                    db_fixture.update_scrape_timestamp.assert_called_once()

                    # Verify return structure
                    assert 'seasons' in result
                    assert 'groups' in result
                    assert 'matches' in result
                    assert 'elapsed' in result
                    assert isinstance(result['elapsed'], float)

    def test_scrape_returns_summary(self, test_data_dir, db_fixture):
        """Scrape returns summary dict with counts."""
        scraper = NBN23Scraper(cache_dir=test_data_dir, database=db_fixture)

        with patch.object(scraper, '_extract_token', return_value="Bearer token"):
            with patch.object(scraper, '_init_session'):
                with patch.object(scraper, '_api_request') as mock_api:
                    mock_api.side_effect = [
                        [{'_id': 's1', 'name': '2024', 'endDate': None}],
                        [{'id': 'c1', 'name': 'L', 'groups': [{'id': 'g1', 'name': 'A'}]}],
                        {'rounds': []},
                        {}
                    ]

                    # Mock db methods
                    for method in ['save_seasons', 'save_competitions', 'save_matches', 'save_standings', 'update_scrape_timestamp']:
                        setattr(db_fixture, method, Mock(return_value=0))

                    result = scraper.scrape()

                    assert result['seasons'] == 1
                    assert result['groups'] == 1
                    assert result['matches'] == 0
                    assert result['elapsed'] > 0

    def test_scrape_filters_old_seasons(self, test_data_dir, db_fixture):
        """Old seasons beyond cutoff date are skipped."""
        scraper = NBN23Scraper(cache_dir=test_data_dir, database=db_fixture)

        # Create a season that ended 60 days ago (beyond 45-day cutoff)
        old_end_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()

        with patch.object(scraper, '_extract_token', return_value="Bearer token"):
            with patch.object(scraper, '_init_session'):
                with patch.object(scraper, '_api_request') as mock_api:
                    mock_api.side_effect = [
                        [{'_id': 's1', 'name': 'Old Season', 'endDate': old_end_date}],
                    ]

                    # Mock db methods
                    db_fixture.save_seasons = Mock()
                    db_fixture.update_scrape_timestamp = Mock()

                    result = scraper.scrape()

                    # Should save the season but not fetch competitions
                    db_fixture.save_seasons.assert_called_once()
                    assert result['seasons'] == 1
                    assert result['groups'] == 0  # No groups because season was filtered

    def test_scrape_includes_recent_seasons(self, test_data_dir, db_fixture):
        """Seasons ended within 45 days are included."""
        scraper = NBN23Scraper(cache_dir=test_data_dir, database=db_fixture)

        # Create a season that ended 30 days ago (within cutoff)
        recent_end_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        with patch.object(scraper, '_extract_token', return_value="Bearer token"):
            with patch.object(scraper, '_init_session'):
                with patch.object(scraper, '_api_request') as mock_api:
                    mock_api.side_effect = [
                        [{'_id': 's1', 'name': 'Recent Season', 'endDate': recent_end_date}],
                        [{'id': 'c1', 'name': 'League', 'groups': [{'id': 'g1', 'name': 'A'}]}],
                        {'rounds': []},
                        {}
                    ]

                    # Mock db methods
                    for method in ['save_seasons', 'save_competitions', 'save_matches', 'save_standings', 'update_scrape_timestamp']:
                        setattr(db_fixture, method, Mock(return_value=0))

                    result = scraper.scrape()

                    # Should include this season
                    assert result['seasons'] == 1
                    assert result['groups'] == 1

    def test_scrape_includes_no_end_date_seasons(self, test_data_dir, db_fixture):
        """Seasons with no endDate are included."""
        scraper = NBN23Scraper(cache_dir=test_data_dir, database=db_fixture)

        with patch.object(scraper, '_extract_token', return_value="Bearer token"):
            with patch.object(scraper, '_init_session'):
                with patch.object(scraper, '_api_request') as mock_api:
                    mock_api.side_effect = [
                        [{'_id': 's1', 'name': 'Current Season', 'endDate': None}],
                        [{'id': 'c1', 'name': 'League', 'groups': [{'id': 'g1', 'name': 'A'}]}],
                        {'rounds': []},
                        {}
                    ]

                    # Mock db methods
                    for method in ['save_seasons', 'save_competitions', 'save_matches', 'save_standings', 'update_scrape_timestamp']:
                        setattr(db_fixture, method, Mock(return_value=0))

                    result = scraper.scrape()

                    # Should include season without end date
                    assert result['seasons'] == 1
                    assert result['groups'] == 1

    def test_scrape_handles_invalid_date(self, test_data_dir, db_fixture):
        """Unparseable endDate is included with warning."""
        scraper = NBN23Scraper(cache_dir=test_data_dir, database=db_fixture)

        with patch.object(scraper, '_extract_token', return_value="Bearer token"):
            with patch.object(scraper, '_init_session'):
                with patch.object(scraper, '_api_request') as mock_api:
                    mock_api.side_effect = [
                        [{'_id': 's1', 'name': 'Bad Date Season', 'endDate': 'invalid-date-format'}],
                        [{'id': 'c1', 'name': 'League', 'groups': [{'id': 'g1', 'name': 'A'}]}],
                        {'rounds': []},
                        {}
                    ]

                    # Mock db methods
                    for method in ['save_seasons', 'save_competitions', 'save_matches', 'save_standings', 'update_scrape_timestamp']:
                        setattr(db_fixture, method, Mock(return_value=0))

                    # Should not raise, includes season by default
                    result = scraper.scrape()

                    assert result['seasons'] == 1
                    assert result['groups'] == 1

    def test_scrape_without_database(self, test_data_dir):
        """Scrape without database doesn't call save methods."""
        scraper = NBN23Scraper(cache_dir=test_data_dir, database=None)

        with patch.object(scraper, '_extract_token', return_value="Bearer token"):
            with patch.object(scraper, '_init_session'):
                with patch.object(scraper, '_api_request') as mock_api:
                    mock_api.side_effect = [
                        [{'_id': 's1', 'name': '2024', 'endDate': None}],
                        [{'id': 'c1', 'name': 'League', 'groups': [{'id': 'g1', 'name': 'A'}]}],
                        {'rounds': [{'matches': [{'id': 'm1'}]}]},
                        {}
                    ]

                    # Should not raise
                    result = scraper.scrape()

                    assert result['seasons'] == 1
                    assert result['groups'] == 1
                    # Can't count matches without db save return value
                    assert result['matches'] == 0

    def test_scrape_skips_empty_groups(self, test_data_dir, db_fixture):
        """Groups without id are skipped."""
        scraper = NBN23Scraper(cache_dir=test_data_dir, database=db_fixture)

        with patch.object(scraper, '_extract_token', return_value="Bearer token"):
            with patch.object(scraper, '_init_session'):
                with patch.object(scraper, '_api_request') as mock_api:
                    mock_api.side_effect = [
                        [{'_id': 's1', 'name': '2024', 'endDate': None}],
                        [{'id': 'c1', 'name': 'League', 'groups': [
                            {'id': None, 'name': 'Invalid Group'},  # No id
                            {'id': 'g1', 'name': 'Valid Group'}  # Has id
                        ]}],
                        {'rounds': []},  # calendar for g1
                        {}  # standings for g1
                    ]

                    # Mock db methods
                    for method in ['save_seasons', 'save_competitions', 'save_matches', 'save_standings', 'update_scrape_timestamp']:
                        setattr(db_fixture, method, Mock(return_value=0))

                    result = scraper.scrape()

                    # Only 1 valid group should be processed
                    assert result['groups'] == 1
