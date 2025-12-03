"""Tests for DataService layer."""

import pytest
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.services.data_service import DataService
from src.storage import reset_database


class TestDataServiceInitialization:
    """Tests for DataService initialization."""

    def setup_method(self):
        """Reset before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()

    def test_init_with_cache_dir(self, test_data_dir):
        """Initialize with custom cache directory."""
        service = DataService(cache_dir=test_data_dir)

        assert service.cache_dir == Path(test_data_dir)
        assert service.cache_dir.exists()

    def test_lazy_scraper_initialization(self, test_data_dir):
        """Scraper only created when needed."""
        service = DataService(cache_dir=test_data_dir)

        # Scraper should not be initialized yet
        assert service._scraper is None

        # Access scraper property to trigger initialization
        scraper = service.scraper

        # Now it should be initialized
        assert scraper is not None
        assert service._scraper is scraper


class TestDataServiceGetData:
    """Tests for get_data method."""

    def setup_method(self):
        """Reset before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()

    def test_get_data_returns_seasons(self, db_fixture, sample_season_data):
        """get_data() returns dict with seasons."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService()

            # Save some seasons to the database and mark cache as updated
            db_fixture.save_seasons(sample_season_data)
            db_fixture.update_scrape_timestamp()

            # Mock scraper to prevent actual scraping
            mock_scraper = Mock()
            mock_scraper.scrape.return_value = None
            service._scraper = mock_scraper

            result = service.get_data()

            assert 'seasons' in result
            assert isinstance(result['seasons'], list)
            assert len(result['seasons']) == 2

    def test_get_data_force_refresh(self, test_data_dir, db_fixture, mock_scraper):
        """Force refresh triggers scrape."""
        # Add required method to db_fixture
        db_fixture.save_seasons([])
        db_fixture.update_scrape_timestamp()

        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)

            # Mock the scraper
            service._scraper = mock_scraper

            # Force refresh
            service.get_data(force_refresh=True)

            # Scraper should have been called
            mock_scraper.scrape.assert_called_once()


class TestDataServiceCacheInfo:
    """Tests for cache info methods."""

    def setup_method(self):
        """Reset before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()

    def test_get_cache_info_delegates_to_db(self, db_fixture):
        """Cache info from database."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService()

            # Add some data
            db_fixture.save_seasons([{'_id': 's1', 'name': 'Test'}])
            db_fixture.update_scrape_timestamp()

            info = service.get_cache_info()

            assert 'exists' in info
            assert info['exists'] is True


class TestDataServiceDelegateMethods:
    """Tests for methods that delegate to database."""

    def setup_method(self):
        """Reset before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()

    def test_get_seasons_delegates_to_db(self, db_fixture, sample_season_data):
        """Seasons from database."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService()

            db_fixture.save_seasons(sample_season_data)

            seasons = service.get_seasons()

            assert len(seasons) == 2
            assert seasons[0]['name'] == '2024-2025'

    def test_get_competitions_delegates_to_db(self, db_fixture, sample_competition_data):
        """Competitions from database."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService()

            # Save season first
            db_fixture.save_seasons([{'_id': 'season1', 'name': '2024-2025'}])
            db_fixture.save_competitions('season1', sample_competition_data)

            competitions = service.get_competitions('season1')

            assert len(competitions) == 2

    def test_get_all_competitions_delegates_to_db(self, db_fixture, sample_competition_data):
        """All competitions from database."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService()

            # Save season and competitions
            db_fixture.save_seasons([{'_id': 'season1', 'name': '2024-2025'}])
            db_fixture.save_competitions('season1', sample_competition_data)

            all_comps = service.get_all_competitions()

            assert len(all_comps) >= 2

    def test_get_matches_with_filters(self, db_fixture, sample_match_data):
        """Match filtering works."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService()

            # Save matches
            db_fixture.save_matches(
                group_id='group1',
                calendar_data=sample_match_data,
                competition_name='Premier League',
                group_name='Division A',
                season_id='season1'
            )

            # Get all matches
            all_matches = service.get_all_matches()
            assert len(all_matches) == 2

            # Filter by team
            maccabi_matches = service.get_all_matches(team_name='Maccabi')
            assert len(maccabi_matches) >= 1

    def test_get_teams_delegates_to_db(self, db_fixture, sample_match_data):
        """Teams from database."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService()

            # Save matches (which contain teams)
            db_fixture.save_matches(
                group_id='group1',
                calendar_data=sample_match_data,
                competition_name='Premier League',
                group_name='Division A',
                season_id='season1'
            )

            teams = service.get_teams()

            assert len(teams) > 0

    def test_search_teams_delegates_to_db(self, db_fixture, sample_match_data):
        """Team search from database."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService()

            # Save matches
            db_fixture.save_matches(
                group_id='group1',
                calendar_data=sample_match_data,
                competition_name='Premier League',
                group_name='Division A',
                season_id='season1'
            )

            teams = service.search_teams('Maccabi')

            assert len(teams) >= 1
            assert 'Maccabi' in teams[0]['name']


class TestDataServiceScrapingState:
    """Tests for scraping state management."""

    def setup_method(self):
        """Reset before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()

    def test_is_scraping_initial_state(self, test_data_dir):
        """Initially not scraping."""
        service = DataService(cache_dir=test_data_dir)

        assert service.is_scraping() is False

    def test_refresh_async_starts_background_thread(self, test_data_dir, db_fixture):
        """Background refresh starts."""
        import threading

        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)

            # Create a blocking mock scraper to ensure is_scraping stays True
            scrape_started = threading.Event()
            scrape_continue = threading.Event()

            def blocking_scrape():
                scrape_started.set()
                scrape_continue.wait(timeout=5)

            blocking_scraper = Mock()
            blocking_scraper.scrape.side_effect = blocking_scrape
            service._scraper = blocking_scraper

            started = service.refresh_async()

            assert started is True
            scrape_started.wait(timeout=2)  # Wait for scrape to actually start
            assert service.is_scraping() is True

            scrape_continue.set()  # Let the scrape complete

    def test_refresh_async_returns_false_when_already_scraping(self, test_data_dir, db_fixture):
        """Prevents duplicate scrapes."""
        import threading

        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)

            # Create a blocking mock scraper to ensure first scrape is still running
            scrape_started = threading.Event()
            scrape_continue = threading.Event()

            def blocking_scrape():
                scrape_started.set()
                scrape_continue.wait(timeout=5)

            blocking_scraper = Mock()
            blocking_scraper.scrape.side_effect = blocking_scrape
            service._scraper = blocking_scraper

            # Start first scrape
            started1 = service.refresh_async()
            assert started1 is True

            # Wait for scrape to start
            scrape_started.wait(timeout=2)

            # Try to start another - should fail
            started2 = service.refresh_async()
            assert started2 is False

            scrape_continue.set()  # Let the scrape complete

    def test_last_scrape_error_tracking(self, test_data_dir):
        """Error tracking works."""
        with patch('src.services.data_service.get_database'):
            service = DataService(cache_dir=test_data_dir)

            # Initially no error
            assert service.get_last_scrape_error() is None

            # Mock scraper that raises error
            error_scraper = Mock()
            error_scraper.scrape.side_effect = Exception("Test error")
            service._scraper = error_scraper

            # Run scrape (will fail)
            try:
                service._run_scrape()
            except:
                pass

            # Error should be tracked
            error = service.get_last_scrape_error()
            assert error is not None
            assert 'Test error' in error


class TestDataServiceScraperProperty:
    """Tests for scraper property and caching."""

    def setup_method(self):
        """Reset before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()

    def test_run_scrape_with_scraper_success(self, test_data_dir, db_fixture, mock_scraper):
        """Mock successful scrape."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)
            service._scraper = mock_scraper

            service._run_scrape()

            # Scraper should have been called
            mock_scraper.scrape.assert_called_once()
            # No error should be set
            assert service.get_last_scrape_error() is None

    def test_run_scrape_with_scraper_failure(self, test_data_dir):
        """Mock failed scrape."""
        with patch('src.services.data_service.get_database'):
            service = DataService(cache_dir=test_data_dir)

            # Mock scraper that fails
            error_scraper = Mock()
            error_scraper.scrape.side_effect = Exception("Scrape failed")
            service._scraper = error_scraper

            # Run scrape
            service._run_scrape()

            # Error should be tracked
            assert service.get_last_scrape_error() == "Scrape failed"

    def test_scraper_property_caches_instance(self, test_data_dir):
        """Scraper singleton per service."""
        with patch('src.services.data_service.get_database'):
            service = DataService(cache_dir=test_data_dir)

            # Get scraper multiple times
            scraper1 = service.scraper
            scraper2 = service.scraper

            # Should be the same instance
            assert scraper1 is scraper2


class TestDataServiceMatchRefresh:
    """Tests for match-only refresh functionality."""

    def setup_method(self):
        """Reset before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()

    def test_refresh_matches_async_returns_no_data_when_empty(self, test_data_dir, db_fixture):
        """Returns no_data when no groups exist."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)

            started, reason = service.refresh_matches_async()

            assert started is False
            assert reason == 'no_data'

    def test_refresh_matches_async_starts_when_groups_exist(self, test_data_dir, db_fixture, mock_scraper):
        """Starts match refresh when groups exist."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)
            service._scraper = mock_scraper

            # Add some data to the database
            db_fixture.save_seasons([{'_id': 'season1', 'name': '2024-2025'}])
            db_fixture.save_competitions('season1', [
                {'name': 'Premier', 'groups': [{'id': 'group1', 'name': 'A'}]}
            ])

            started, reason = service.refresh_matches_async()

            assert started is True
            assert reason == 'started'
            assert service.is_scraping() is True

    def test_refresh_matches_async_returns_in_progress_when_scraping(self, test_data_dir, db_fixture, mock_scraper):
        """Returns in_progress when already scraping."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)
            service._scraper = mock_scraper

            # Add data
            db_fixture.save_seasons([{'_id': 'season1', 'name': '2024-2025'}])
            db_fixture.save_competitions('season1', [
                {'name': 'Premier', 'groups': [{'id': 'group1', 'name': 'A'}]}
            ])

            # Start first refresh
            started1, reason1 = service.refresh_matches_async()
            assert started1 is True

            # Try to start second refresh
            started2, reason2 = service.refresh_matches_async()
            assert started2 is False
            assert reason2 == 'in_progress'

    def test_get_refresh_type_returns_matches_during_match_refresh(self, test_data_dir, db_fixture, mock_scraper):
        """get_refresh_type returns 'matches' during match refresh."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)
            service._scraper = mock_scraper

            # Add data
            db_fixture.save_seasons([{'_id': 'season1', 'name': '2024-2025'}])
            db_fixture.save_competitions('season1', [
                {'name': 'Premier', 'groups': [{'id': 'group1', 'name': 'A'}]}
            ])

            # Initially None
            assert service.get_refresh_type() is None

            # Start match refresh
            service.refresh_matches_async()

            # Should be 'matches'
            assert service.get_refresh_type() == 'matches'

    def test_get_refresh_type_returns_full_during_full_refresh(self, test_data_dir, db_fixture, mock_scraper):
        """get_refresh_type returns 'full' during full refresh."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)
            service._scraper = mock_scraper

            # Start full refresh
            service.refresh_async()

            # Should be 'full'
            assert service.get_refresh_type() == 'full'

    def test_get_refresh_result_returns_none_initially(self, test_data_dir):
        """get_refresh_result returns None before any refresh."""
        with patch('src.services.data_service.get_database'):
            service = DataService(cache_dir=test_data_dir)

            assert service.get_refresh_result() is None

    def test_full_and_match_refresh_share_lock(self, test_data_dir, db_fixture):
        """Full and match refresh cannot run concurrently."""
        import threading

        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)

            # Add data for match refresh
            db_fixture.save_seasons([{'_id': 'season1', 'name': '2024-2025'}])
            db_fixture.save_competitions('season1', [
                {'name': 'Premier', 'groups': [{'id': 'group1', 'name': 'A'}]}
            ])

            # Create a blocking mock scraper that waits for an event
            scrape_started = threading.Event()
            scrape_continue = threading.Event()

            def blocking_scrape():
                scrape_started.set()  # Signal that scrape has started
                scrape_continue.wait(timeout=5)  # Wait until test says continue

            blocking_scraper = Mock()
            blocking_scraper.scrape.side_effect = blocking_scrape
            service._scraper = blocking_scraper

            # Start full refresh
            started_full = service.refresh_async()
            assert started_full is True

            # Wait for scrape to actually start
            scrape_started.wait(timeout=2)

            # Try to start match refresh - should fail because full is in progress
            started_match, reason = service.refresh_matches_async()
            assert started_match is False
            assert reason == 'in_progress'

            # Let the full refresh complete
            scrape_continue.set()
