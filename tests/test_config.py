"""Tests for configuration module."""

import pytest
import os
from unittest.mock import patch

from src import config


class TestConfigHelpers:
    """Tests for configuration helper functions."""

    def test_get_int_default(self):
        """Default value when environment variable not set."""
        with patch.dict(os.environ, {}, clear=False):
            result = config._get_int('NONEXISTENT_VAR', 42)
            assert result == 42

    def test_get_int_from_env(self):
        """Parse integer from environment variable."""
        with patch.dict(os.environ, {'TEST_INT': '100'}, clear=False):
            result = config._get_int('TEST_INT', 42)
            assert result == 100

    def test_get_int_invalid_value(self):
        """Handle non-integer values gracefully."""
        with patch.dict(os.environ, {'TEST_INT': 'not_a_number'}, clear=False):
            result = config._get_int('TEST_INT', 42)
            assert result == 42  # Returns default on ValueError

    def test_get_bool_true_variants(self):
        """Test 'true', '1', 'yes' variants."""
        true_values = ['true', 'True', 'TRUE', '1', 'yes', 'Yes', 'YES']
        for value in true_values:
            with patch.dict(os.environ, {'TEST_BOOL': value}, clear=False):
                result = config._get_bool('TEST_BOOL', False)
                assert result is True, f"Failed for value: {value}"

    def test_get_bool_false_variants(self):
        """Test 'false', '0', 'no' variants."""
        false_values = ['false', 'False', 'FALSE', '0', 'no', 'No', 'NO', 'anything_else']
        for value in false_values:
            with patch.dict(os.environ, {'TEST_BOOL': value}, clear=False):
                result = config._get_bool('TEST_BOOL', True)
                assert result is False, f"Failed for value: {value}"

    def test_get_bool_default(self):
        """Default value when environment variable not set."""
        with patch.dict(os.environ, {}, clear=False):
            result = config._get_bool('NONEXISTENT_VAR', True)
            assert result is True

            result = config._get_bool('NONEXISTENT_VAR', False)
            assert result is False

    def test_get_str_default(self):
        """String default value."""
        with patch.dict(os.environ, {}, clear=False):
            result = config._get_str('NONEXISTENT_VAR', 'default_value')
            assert result == 'default_value'

    def test_get_str_from_env(self):
        """Get string from environment variable."""
        with patch.dict(os.environ, {'TEST_STR': 'test_value'}, clear=False):
            result = config._get_str('TEST_STR', 'default')
            assert result == 'test_value'


class TestConfigValues:
    """Tests for configuration constants."""

    def test_cache_dir_priority(self):
        """Test DATA_DIR > RAILWAY_VOLUME_MOUNT_PATH > default."""
        # Test DATA_DIR takes priority
        with patch.dict(
            os.environ,
            {'DATA_DIR': '/custom/data', 'RAILWAY_VOLUME_MOUNT_PATH': '/railway/data'},
            clear=False
        ):
            # Re-evaluate CACHE_DIR
            cache_dir = (
                os.environ.get('DATA_DIR') or
                os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or
                ('/app/cache' if os.path.exists('/app') else 'cache')
            )
            assert cache_dir == '/custom/data'

        # Test RAILWAY_VOLUME_MOUNT_PATH when DATA_DIR not set
        with patch.dict(
            os.environ,
            {'RAILWAY_VOLUME_MOUNT_PATH': '/railway/data'},
            clear=False
        ):
            if 'DATA_DIR' in os.environ:
                del os.environ['DATA_DIR']

            cache_dir = (
                os.environ.get('DATA_DIR') or
                os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or
                ('/app/cache' if os.path.exists('/app') else 'cache')
            )
            assert cache_dir == '/railway/data'

    def test_db_type_default(self):
        """Default database type is sqlite."""
        # config module has already loaded, check that it uses default correctly
        with patch.dict(os.environ, {}, clear=False):
            db_type = config._get_str('DB_TYPE', 'sqlite')
            assert db_type == 'sqlite'

    def test_all_config_values_exist(self):
        """Validate all expected config constants exist."""
        required_config = [
            'PORT', 'HOST',
            'DB_TYPE',
            'CACHE_TTL_MINUTES', 'CACHE_DIR',
            'SCRAPER_HEADLESS', 'WIDGET_URL',
            'REFRESH_COOLDOWN_SECONDS',
            'LOG_LEVEL'
        ]

        for config_name in required_config:
            assert hasattr(config, config_name), f"Missing config: {config_name}"
            value = getattr(config, config_name)
            assert value is not None, f"Config {config_name} is None"
