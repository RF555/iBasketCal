"""Tests for RateLimiter class."""

import pytest
import time
import threading
from datetime import datetime

from src.main import RateLimiter


class TestRateLimiter:
    """Tests for RateLimiter functionality."""

    def test_rate_limiter_init_default(self):
        """Initialize with default cooldown."""
        limiter = RateLimiter()
        assert limiter.cooldown_seconds == 300  # Default 5 minutes

    def test_rate_limiter_init_custom(self):
        """Initialize with custom cooldown."""
        limiter = RateLimiter(cooldown_seconds=60)
        assert limiter.cooldown_seconds == 60

    def test_try_acquire_first_request(self):
        """First request is allowed."""
        limiter = RateLimiter(cooldown_seconds=10)

        allowed, wait_seconds = limiter.try_acquire()

        assert allowed is True
        assert wait_seconds == 0

    def test_try_acquire_within_cooldown(self):
        """Second request within cooldown is blocked."""
        limiter = RateLimiter(cooldown_seconds=5)

        # First request - should be allowed
        allowed1, wait1 = limiter.try_acquire()
        assert allowed1 is True

        # Immediate second request - should be blocked
        allowed2, wait2 = limiter.try_acquire()
        assert allowed2 is False
        assert wait2 > 0  # Should have wait time remaining

    def test_try_acquire_returns_wait_seconds(self):
        """Returns remaining wait time when blocked."""
        limiter = RateLimiter(cooldown_seconds=10)

        # First request
        limiter.try_acquire()

        # Second request immediately after
        allowed, wait_seconds = limiter.try_acquire()

        assert allowed is False
        assert wait_seconds > 0
        assert wait_seconds <= 10  # Should be at most the cooldown

    def test_try_acquire_after_cooldown(self):
        """Request allowed after cooldown expires."""
        limiter = RateLimiter(cooldown_seconds=1)  # Short cooldown for testing

        # First request
        allowed1, _ = limiter.try_acquire()
        assert allowed1 is True

        # Wait for cooldown to expire
        time.sleep(1.1)

        # Second request after cooldown
        allowed2, wait2 = limiter.try_acquire()
        assert allowed2 is True
        assert wait2 == 0

    def test_reset_clears_state(self):
        """Reset allows immediate request."""
        limiter = RateLimiter(cooldown_seconds=10)

        # First request
        limiter.try_acquire()

        # Second request - should be blocked
        allowed_before_reset, _ = limiter.try_acquire()
        assert allowed_before_reset is False

        # Reset
        limiter.reset()

        # Should now be allowed
        allowed_after_reset, wait = limiter.try_acquire()
        assert allowed_after_reset is True
        assert wait == 0

    def test_try_acquire_thread_safe(self):
        """Concurrent access works correctly."""
        limiter = RateLimiter(cooldown_seconds=5)
        results = []

        def acquire():
            allowed, wait = limiter.try_acquire()
            results.append((allowed, wait))

        # Create multiple threads trying to acquire
        threads = [threading.Thread(target=acquire) for _ in range(5)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all to complete
        for t in threads:
            t.join()

        # Only one should have been allowed
        allowed_count = sum(1 for allowed, _ in results if allowed)
        assert allowed_count == 1, "Only one thread should acquire the rate limit"

        # Others should have wait times
        blocked = [wait for allowed, wait in results if not allowed]
        assert all(wait > 0 for wait in blocked), "Blocked requests should have wait times"

    def test_multiple_acquisitions_sequence(self):
        """Sequence of requests with various timings."""
        limiter = RateLimiter(cooldown_seconds=2)

        # Request 1 - allowed
        allowed1, wait1 = limiter.try_acquire()
        assert allowed1 is True
        assert wait1 == 0

        # Request 2 - blocked (immediately after)
        allowed2, wait2 = limiter.try_acquire()
        assert allowed2 is False
        assert wait2 > 0

        # Wait part of the cooldown (0.5 seconds)
        time.sleep(0.5)

        # Request 3 - still blocked but less wait time
        allowed3, wait3 = limiter.try_acquire()
        assert allowed3 is False
        assert wait3 > 0
        assert wait3 < wait2  # Less wait time than before

        # Wait for cooldown to expire (need full 2 seconds from request 1)
        time.sleep(1.6)

        # Request 4 - allowed
        allowed4, wait4 = limiter.try_acquire()
        assert allowed4 is True
        assert wait4 == 0
