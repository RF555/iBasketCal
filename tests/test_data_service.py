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

    def test_refresh_async_starts_background_thread(self, test_data_dir, db_fixture, mock_scraper):
        """Background refresh starts."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)
            service._scraper = mock_scraper

            started = service.refresh_async()

            assert started is True
            assert service.is_scraping() is True

    def test_refresh_async_returns_false_when_already_scraping(self, test_data_dir, db_fixture, mock_scraper):
        """Prevents duplicate scrapes."""
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            service = DataService(cache_dir=test_data_dir)
            service._scraper = mock_scraper

            # Start first scrape
            started1 = service.refresh_async()
            assert started1 is True

            # Try to start another
            started2 = service.refresh_async()
            assert started2 is False

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


class TestDataAccessMethodsDelegation:
    """Tests for data access method delegation to database."""

    def setup_method(self):
        """Reset before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()

    def test_get_seasons_delegates_correctly(self, test_data_dir):
        """Verify get_seasons calls db.get_seasons()."""
        mock_db = Mock()
        mock_db.get_seasons.return_value = [{'_id': 's1', 'name': 'Season 1'}]

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            result = service.get_seasons()

            mock_db.get_seasons.assert_called_once()
            assert len(result) == 1
            assert result[0]['name'] == 'Season 1'

    def test_get_competitions_delegates_with_season_id(self, test_data_dir):
        """Verify get_competitions passes season_id to db."""
        mock_db = Mock()
        mock_db.get_competitions.return_value = [{'id': 'c1', 'name': 'League A'}]

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            result = service.get_competitions('season_2024')

            mock_db.get_competitions.assert_called_once_with('season_2024')
            assert len(result) == 1

    def test_get_all_competitions_delegates_correctly(self, test_data_dir):
        """Verify get_all_competitions calls db.get_all_competitions()."""
        mock_db = Mock()
        mock_db.get_all_competitions.return_value = [
            {'id': 'c1', 'name': 'League A'},
            {'id': 'c2', 'name': 'League B'}
        ]

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            result = service.get_all_competitions()

            mock_db.get_all_competitions.assert_called_once()
            assert len(result) == 2

    def test_get_matches_delegates_with_group_id(self, test_data_dir):
        """Verify get_matches passes group_id to db."""
        mock_db = Mock()
        mock_db.get_matches.return_value = [{'id': 'm1'}, {'id': 'm2'}]

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            result = service.get_matches('group_123')

            mock_db.get_matches.assert_called_once_with(group_id='group_123')
            assert len(result) == 2

    def test_get_all_matches_with_season_filter(self, test_data_dir):
        """Verify get_all_matches passes season_id correctly."""
        mock_db = Mock()
        mock_db.get_matches.return_value = [{'id': 'm1', 'date': '2024-10-15'}]

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            result = service.get_all_matches(season_id='season_2024')

            mock_db.get_matches.assert_called_once()
            call_args = mock_db.get_matches.call_args
            assert call_args[1]['season_id'] == 'season_2024'

    def test_get_all_matches_with_group_id_filter(self, test_data_dir):
        """Verify get_all_matches passes group_id correctly."""
        mock_db = Mock()
        mock_db.get_matches.return_value = []

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            service.get_all_matches(group_id='group_abc')

            call_args = mock_db.get_matches.call_args
            assert call_args[1]['group_id'] == 'group_abc'

    def test_get_all_matches_with_team_id_filter(self, test_data_dir):
        """Verify get_all_matches passes team_id correctly."""
        mock_db = Mock()
        mock_db.get_matches.return_value = []

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            service.get_all_matches(team_id='team_xyz')

            call_args = mock_db.get_matches.call_args
            assert call_args[1]['team_id'] == 'team_xyz'

    def test_get_all_matches_with_multiple_filters(self, test_data_dir):
        """Verify get_all_matches passes all filters together."""
        mock_db = Mock()
        mock_db.get_matches.return_value = []

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            service.get_all_matches(
                season_id='season_2024',
                group_id='group_123',
                team_id='team_abc',
                competition_name='Premier',
                team_name='Maccabi'
            )

            call_args = mock_db.get_matches.call_args
            assert call_args[1]['season_id'] == 'season_2024'
            assert call_args[1]['group_id'] == 'group_123'
            assert call_args[1]['team_id'] == 'team_abc'
            assert call_args[1]['competition_name'] == 'Premier'
            assert call_args[1]['team_name'] == 'Maccabi'

    def test_get_teams_without_season(self, test_data_dir):
        """Verify get_teams calls db with season_id=None."""
        mock_db = Mock()
        mock_db.get_teams.return_value = [{'id': 't1', 'name': 'Team A'}]

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            result = service.get_teams()

            mock_db.get_teams.assert_called_once_with(season_id=None)
            assert len(result) == 1

    def test_get_teams_with_season(self, test_data_dir):
        """Verify get_teams passes season_id to db."""
        mock_db = Mock()
        mock_db.get_teams.return_value = [{'id': 't1', 'name': 'Team A'}]

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            result = service.get_teams(season_id='season_2024')

            mock_db.get_teams.assert_called_once_with(season_id='season_2024')

    def test_get_teams_by_group_delegates(self, test_data_dir):
        """Verify get_teams_by_group passes group_id to db."""
        mock_db = Mock()
        mock_db.get_teams_by_group.return_value = [
            {'id': 't1', 'name': 'Team A'},
            {'id': 't2', 'name': 'Team B'}
        ]

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            result = service.get_teams_by_group('group_123')

            mock_db.get_teams_by_group.assert_called_once_with('group_123')
            assert len(result) == 2

    def test_search_teams_without_season(self, test_data_dir):
        """Verify search_teams passes query with season_id=None."""
        mock_db = Mock()
        mock_db.search_teams.return_value = [{'id': 't1', 'name': 'Maccabi'}]

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            result = service.search_teams('Maccabi')

            mock_db.search_teams.assert_called_once_with('Maccabi', season_id=None)
            assert len(result) == 1

    def test_search_teams_with_season(self, test_data_dir):
        """Verify search_teams passes both query and season_id."""
        mock_db = Mock()
        mock_db.search_teams.return_value = []

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            service.search_teams('Hapoel', season_id='season_2024')

            mock_db.search_teams.assert_called_once_with('Hapoel', season_id='season_2024')

    def test_get_cache_info_delegates_to_db(self, test_data_dir):
        """Verify get_cache_info calls db.get_cache_info()."""
        mock_db = Mock()
        mock_db.get_cache_info.return_value = {
            'exists': True,
            'stale': False,
            'last_updated': '2024-01-15T12:00:00Z'
        }

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)
            result = service.get_cache_info()

            mock_db.get_cache_info.assert_called_once()
            assert result['exists'] is True
            assert result['stale'] is False


class TestScraperPropertyLazyInit:
    """Tests for scraper property lazy initialization."""

    def setup_method(self):
        """Reset before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()

    def test_scraper_lazy_initialization(self, test_data_dir):
        """Verify scraper is only created on first access."""
        mock_db = Mock()

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)

            # Initially None
            assert service._scraper is None

            # Access property
            scraper = service.scraper

            # Now initialized
            assert scraper is not None
            assert service._scraper is scraper

    def test_scraper_reuses_instance(self, test_data_dir):
        """Verify scraper property returns same instance on multiple accesses."""
        mock_db = Mock()

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)

            # Access multiple times
            scraper1 = service.scraper
            scraper2 = service.scraper
            scraper3 = service.scraper

            # All should be the same instance
            assert scraper1 is scraper2
            assert scraper2 is scraper3


class TestRunScrapeDetails:
    """Tests for _run_scrape method edge cases."""

    def setup_method(self):
        """Reset before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()

    def test_run_scrape_sets_error_on_failure(self, test_data_dir):
        """Verify error is captured when scrape fails."""
        mock_db = Mock()

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)

            # Mock scraper that raises exception
            error_scraper = Mock()
            error_scraper.scrape.side_effect = RuntimeError("Token extraction failed")
            service._scraper = error_scraper

            # Run scrape
            service._run_scrape()

            # Error should be captured
            error = service.get_last_scrape_error()
            assert error is not None
            assert "Token extraction failed" in error

    def test_run_scrape_clears_scraping_flag_on_error(self, test_data_dir):
        """Verify _is_scraping flag is cleared after error."""
        mock_db = Mock()

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)

            # Mock failing scraper
            error_scraper = Mock()
            error_scraper.scrape.side_effect = Exception("Network error")
            service._scraper = error_scraper

            # Run scrape
            service._run_scrape()

            # Flag should be cleared even after error
            assert service.is_scraping() is False

    def test_run_scrape_skips_when_already_scraping(self, test_data_dir):
        """Verify concurrent scrape calls are skipped."""
        mock_db = Mock()

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)

            # Mock scraper
            mock_scraper = Mock()
            service._scraper = mock_scraper

            # Simulate already scraping
            service._is_scraping = True

            # Try to run scrape
            service._run_scrape()

            # Scraper should NOT have been called
            mock_scraper.scrape.assert_not_called()


class TestGetDataScrapingBehavior:
    """Tests for get_data scraping triggers."""

    def setup_method(self):
        """Reset before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()

    def test_get_data_scrapes_when_no_cache(self, test_data_dir):
        """Verify scrape is triggered when cache doesn't exist."""
        mock_db = Mock()
        mock_db.get_cache_info.return_value = {'exists': False, 'stale': False}
        mock_db.get_seasons.return_value = []

        with patch('src.services.data_service.get_database', return_value=mock_db):
            service = DataService(cache_dir=test_data_dir)

            # Mock scraper
            mock_scraper = Mock()
            mock_scraper.scrape.return_value = None
            service._scraper = mock_scraper

            # Get data when cache doesn't exist
            service.get_data(force_refresh=False)

            # Scraper should have been called
            mock_scraper.scrape.assert_called_once()
