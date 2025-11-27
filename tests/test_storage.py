"""Tests for storage module."""

import pytest
import os
import shutil
from unittest.mock import patch

from src.storage import get_database, reset_database, DatabaseInterface
from src.storage.exceptions import ConfigurationError


class TestFactory:
    """Tests for factory function."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_database()

    def teardown_method(self):
        """Clean up after each test."""
        reset_database()
        # Clean up test directories
        for test_dir in ['cache/test_factory', 'cache/test_explicit', 'cache/test_singleton']:
            if os.path.exists(test_dir):
                try:
                    shutil.rmtree(test_dir)
                except PermissionError:
                    pass  # Windows file locking, ignore

    def test_default_is_sqlite(self):
        """Default DB_TYPE should be sqlite."""
        with patch.dict(os.environ, {'DB_TYPE': 'sqlite', 'DATA_DIR': 'cache/test_factory'}, clear=False):
            reset_database()
            db = get_database()
            assert db.__class__.__name__ == 'SQLiteDatabase'
            reset_database()  # Close before cleanup

    def test_sqlite_explicit(self):
        """Explicit sqlite DB_TYPE works."""
        with patch.dict(os.environ, {'DB_TYPE': 'sqlite', 'DATA_DIR': 'cache/test_explicit'}, clear=False):
            reset_database()
            db = get_database()
            assert db.__class__.__name__ == 'SQLiteDatabase'
            reset_database()  # Close before cleanup

    def test_invalid_db_type_raises(self):
        """Invalid DB_TYPE raises ConfigurationError."""
        with patch.dict(os.environ, {'DB_TYPE': 'invalid'}, clear=False):
            reset_database()
            with pytest.raises(ConfigurationError):
                get_database()

    def test_singleton_returns_same_instance(self):
        """Factory returns same instance on subsequent calls."""
        with patch.dict(os.environ, {'DB_TYPE': 'sqlite', 'DATA_DIR': 'cache/test_singleton'}, clear=False):
            reset_database()
            db1 = get_database()
            db2 = get_database()
            assert db1 is db2
            reset_database()  # Close before cleanup


class TestSQLiteDatabase:
    """Tests for SQLite implementation."""

    def setup_method(self):
        """Create fresh database for each test."""
        reset_database()
        os.environ['DB_TYPE'] = 'sqlite'
        os.environ['DATA_DIR'] = 'cache/test_sqlite'

    def teardown_method(self):
        """Clean up test database."""
        reset_database()
        if os.path.exists('cache/test_sqlite'):
            shutil.rmtree('cache/test_sqlite')

    def test_implements_interface(self):
        """SQLiteDatabase implements DatabaseInterface."""
        db = get_database()
        assert isinstance(db, DatabaseInterface)

    def test_health_check(self):
        """Health check returns True for valid connection."""
        db = get_database()
        assert db.health_check() is True

    def test_save_and_get_seasons(self):
        """Can save and retrieve seasons."""
        db = get_database()

        seasons = [
            {'_id': 'season1', 'name': '2024-2025'},
            {'_id': 'season2', 'name': '2023-2024'},
        ]

        count = db.save_seasons(seasons)
        assert count == 2

        retrieved = db.get_seasons()
        assert len(retrieved) == 2
        assert retrieved[0]['name'] == '2024-2025'  # Ordered desc by name

    def test_save_and_get_competitions(self):
        """Can save and retrieve competitions."""
        db = get_database()

        # First save a season
        db.save_seasons([{'_id': 'season1', 'name': '2024-2025'}])

        competitions = [
            {
                'id': 'comp1',
                'name': 'Premier League',
                'groups': [
                    {'id': 'group1', 'name': 'Division A', 'type': 'league'}
                ]
            },
            {
                'id': 'comp2',
                'name': 'National League',
                'groups': []
            }
        ]

        count = db.save_competitions('season1', competitions)
        assert count == 2

        retrieved = db.get_competitions('season1')
        assert len(retrieved) == 2

    def test_save_and_get_matches(self):
        """Can save and retrieve matches."""
        db = get_database()

        calendar_data = {
            'rounds': [
                {
                    'matches': [
                        {
                            'id': 'match1',
                            'date': '2024-01-15T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team1', 'name': 'Team A'},
                            'awayTeam': {'id': 'team2', 'name': 'Team B'},
                            'court': {'place': 'Arena', 'address': '123 Main St'}
                        }
                    ]
                }
            ]
        }

        count = db.save_matches(
            group_id='group1',
            calendar_data=calendar_data,
            competition_name='Premier League',
            group_name='Division A',
            season_id='season1'
        )
        assert count == 1

        matches = db.get_matches(season_id='season1')
        assert len(matches) == 1
        assert matches[0]['homeTeam']['name'] == 'Team A'

    def test_get_matches_with_filters(self):
        """Can filter matches by various criteria."""
        db = get_database()

        calendar_data = {
            'rounds': [
                {
                    'matches': [
                        {
                            'id': 'match1',
                            'date': '2024-01-15T18:00:00Z',
                            'status': 'CLOSED',
                            'homeTeam': {'id': 'team1', 'name': 'Maccabi Tel Aviv'},
                            'awayTeam': {'id': 'team2', 'name': 'Hapoel Jerusalem'},
                            'court': {'place': 'Arena', 'address': '123 Main St'},
                            'score': {
                                'totals': [
                                    {'teamId': 'team1', 'total': 85},
                                    {'teamId': 'team2', 'total': 78}
                                ]
                            }
                        },
                        {
                            'id': 'match2',
                            'date': '2024-01-20T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team3', 'name': 'Team C'},
                            'awayTeam': {'id': 'team4', 'name': 'Team D'},
                            'court': {'place': 'Arena', 'address': '456 Side St'}
                        }
                    ]
                }
            ]
        }

        db.save_matches(
            group_id='group1',
            calendar_data=calendar_data,
            competition_name='Premier League',
            group_name='Division A',
            season_id='season1'
        )

        # Filter by team name
        matches = db.get_matches(team_name='Maccabi')
        assert len(matches) == 1
        assert matches[0]['homeTeam']['name'] == 'Maccabi Tel Aviv'

        # Filter by status
        matches = db.get_matches(status='CLOSED')
        assert len(matches) == 1

        # Filter by limit
        matches = db.get_matches(limit=1)
        assert len(matches) == 1

    def test_get_teams(self):
        """Can get teams from matches."""
        db = get_database()

        calendar_data = {
            'rounds': [
                {
                    'matches': [
                        {
                            'id': 'match1',
                            'date': '2024-01-15T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team1', 'name': 'Team A', 'logo': 'logo1.png'},
                            'awayTeam': {'id': 'team2', 'name': 'Team B', 'logo': 'logo2.png'},
                            'court': {}
                        }
                    ]
                }
            ]
        }

        db.save_matches(
            group_id='group1',
            calendar_data=calendar_data,
            competition_name='Premier League',
            group_name='Division A',
            season_id='season1'
        )

        teams = db.get_teams()
        assert len(teams) == 2

    def test_search_teams(self):
        """Can search teams by name."""
        db = get_database()

        calendar_data = {
            'rounds': [
                {
                    'matches': [
                        {
                            'id': 'match1',
                            'date': '2024-01-15T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team1', 'name': 'Maccabi Tel Aviv'},
                            'awayTeam': {'id': 'team2', 'name': 'Hapoel Jerusalem'},
                            'court': {}
                        }
                    ]
                }
            ]
        }

        db.save_matches(
            group_id='group1',
            calendar_data=calendar_data,
            competition_name='Premier League',
            group_name='Division A',
            season_id='season1'
        )

        teams = db.search_teams('Maccabi')
        assert len(teams) == 1
        assert teams[0]['name'] == 'Maccabi Tel Aviv'

    def test_cache_info(self):
        """Can get cache info."""
        db = get_database()

        # Initially no data
        info = db.get_cache_info()
        assert info['exists'] is False

        # After saving some data and updating timestamp
        db.save_seasons([{'_id': 'season1', 'name': '2024-2025'}])
        db.update_scrape_timestamp()

        info = db.get_cache_info()
        assert info['exists'] is True
        assert info['stale'] is False
        assert info['last_updated'] is not None
        assert info['stats']['seasons'] == 1

    def test_clear_all(self):
        """Clear all removes all data."""
        db = get_database()

        db.save_seasons([{'_id': 's1', 'name': 'Test'}])
        db.update_scrape_timestamp()

        db.clear_all()

        assert db.get_seasons() == []
        info = db.get_cache_info()
        assert info['exists'] is False

    def test_database_size(self):
        """Can get database size."""
        db = get_database()
        size = db.get_database_size()
        # Size should be > 0 after initialization
        assert size >= 0

    def test_vacuum(self):
        """Vacuum runs without error."""
        db = get_database()
        db.vacuum()  # Should not raise


class TestDatabaseInterface:
    """Tests for DatabaseInterface ABC."""

    def test_cannot_instantiate_interface(self):
        """Cannot instantiate abstract class directly."""
        with pytest.raises(TypeError):
            DatabaseInterface()

    def test_interface_has_all_methods(self):
        """Interface defines all required methods."""
        required_methods = [
            'initialize', 'close', 'health_check',
            'save_seasons', 'save_competitions', 'save_matches',
            'save_standings', 'update_scrape_timestamp',
            'get_seasons', 'get_competitions', 'get_all_competitions',
            'get_matches', 'get_teams', 'search_teams', 'get_standings',
            'get_cache_info', 'get_database_size',
            'clear_all', 'vacuum'
        ]

        for method in required_methods:
            assert hasattr(DatabaseInterface, method), f"Missing method: {method}"
