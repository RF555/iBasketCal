"""
Shared test fixtures and configuration.

Provides reusable fixtures for all test files including database instances,
sample data, mocked scrapers, and FastAPI test clients.
"""

import pytest
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from src.storage import get_database, reset_database
from src.services.data_service import DataService
from src.services.calendar_service import CalendarService
from src.scraper.nbn23_scraper import NBN23Scraper

# For FastAPI testing
try:
    from httpx import AsyncClient
    from src.main import app
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture
def test_data_dir():
    """Provide a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp(prefix="ibasketcal_test_")
    yield temp_dir

    # Cleanup
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass  # Windows file locking, ignore


@pytest.fixture
def db_fixture(test_data_dir):
    """Provide a clean test database instance."""
    with patch.dict(os.environ, {'DB_TYPE': 'sqlite', 'DATA_DIR': test_data_dir}, clear=False):
        reset_database()
        db = get_database()
        yield db
        reset_database()  # Close connection before cleanup


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_season_data() -> List[Dict[str, Any]]:
    """Provide sample season data."""
    return [
        {
            '_id': 'season_2024_2025',
            'name': '2024-2025',
            'startDate': '2024-09-01',
            'endDate': '2025-06-30'
        },
        {
            '_id': 'season_2023_2024',
            'name': '2023-2024',
            'startDate': '2023-09-01',
            'endDate': '2024-06-30'
        }
    ]


@pytest.fixture
def sample_competition_data() -> List[Dict[str, Any]]:
    """Provide sample competition data."""
    return [
        {
            'id': 'comp_premier',
            'name': 'Premier League',
            'groups': [
                {
                    'id': 'group_premier_a',
                    'name': 'Division A',
                    'type': 'league'
                }
            ]
        },
        {
            'id': 'comp_national',
            'name': 'National League',
            'groups': [
                {
                    'id': 'group_national_a',
                    'name': 'Group A',
                    'type': 'league'
                }
            ]
        }
    ]


@pytest.fixture
def sample_match_data() -> Dict[str, Any]:
    """Provide sample match calendar data."""
    return {
        'rounds': [
            {
                'roundNumber': 1,
                'matches': [
                    {
                        'id': 'match_001',
                        'date': '2024-10-15T18:00:00Z',
                        'status': 'NOT_STARTED',
                        'homeTeam': {
                            'id': 'team_maccabi_ta',
                            'name': 'Maccabi Tel Aviv',
                            'logo': 'maccabi_logo.png'
                        },
                        'awayTeam': {
                            'id': 'team_hapoel_js',
                            'name': 'Hapoel Jerusalem',
                            'logo': 'hapoel_logo.png'
                        },
                        'court': {
                            'place': 'Menora Mivtachim Arena',
                            'town': 'Tel Aviv',
                            'address': 'Yigal Alon 51'
                        }
                    },
                    {
                        'id': 'match_002',
                        'date': '2024-10-20T20:00:00Z',
                        'status': 'CLOSED',
                        'homeTeam': {
                            'id': 'team_hapoel_ta',
                            'name': 'Hapoel Tel Aviv',
                            'logo': 'hapoel_ta_logo.png'
                        },
                        'awayTeam': {
                            'id': 'team_maccabi_haifa',
                            'name': 'Maccabi Haifa',
                            'logo': 'maccabi_haifa_logo.png'
                        },
                        'court': {
                            'place': 'Drive In Arena',
                            'town': 'Tel Aviv',
                            'address': 'Rokach Blvd'
                        },
                        'score': {
                            'totals': [
                                {'teamId': 'team_hapoel_ta', 'total': 85},
                                {'teamId': 'team_maccabi_haifa', 'total': 78}
                            ]
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_team_data() -> List[Dict[str, Any]]:
    """Provide sample team data."""
    return [
        {
            'id': 'team_maccabi_ta',
            'name': 'Maccabi Tel Aviv',
            'logo': 'maccabi_logo.png'
        },
        {
            'id': 'team_hapoel_js',
            'name': 'Hapoel Jerusalem',
            'logo': 'hapoel_logo.png'
        },
        {
            'id': 'team_hapoel_ta',
            'name': 'Hapoel Tel Aviv',
            'logo': 'hapoel_ta_logo.png'
        }
    ]


# =============================================================================
# MOCK SCRAPER FIXTURE
# =============================================================================

@pytest.fixture
def mock_scraper():
    """Provide a mock NBN23Scraper for testing."""
    # Use MagicMock to allow any attribute access
    from unittest.mock import MagicMock
    scraper = MagicMock()

    # Mock scrape method to do nothing
    scraper.scrape.return_value = None

    return scraper


# =============================================================================
# FASTAPI TEST CLIENT FIXTURES
# =============================================================================

if HTTPX_AVAILABLE:
    @pytest.fixture
    async def async_test_client():
        """Provide an async test client for FastAPI endpoints."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client


    @pytest.fixture
    def test_app():
        """Provide the FastAPI app instance for testing."""
        return app
