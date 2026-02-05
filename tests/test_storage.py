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

    def test_get_matches_with_team_id_filter(self):
        """Can filter matches by team_id (exact ID match)."""
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
                            'court': {}
                        },
                        {
                            'id': 'match2',
                            'date': '2024-01-16T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team2', 'name': 'Team B'},
                            'awayTeam': {'id': 'team3', 'name': 'Team C'},
                            'court': {}
                        },
                        {
                            'id': 'match3',
                            'date': '2024-01-17T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team3', 'name': 'Team C'},
                            'awayTeam': {'id': 'team4', 'name': 'Team D'},
                            'court': {}
                        }
                    ]
                }
            ]
        }

        db.save_matches(
            group_id='group1',
            calendar_data=calendar_data,
            competition_name='League',
            group_name='Division A',
            season_id='season1'
        )

        # Filter by team_id for home team
        matches = db.get_matches(team_id='team1')
        assert len(matches) == 1
        assert matches[0]['id'] == 'match1'

        # Filter by team_id for team that plays both home and away
        matches = db.get_matches(team_id='team2')
        assert len(matches) == 2
        match_ids = [m['id'] for m in matches]
        assert 'match1' in match_ids
        assert 'match2' in match_ids

        # Filter by team_id for away team only
        matches = db.get_matches(team_id='team4')
        assert len(matches) == 1
        assert matches[0]['id'] == 'match3'

    def test_team_id_takes_precedence_over_team_name(self):
        """team_id filter takes precedence over team_name when both provided."""
        db = get_database()

        calendar_data = {
            'rounds': [
                {
                    'matches': [
                        {
                            'id': 'match1',
                            'date': '2024-01-15T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team1', 'name': 'Maccabi'},
                            'awayTeam': {'id': 'team2', 'name': 'Hapoel'},
                            'court': {}
                        },
                        {
                            'id': 'match2',
                            'date': '2024-01-16T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team3', 'name': 'Other Team'},
                            'awayTeam': {'id': 'team4', 'name': 'Another Team'},
                            'court': {}
                        }
                    ]
                }
            ]
        }

        db.save_matches(
            group_id='group1',
            calendar_data=calendar_data,
            competition_name='League',
            group_name='Division A',
            season_id='season1'
        )

        # When both team_id and team_name provided, team_id should take precedence
        # team_id='team3' should find match2, even though team_name='Maccabi' would find match1
        matches = db.get_matches(team_id='team3', team_name='Maccabi')
        assert len(matches) == 1
        assert matches[0]['id'] == 'match2'

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

    def test_get_teams_by_group(self):
        """Can get teams for a specific competition group."""
        db = get_database()

        # Create matches in two different groups
        calendar_data_group1 = {
            'rounds': [
                {
                    'matches': [
                        {
                            'id': 'match1',
                            'date': '2024-01-15T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team1', 'name': 'Team A', 'logo': 'a.png'},
                            'awayTeam': {'id': 'team2', 'name': 'Team B', 'logo': 'b.png'},
                            'court': {}
                        }
                    ]
                }
            ]
        }

        calendar_data_group2 = {
            'rounds': [
                {
                    'matches': [
                        {
                            'id': 'match2',
                            'date': '2024-01-16T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team3', 'name': 'Team C', 'logo': 'c.png'},
                            'awayTeam': {'id': 'team4', 'name': 'Team D', 'logo': 'd.png'},
                            'court': {}
                        }
                    ]
                }
            ]
        }

        db.save_matches(
            group_id='group1',
            calendar_data=calendar_data_group1,
            competition_name='League 1',
            group_name='Division A',
            season_id='season1'
        )

        db.save_matches(
            group_id='group2',
            calendar_data=calendar_data_group2,
            competition_name='League 2',
            group_name='Division B',
            season_id='season1'
        )

        # Get teams for group1 only
        teams = db.get_teams_by_group('group1')
        assert len(teams) == 2
        team_names = [t['name'] for t in teams]
        assert 'Team A' in team_names
        assert 'Team B' in team_names
        assert 'Team C' not in team_names
        assert 'Team D' not in team_names

        # Get teams for group2 only
        teams = db.get_teams_by_group('group2')
        assert len(teams) == 2
        team_names = [t['name'] for t in teams]
        assert 'Team C' in team_names
        assert 'Team D' in team_names

    def test_get_teams_by_group_empty(self):
        """get_teams_by_group returns empty list for nonexistent group."""
        db = get_database()
        teams = db.get_teams_by_group('nonexistent_group')
        assert teams == []

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


class TestStandings:
    """Tests for standings operations."""

    def setup_method(self):
        """Create fresh database for each test."""
        reset_database()
        os.environ['DB_TYPE'] = 'sqlite'
        os.environ['DATA_DIR'] = 'cache/test_standings'

    def teardown_method(self):
        """Clean up test database."""
        reset_database()
        if os.path.exists('cache/test_standings'):
            shutil.rmtree('cache/test_standings')

    def test_save_standings(self):
        """Save standings data and verify count returned."""
        db = get_database()

        standings_data = [
            {'teamId': 'team1', 'position': 1, 'wins': 10, 'losses': 2},
            {'teamId': 'team2', 'position': 2, 'wins': 8, 'losses': 4},
            {'teamId': 'team3', 'position': 3, 'wins': 6, 'losses': 6}
        ]

        count = db.save_standings('group1', standings_data)
        assert count == 3

    def test_get_standings_ordered_by_position(self):
        """Standings are returned in position order."""
        db = get_database()

        standings_data = [
            {'teamId': 'team3', 'position': 3, 'wins': 6, 'losses': 6},
            {'teamId': 'team1', 'position': 1, 'wins': 10, 'losses': 2},
            {'teamId': 'team2', 'position': 2, 'wins': 8, 'losses': 4}
        ]

        db.save_standings('group1', standings_data)
        retrieved = db.get_standings('group1')

        assert len(retrieved) == 3
        assert retrieved[0]['position'] == 1
        assert retrieved[1]['position'] == 2
        assert retrieved[2]['position'] == 3

    def test_save_standings_skips_no_team_id(self):
        """Entries without teamId are skipped."""
        db = get_database()

        standings_data = [
            {'teamId': 'team1', 'position': 1, 'wins': 10},
            {'position': 2, 'wins': 8},  # No teamId
            {'teamId': 'team2', 'position': 3, 'wins': 6}
        ]

        count = db.save_standings('group1', standings_data)
        # Only 2 entries have teamId, so count is still 3 (input length)
        # but only 2 are actually saved
        retrieved = db.get_standings('group1')
        assert len(retrieved) == 2

    def test_standings_upsert(self):
        """Saving standings twice updates existing."""
        db = get_database()

        initial_data = [
            {'teamId': 'team1', 'position': 1, 'wins': 10, 'losses': 2}
        ]
        db.save_standings('group1', initial_data)

        updated_data = [
            {'teamId': 'team1', 'position': 1, 'wins': 12, 'losses': 2}
        ]
        db.save_standings('group1', updated_data)

        retrieved = db.get_standings('group1')
        assert len(retrieved) == 1
        assert retrieved[0]['wins'] == 12


class TestAdvancedMatchFilters:
    """Tests for advanced match filtering."""

    def setup_method(self):
        """Create fresh database for each test."""
        reset_database()
        os.environ['DB_TYPE'] = 'sqlite'
        os.environ['DATA_DIR'] = 'cache/test_match_filters'

    def teardown_method(self):
        """Clean up test database."""
        reset_database()
        if os.path.exists('cache/test_match_filters'):
            shutil.rmtree('cache/test_match_filters')

    def _save_test_matches(self, db):
        """Helper to save test matches."""
        calendar_data = {
            'rounds': [
                {
                    'matches': [
                        {
                            'id': 'match1',
                            'date': '2024-01-15T18:00:00Z',
                            'status': 'CLOSED',
                            'homeTeam': {'id': 'team1', 'name': 'Team A'},
                            'awayTeam': {'id': 'team2', 'name': 'Team B'},
                            'court': {},
                            'score': {'totals': []}
                        },
                        {
                            'id': 'match2',
                            'date': '2024-02-20T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team3', 'name': 'Team C'},
                            'awayTeam': {'id': 'team4', 'name': 'Team D'},
                            'court': {}
                        },
                        {
                            'id': 'match3',
                            'date': '2024-03-25T18:00:00Z',
                            'status': 'CLOSED',
                            'homeTeam': {'id': 'team1', 'name': 'Team A'},
                            'awayTeam': {'id': 'team3', 'name': 'Team C'},
                            'court': {}
                        }
                    ]
                }
            ]
        }

        db.save_matches(
            group_id='group1',
            calendar_data=calendar_data,
            competition_name='Test League',
            group_name='Division A',
            season_id='season1'
        )

    def test_get_matches_by_status(self):
        """Filter matches by status."""
        db = get_database()
        self._save_test_matches(db)

        matches = db.get_matches(status='CLOSED')
        assert len(matches) == 2
        for match in matches:
            assert match['status'] == 'CLOSED'

    def test_get_matches_by_date_from(self):
        """Filter matches with date >= value."""
        db = get_database()
        self._save_test_matches(db)

        matches = db.get_matches(date_from='2024-02-01T00:00:00Z')
        assert len(matches) == 2
        assert matches[0]['id'] == 'match2'
        assert matches[1]['id'] == 'match3'

    def test_get_matches_by_date_to(self):
        """Filter matches with date <= value."""
        db = get_database()
        self._save_test_matches(db)

        matches = db.get_matches(date_to='2024-02-01T00:00:00Z')
        assert len(matches) == 1
        assert matches[0]['id'] == 'match1'

    def test_get_matches_by_date_range(self):
        """Filter matches with date_from and date_to combined."""
        db = get_database()
        self._save_test_matches(db)

        matches = db.get_matches(
            date_from='2024-01-10T00:00:00Z',
            date_to='2024-02-25T00:00:00Z'
        )
        assert len(matches) == 2
        assert matches[0]['id'] == 'match1'
        assert matches[1]['id'] == 'match2'

    def test_get_matches_with_limit(self):
        """Limit parameter returns only specified number of matches."""
        db = get_database()
        self._save_test_matches(db)

        matches = db.get_matches(limit=1)
        assert len(matches) == 1

    def test_get_matches_team_id_over_team_name(self):
        """When both team_id and team_name provided, team_id takes precedence."""
        db = get_database()
        self._save_test_matches(db)

        # team_id='team3' should find matches with Team C
        # even though team_name='Team A' would find different matches
        matches = db.get_matches(team_id='team3', team_name='Team A')
        assert len(matches) == 2
        assert matches[0]['id'] == 'match2'
        assert matches[1]['id'] == 'match3'

    def test_get_matches_combined_filters(self):
        """Combined filters: season_id + group_id + status."""
        db = get_database()
        self._save_test_matches(db)

        matches = db.get_matches(
            season_id='season1',
            group_id='group1',
            status='CLOSED'
        )
        assert len(matches) == 2


class TestAllCompetitions:
    """Tests for get_all_competitions method."""

    def setup_method(self):
        """Create fresh database for each test."""
        reset_database()
        os.environ['DB_TYPE'] = 'sqlite'
        os.environ['DATA_DIR'] = 'cache/test_all_competitions'

    def teardown_method(self):
        """Clean up test database."""
        reset_database()
        if os.path.exists('cache/test_all_competitions'):
            shutil.rmtree('cache/test_all_competitions')

    def test_get_all_competitions_returns_season_id(self):
        """Each competition has _season_id field."""
        db = get_database()

        # Save seasons
        db.save_seasons([
            {'_id': 'season1', 'name': '2024-2025'},
            {'_id': 'season2', 'name': '2023-2024'}
        ])

        # Save competitions for season1
        db.save_competitions('season1', [
            {
                'id': 'comp1',
                'name': 'Premier League',
                'groups': [{'id': 'g1', 'name': 'Division A', 'type': 'league'}]
            }
        ])

        # Save competitions for season2
        db.save_competitions('season2', [
            {
                'id': 'comp2',
                'name': 'National League',
                'groups': [{'id': 'g2', 'name': 'Group A', 'type': 'league'}]
            }
        ])

        all_comps = db.get_all_competitions()
        assert len(all_comps) == 2

        for comp in all_comps:
            assert '_season_id' in comp
            assert comp['_season_id'] in ['season1', 'season2']

    def test_get_all_competitions_across_seasons(self):
        """Returns competitions from multiple seasons."""
        db = get_database()

        # Save seasons
        db.save_seasons([
            {'_id': 'season1', 'name': '2024-2025'},
            {'_id': 'season2', 'name': '2023-2024'}
        ])

        # Save competitions for both seasons
        db.save_competitions('season1', [
            {'id': 'comp1', 'name': 'League A', 'groups': []}
        ])
        db.save_competitions('season2', [
            {'id': 'comp2', 'name': 'League B', 'groups': []}
        ])

        all_comps = db.get_all_competitions()
        assert len(all_comps) == 2
        names = [c['name'] for c in all_comps]
        assert 'League A' in names
        assert 'League B' in names


class TestCacheAndMaintenance:
    """Tests for cache info and maintenance operations."""

    def setup_method(self):
        """Create fresh database for each test."""
        reset_database()
        os.environ['DB_TYPE'] = 'sqlite'
        os.environ['DATA_DIR'] = 'cache/test_cache'

    def teardown_method(self):
        """Clean up test database."""
        reset_database()
        if os.path.exists('cache/test_cache'):
            shutil.rmtree('cache/test_cache')

    def test_update_scrape_timestamp(self):
        """After calling update_scrape_timestamp, cache info shows exists=True."""
        db = get_database()

        # Initially no scrape timestamp
        info = db.get_cache_info()
        assert info['exists'] is False

        # Update timestamp
        db.update_scrape_timestamp()

        # Now exists
        info = db.get_cache_info()
        assert info['exists'] is True
        assert info['last_updated'] is not None

    def test_get_cache_info_stale_detection(self):
        """Cache is marked as stale when TTL exceeded."""
        db = get_database()

        # Save a scrape timestamp that's old (in the past)
        from datetime import datetime, timezone, timedelta
        old_timestamp = datetime.now(timezone.utc) - timedelta(minutes=10)

        with db.transaction() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO metadata (key, value, updated_at)
                VALUES ('last_scrape', ?, CURRENT_TIMESTAMP)
            ''', (old_timestamp.isoformat(),))

        # Now check with a TTL of 5 minutes - the 10-minute-old cache should be stale
        with patch('src.storage.sqlite_db.config.CACHE_TTL_MINUTES', 5):
            info = db.get_cache_info()
            assert info['stale'] is True
            assert info['age_minutes'] >= 10

    def test_get_cache_info_not_stale(self):
        """Recently scraped cache is not stale."""
        db = get_database()

        # Mock a very long TTL
        with patch('src.config.CACHE_TTL_MINUTES', 99999):
            db.update_scrape_timestamp()
            info = db.get_cache_info()
            assert info['stale'] is False

    def test_get_cache_info_stats(self):
        """Cache info includes stats for all tables."""
        db = get_database()

        # Save some data
        db.save_seasons([{'_id': 's1', 'name': '2024-2025'}])
        db.save_competitions('s1', [
            {'id': 'c1', 'name': 'League', 'groups': [{'id': 'g1', 'name': 'A', 'type': 'league'}]}
        ])
        db.update_scrape_timestamp()

        info = db.get_cache_info()
        assert 'stats' in info
        assert info['stats']['seasons'] == 1
        assert info['stats']['competitions'] == 1
        assert info['stats']['groups'] >= 1

    def test_get_database_size_returns_positive(self):
        """After data saved, database size > 0."""
        db = get_database()

        db.save_seasons([{'_id': 's1', 'name': 'Test'}])

        size = db.get_database_size()
        assert size > 0

    def test_get_database_size_nonexistent_file(self):
        """Returns 0 for nonexistent database file."""
        db = get_database()

        # Create a new instance with nonexistent path
        from src.storage.sqlite_db import SQLiteDatabase
        fake_db = SQLiteDatabase(db_path='cache/nonexistent/fake.db')

        size = fake_db.get_database_size()
        assert size == 0

    def test_clear_all_removes_data(self):
        """After clear_all, all tables are empty."""
        db = get_database()

        # Add data
        db.save_seasons([{'_id': 's1', 'name': '2024'}])
        db.save_competitions('s1', [{'id': 'c1', 'name': 'League', 'groups': []}])
        db.update_scrape_timestamp()

        # Verify data exists
        assert len(db.get_seasons()) > 0
        assert db.get_cache_info()['exists'] is True

        # Clear all
        db.clear_all()

        # Verify empty
        assert len(db.get_seasons()) == 0
        assert len(db.get_competitions('s1')) == 0
        assert db.get_cache_info()['exists'] is False

    def test_vacuum_runs_without_error(self):
        """Vacuum operation completes successfully."""
        db = get_database()

        # Add some data
        db.save_seasons([{'_id': 's1', 'name': 'Test'}])

        # Vacuum should not raise
        db.vacuum()


class TestExceptionHierarchy:
    """Tests for storage exception hierarchy."""

    def test_database_error_is_exception(self):
        """DatabaseError inherits from Exception."""
        from src.storage.exceptions import DatabaseError
        assert issubclass(DatabaseError, Exception)

    def test_connection_error_inherits_database_error(self):
        """ConnectionError inherits from DatabaseError."""
        from src.storage.exceptions import DatabaseError, ConnectionError as StorageConnectionError
        assert issubclass(StorageConnectionError, DatabaseError)

    def test_configuration_error_inherits_database_error(self):
        """ConfigurationError inherits from DatabaseError."""
        from src.storage.exceptions import DatabaseError, ConfigurationError
        assert issubclass(ConfigurationError, DatabaseError)

    def test_schema_error_inherits_database_error(self):
        """SchemaError inherits from DatabaseError."""
        from src.storage.exceptions import DatabaseError, SchemaError
        assert issubclass(SchemaError, DatabaseError)

    def test_query_error_inherits_database_error(self):
        """QueryError inherits from DatabaseError."""
        from src.storage.exceptions import DatabaseError, QueryError
        assert issubclass(QueryError, DatabaseError)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def setup_method(self):
        """Create fresh database for each test."""
        reset_database()
        os.environ['DB_TYPE'] = 'sqlite'
        os.environ['DATA_DIR'] = 'cache/test_edge_cases'

    def teardown_method(self):
        """Clean up test database."""
        reset_database()
        if os.path.exists('cache/test_edge_cases'):
            shutil.rmtree('cache/test_edge_cases')

    def test_save_matches_with_hebrew_names(self):
        """Unicode Hebrew team names are saved and retrieved correctly."""
        db = get_database()

        calendar_data = {
            'rounds': [
                {
                    'matches': [
                        {
                            'id': 'match1',
                            'date': '2024-01-15T18:00:00Z',
                            'status': 'NOT_STARTED',
                            'homeTeam': {'id': 'team1', 'name': 'מכבי תל אביב'},
                            'awayTeam': {'id': 'team2', 'name': 'הפועל ירושלים'},
                            'court': {'place': 'מנורה מבטחים', 'address': 'יגאל אלון 51'}
                        }
                    ]
                }
            ]
        }

        count = db.save_matches(
            group_id='group1',
            calendar_data=calendar_data,
            competition_name='ליגת העל',
            group_name='בית א',
            season_id='season1'
        )
        assert count == 1

        matches = db.get_matches()
        assert len(matches) == 1
        assert matches[0]['homeTeam']['name'] == 'מכבי תל אביב'
        assert matches[0]['awayTeam']['name'] == 'הפועל ירושלים'
        assert matches[0]['_competition'] == 'ליגת העל'

    def test_save_empty_seasons(self):
        """Saving empty list returns 0."""
        db = get_database()

        count = db.save_seasons([])
        assert count == 0

        seasons = db.get_seasons()
        assert seasons == []

    def test_transaction_rollback_on_error(self):
        """Data not committed if exception occurs in transaction."""
        db = get_database()

        # Save initial data
        db.save_seasons([{'_id': 's1', 'name': 'Season 1'}])
        assert len(db.get_seasons()) == 1

        # Try to cause an error during transaction
        try:
            with db.transaction() as conn:
                # This should work
                conn.execute(
                    "INSERT INTO seasons (id, name, data) VALUES (?, ?, ?)",
                    ('s2', 'Season 2', '{}')
                )
                # Force an error to trigger rollback
                conn.execute("INSERT INTO nonexistent_table VALUES (?)", ('test',))
        except Exception:
            pass  # Expected

        # Only original season should exist (transaction rolled back)
        seasons = db.get_seasons()
        assert len(seasons) == 1
        assert seasons[0]['_id'] == 's1'


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
            'get_matches', 'get_teams', 'get_teams_by_group', 'search_teams', 'get_standings',
            'get_cache_info', 'get_database_size',
            'clear_all', 'vacuum'
        ]

        for method in required_methods:
            assert hasattr(DatabaseInterface, method), f"Missing method: {method}"
