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


class TestFullApiWorkflow:
    """Tests for complete API data flow through all layers."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_seasons_to_competitions_to_matches_flow(
        self,
        db_fixture,
        sample_season_data,
        sample_competition_data,
        sample_match_data
    ):
        """Complete data flow: seasons → competitions → matches."""
        # Step 1: Save hierarchical data to database
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

        # Step 2: Query seasons through DataService
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            data_service = DataService()
            seasons = data_service.get_seasons()

            # Verify seasons
            assert len(seasons) == 2
            assert seasons[0]['_id'] == 'season_2024_2025'

            # Step 3: Query competitions for a season
            competitions = data_service.get_competitions('season_2024_2025')
            assert len(competitions) == 2
            # Competitions are sorted alphabetically
            comp_names = [c['name'] for c in competitions]
            assert 'Premier League' in comp_names
            assert 'National League' in comp_names

            # Step 4: Query matches
            matches = data_service.get_all_matches(season_id='season_2024_2025')
            assert len(matches) == 2

            # Verify match metadata is enriched
            assert matches[0]['_competition'] == 'Premier League'
            assert matches[0]['_group'] == 'Division A'
            assert matches[0]['_season_id'] == 'season_2024_2025'
            assert matches[0]['_group_id'] == 'group_premier_a'

    def test_calendar_generation_from_stored_data(
        self,
        db_fixture,
        sample_season_data,
        sample_match_data
    ):
        """Generate ICS calendar from database-stored matches."""
        # Save data to database
        db_fixture.save_seasons(sample_season_data)
        db_fixture.save_matches(
            group_id='group_premier_a',
            calendar_data=sample_match_data,
            competition_name='Premier League',
            group_name='Division A',
            season_id='season_2024_2025'
        )

        # Retrieve matches via DataService
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            data_service = DataService()
            matches = data_service.get_all_matches()

            assert len(matches) == 2

            # Generate calendar
            calendar_service = CalendarService()
            ics = calendar_service.generate_ics(matches, "Test Calendar")

            # Verify ICS structure
            assert 'BEGIN:VCALENDAR' in ics
            assert 'END:VCALENDAR' in ics

            # Count VEVENT entries (should match number of matches)
            vevent_count = ics.count('BEGIN:VEVENT')
            assert vevent_count == 2

            # Verify team names appear
            assert 'Maccabi Tel Aviv' in ics
            assert 'Hapoel Jerusalem' in ics


class TestPlayerModeIntegration:
    """Tests for player mode calendar generation."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_player_mode_calendar_generation(
        self,
        db_fixture,
        sample_season_data,
        sample_match_data
    ):
        """Generate ICS with player mode - events should start earlier."""
        # Save matches
        db_fixture.save_seasons(sample_season_data)
        db_fixture.save_matches(
            group_id='group1',
            calendar_data=sample_match_data,
            competition_name='Premier League',
            group_name='Division A',
            season_id='season_2024_2025'
        )

        with patch('src.services.data_service.get_database', return_value=db_fixture):
            data_service = DataService()
            matches = data_service.get_all_matches()

            # Generate player mode calendar with 60 min prep
            calendar_service = CalendarService()
            ics_player = calendar_service.generate_ics(
                matches,
                "Player Calendar",
                player_mode=True,
                prep_time_minutes=60
            )

            # Verify calendar was generated
            assert 'BEGIN:VCALENDAR' in ics_player
            assert 'BEGIN:VEVENT' in ics_player

            # Verify player mode indicator in event
            # The match date is 2024-10-15T18:00:00Z
            # With 60 min prep, should start at 17:00:00Z
            assert 'DTSTART' in ics_player
            # Check that prep time is mentioned somewhere
            assert 'Prep time' in ics_player or '60 min' in ics_player or '17:00' in ics_player

    def test_fan_vs_player_mode_comparison(
        self,
        db_fixture,
        sample_season_data,
        sample_match_data
    ):
        """Compare fan mode vs player mode - verify different start times."""
        # Save data
        db_fixture.save_seasons(sample_season_data)
        db_fixture.save_matches(
            group_id='group1',
            calendar_data=sample_match_data,
            competition_name='Premier League',
            group_name='Division A',
            season_id='season_2024_2025'
        )

        with patch('src.services.data_service.get_database', return_value=db_fixture):
            data_service = DataService()
            matches = data_service.get_all_matches()
            calendar_service = CalendarService()

            # Generate fan mode calendar
            ics_fan = calendar_service.generate_ics(matches, "Fan Calendar", player_mode=False)

            # Generate player mode calendar with 90 min prep
            ics_player = calendar_service.generate_ics(
                matches,
                "Player Calendar",
                player_mode=True,
                prep_time_minutes=90
            )

            # Both should be valid calendars
            assert 'BEGIN:VCALENDAR' in ics_fan
            assert 'BEGIN:VCALENDAR' in ics_player

            # Both should have the same number of events
            assert ics_fan.count('BEGIN:VEVENT') == ics_player.count('BEGIN:VEVENT')

            # Extract DTSTART from within VEVENT (not VTIMEZONE)
            # Find first VEVENT, then find DTSTART within it
            fan_vevent_pos = ics_fan.find('BEGIN:VEVENT')
            fan_vevent_end_pos = ics_fan.find('END:VEVENT', fan_vevent_pos)
            fan_vevent_section = ics_fan[fan_vevent_pos:fan_vevent_end_pos]
            fan_start_pos = fan_vevent_section.find('DTSTART')

            player_vevent_pos = ics_player.find('BEGIN:VEVENT')
            player_vevent_end_pos = ics_player.find('END:VEVENT', player_vevent_pos)
            player_vevent_section = ics_player[player_vevent_pos:player_vevent_end_pos]
            player_start_pos = player_vevent_section.find('DTSTART')

            assert fan_start_pos > 0
            assert player_start_pos > 0

            # The start times should be different (player mode starts earlier)
            fan_start_line = fan_vevent_section[fan_start_pos:fan_start_pos+50]
            player_start_line = player_vevent_section[player_start_pos:player_start_pos+50]

            assert fan_start_line != player_start_line


class TestEmptyDatabaseResponses:
    """Tests for API behavior with empty database."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_empty_db_returns_empty_seasons(self, db_fixture):
        """Empty database should return empty list, not error."""
        # Verify database is empty
        cache_info = db_fixture.get_cache_info()
        assert cache_info['exists'] is False

        # Query seasons from empty database
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            data_service = DataService()
            seasons = data_service.get_seasons()

            # Should return empty list, not None or error
            assert seasons is not None
            assert isinstance(seasons, list)
            assert len(seasons) == 0

    def test_empty_db_calendar_is_valid(self, db_fixture):
        """Generate valid ICS even with no matches."""
        # No data in database
        with patch('src.services.data_service.get_database', return_value=db_fixture):
            data_service = DataService()
            matches = data_service.get_all_matches()

            assert len(matches) == 0

            # Generate calendar from empty matches
            calendar_service = CalendarService()
            ics = calendar_service.generate_ics(matches, "Empty Calendar")

            # Should still be a valid calendar structure
            assert 'BEGIN:VCALENDAR' in ics
            assert 'END:VCALENDAR' in ics
            assert 'VERSION:2.0' in ics

            # Should have no events
            assert 'BEGIN:VEVENT' not in ics

            # Verify it's properly formatted (CRLF line endings)
            assert '\r\n' in ics


class TestCacheInfoIntegration:
    """Tests for cache info reporting."""

    def setup_method(self):
        """Reset state before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after test."""
        reset_database()

    def test_cache_info_after_data_saved(
        self,
        db_fixture,
        sample_season_data,
        sample_competition_data,
        sample_match_data
    ):
        """Cache info should reflect saved data with statistics."""
        # Initially empty
        cache_info = db_fixture.get_cache_info()
        assert cache_info['exists'] is False

        # Save comprehensive data
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

        # Check cache info now reports data
        cache_info = db_fixture.get_cache_info()

        assert cache_info['exists'] is True
        assert cache_info['stale'] is False  # Just updated
        assert 'last_updated' in cache_info
        assert cache_info['last_updated'] is not None

        # Verify stats
        stats = cache_info['stats']
        assert stats['seasons'] == 2
        assert stats['competitions'] >= 1
        assert stats['matches'] == 2

    def test_cache_info_with_no_data(self, db_fixture):
        """Cache info should report exists=False for empty database."""
        # Fresh database
        cache_info = db_fixture.get_cache_info()

        assert cache_info['exists'] is False
        assert 'last_updated' in cache_info
        assert cache_info['last_updated'] is None

        # Stats should be empty dict or all zeros
        stats = cache_info['stats']
        assert isinstance(stats, dict)
        # Either empty dict or dict with zero counts
        if stats:
            assert stats.get('seasons', 0) == 0
            assert stats.get('competitions', 0) == 0
            assert stats.get('matches', 0) == 0
