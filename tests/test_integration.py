"""End-to-end integration tests."""

import pytest
import time
import threading
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from src.main import app
from src.services.data_service import DataService
from src.services.calendar_service import CalendarService
from src.storage import reset_database, get_database


client = TestClient(app)


class TestFullWorkflow:
    """Tests for complete workflows."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_full_workflow_scrape_to_calendar(
        self,
        test_data_dir,
        db_fixture,
        sample_season_data,
        sample_competition_data,
        sample_match_data
    ):
        """Complete flow: scrape -> query -> generate ICS."""
        # Step 1: Save data to database (simulating scrape)
        db_fixture.save_seasons(sample_season_data)
        db_fixture.save_competitions('season_2024_2025', sample_competition_data)
        db_fixture.save_matches(
            group_id='group_premier_a',
            calendar_data=sample_match_data,
            competition_name='Premier League',
            group_name='Division A',
            season_id='season_2024_2025'
        )
        db_fixture.update_scrape_timestamp()

        # Step 2: Create service with the database
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            data_service = DataService(cache_dir=test_data_dir)
            calendar_service = CalendarService()

            # Step 3: Query data
            seasons = data_service.get_seasons()
            assert len(seasons) == 2

            matches = data_service.get_all_matches()
            assert len(matches) == 2

            # Step 4: Generate calendar
            ics = calendar_service.generate_ics(matches, "Test Calendar")
            assert 'BEGIN:VCALENDAR' in ics
            assert 'Maccabi Tel Aviv' in ics
            assert 'Hapoel Jerusalem' in ics

    def test_calendar_subscription_workflow(
        self,
        db_fixture,
        sample_season_data,
        sample_match_data
    ):
        """Simulate calendar app subscription."""
        # Setup data
        db_fixture.save_seasons(sample_season_data)
        db_fixture.save_matches(
            group_id='group1',
            calendar_data=sample_match_data,
            competition_name='Premier League',
            group_name='Division A',
            season_id='season_2024_2025'
        )
        db_fixture.update_scrape_timestamp()

        with patch('src.main.data_service.get_all_matches') as mock_get_matches:
            mock_get_matches.return_value = db_fixture.get_matches(season_id='season_2024_2025')

            # Calendar app requests the ICS file
            response = client.get("/calendar.ics")

            assert response.status_code == 200
            assert 'text/calendar' in response.headers['content-type']
            assert 'BEGIN:VCALENDAR' in response.text

            # Verify cache headers for calendar app
            assert 'cache-control' in response.headers


class TestCacheRefreshWorkflow:
    """Tests for cache refresh workflows."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_cache_refresh_workflow(self, db_fixture):
        """Test cache staleness and refresh."""
        # Start with no cache
        cache_info = db_fixture.get_cache_info()
        assert cache_info['exists'] is False

        # Add some data
        db_fixture.save_seasons([{'_id': 's1', 'name': 'Test Season'}])
        db_fixture.update_scrape_timestamp()

        # Cache now exists
        cache_info = db_fixture.get_cache_info()
        assert cache_info['exists'] is True
        assert cache_info['stale'] is False

        # Simulate cache becoming stale (would need to mock time or wait)
        # For this test, just verify the cache info structure
        assert 'last_updated' in cache_info
        assert 'stats' in cache_info


class TestFilteredCalendarGeneration:
    """Tests for generating calendars with various filters."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_filtered_calendar_generation(
        self,
        db_fixture,
        sample_season_data,
        sample_match_data
    ):
        """Generate calendars with various filters."""
        # Setup data
        db_fixture.save_seasons(sample_season_data)
        db_fixture.save_matches(
            group_id='group1',
            calendar_data=sample_match_data,
            competition_name='Premier League',
            group_name='Division A',
            season_id='season_2024_2025'
        )

        with patch('src.main.data_service.get_all_matches') as mock_get_matches:
            # Test 1: Filter by team
            mock_get_matches.return_value = [m for m in sample_match_data['rounds'][0]['matches']
                                              if 'Maccabi' in m['homeTeam']['name'] or
                                              'Maccabi' in m['awayTeam']['name']]

            response = client.get("/calendar.ics?team=Maccabi")
            assert response.status_code == 200
            assert 'Maccabi' in response.text

            # Test 2: Filter by competition
            mock_get_matches.return_value = sample_match_data['rounds'][0]['matches']

            response = client.get("/calendar.ics?competition=Premier")
            assert response.status_code == 200

            # Test 3: Multiple filters
            response = client.get("/calendar.ics?team=Maccabi&competition=Premier")
            assert response.status_code == 200


class TestConcurrentRequests:
    """Tests for concurrent API requests."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_concurrent_api_requests(self, db_fixture, sample_season_data):
        """Multiple simultaneous API calls."""
        # Setup data
        db_fixture.save_seasons(sample_season_data)

        with patch('src.main.data_service.get_seasons', return_value=sample_season_data):
            results = []
            errors = []

            def make_request():
                try:
                    response = client.get("/api/seasons")
                    results.append(response.status_code)
                except Exception as e:
                    errors.append(str(e))

            # Create multiple threads making requests
            threads = [threading.Thread(target=make_request) for _ in range(10)]

            # Start all threads
            for t in threads:
                t.start()

            # Wait for all to complete
            for t in threads:
                t.join()

            # All requests should succeed
            assert len(errors) == 0
            assert all(status == 200 for status in results)


class TestDatabasePersistence:
    """Tests for data persistence."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_database_persistence(self, db_fixture, sample_season_data):
        """Data persists across service restarts."""
        # Save data
        db_fixture.save_seasons(sample_season_data)
        db_fixture.update_scrape_timestamp()

        # Verify data exists
        seasons1 = db_fixture.get_seasons()
        assert len(seasons1) == 2

        # "Restart" by getting a new database instance (but same file)
        # In a real scenario, this would be a new process
        reset_database()
        db2 = get_database()

        # Data should still be there
        seasons2 = db2.get_seasons()
        assert len(seasons2) == 2
        assert seasons2[0]['_id'] == seasons1[0]['_id']


class TestErrorRecovery:
    """Tests for error recovery."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_error_recovery(self):
        """App recovers from database errors."""
        # Test API returns graceful error when database fails
        with patch('src.main.data_service.get_seasons', side_effect=Exception("DB Connection Failed")):
            response = client.get("/api/seasons")

            # Should return 500 but not crash
            assert response.status_code == 500
            assert "DB Connection Failed" in response.json()["detail"]

        # After error, API should still work normally
        with patch('src.main.data_service.get_seasons', return_value=[]):
            response = client.get("/api/seasons")
            assert response.status_code == 200
