"""Tests for ICS calendar generation."""

import pytest
from datetime import datetime, timezone, timedelta

from src.utils.ics import ICSBuilder
from src.services.calendar import CalendarService
from src.models.match import Match, Team, Score, Court


class TestICSBuilder:
    """Tests for ICSBuilder."""

    def test_escape_text(self):
        """Test escaping special characters."""
        assert ICSBuilder.escape_text("Hello, World") == "Hello\\, World"
        assert ICSBuilder.escape_text("Test;Value") == "Test\\;Value"
        assert ICSBuilder.escape_text("Back\\slash") == "Back\\\\slash"
        assert ICSBuilder.escape_text("Line\nBreak") == "Line\\nBreak"
        assert ICSBuilder.escape_text("") == ""

    def test_format_datetime(self):
        """Test datetime formatting."""
        dt = datetime(2025, 10, 15, 19, 0, 0)
        formatted = ICSBuilder.format_datetime(dt)

        assert formatted == "20251015T190000Z"

    def test_generate_uid(self):
        """Test UID generation."""
        uid = ICSBuilder.generate_uid("match123", "example.com")

        assert uid == "match123@example.com"

    def test_build_empty_calendar(self):
        """Test building calendar with no events."""
        builder = ICSBuilder(calendar_name="Test Calendar")
        ics = builder.build()

        assert "BEGIN:VCALENDAR" in ics
        assert "END:VCALENDAR" in ics
        assert "VERSION:2.0" in ics
        assert "X-WR-CALNAME:Test Calendar" in ics
        assert "BEGIN:VTIMEZONE" in ics
        # No events
        assert "BEGIN:VEVENT" not in ics

    def test_add_event(self):
        """Test adding an event."""
        builder = ICSBuilder()
        builder.add_event(
            uid="test@example.com",
            summary="Test Event",
            dtstart=datetime(2025, 10, 15, 19, 0, 0),
            dtend=datetime(2025, 10, 15, 21, 0, 0),
            location="Test Location",
            description="Test Description",
        )

        ics = builder.build()

        assert "BEGIN:VEVENT" in ics
        assert "END:VEVENT" in ics
        assert "UID:test@example.com" in ics
        assert "SUMMARY:Test Event" in ics
        assert "LOCATION:Test Location" in ics
        assert "DESCRIPTION:Test Description" in ics
        assert "DTSTART:20251015T190000Z" in ics
        assert "DTEND:20251015T210000Z" in ics

    def test_fold_long_line(self):
        """Test line folding for long lines."""
        long_text = "A" * 100
        folded = ICSBuilder.fold_line(f"SUMMARY:{long_text}")

        # Should be split across multiple lines
        lines = folded.split("\r\n")
        assert len(lines) > 1
        # Continuation lines start with space
        assert all(line.startswith(" ") for line in lines[1:])

    def test_crlf_line_endings(self):
        """Test that ICS uses CRLF line endings."""
        builder = ICSBuilder()
        ics = builder.build()

        # Should contain CRLF
        assert "\r\n" in ics
        # Should not have standalone LF (except within CRLF)
        assert ics.replace("\r\n", "").count("\n") == 0


class TestCalendarService:
    """Tests for CalendarService."""

    @pytest.fixture
    def service(self):
        """Create a test service."""
        return CalendarService(base_url="test.local")

    @pytest.fixture
    def sample_match(self):
        """Create a sample match."""
        return Match(
            id="match123",
            date=datetime(2025, 10, 15, 19, 0, 0, tzinfo=timezone.utc),
            status="NOT_STARTED",
            homeTeam=Team(id="team1", name="מכבי תל אביב", logo=None),
            awayTeam=Team(id="team2", name="הפועל ירושלים", logo=None),
            score=None,
            court=Court(place="היכל התרבות", town="תל אביב", address=None),
            competition_name="ליגת על",
            group_name="רגילה",
        )

    def test_generate_ics_empty(self, service):
        """Test generating ICS with no matches."""
        ics = service.generate_ics([], "Test Calendar")

        assert "BEGIN:VCALENDAR" in ics
        assert "BEGIN:VEVENT" not in ics

    def test_generate_ics_with_match(self, service, sample_match):
        """Test generating ICS with a match."""
        ics = service.generate_ics([sample_match], "Test Calendar")

        assert "BEGIN:VEVENT" in ics
        assert "מכבי תל אביב vs הפועל ירושלים" in ics
        assert "היכל התרבות" in ics

    def test_generate_calendar_name(self, service):
        """Test calendar name generation."""
        name = service.generate_calendar_name()
        assert "כדורסל ישראלי" in name

        name = service.generate_calendar_name(competition="ליגת על")
        assert "ליגת על" in name

        name = service.generate_calendar_name(team="מכבי")
        assert "מכבי" in name

    def test_match_title_upcoming(self, service, sample_match):
        """Test match title for upcoming game."""
        title = sample_match.get_title()
        assert "vs" in title
        assert "מכבי תל אביב" in title
        assert "הפועל ירושלים" in title

    def test_match_title_finished(self, service, sample_match):
        """Test match title for finished game."""
        from src.models.match import ScoreTotal

        sample_match.status = "CLOSED"
        sample_match.score = Score(
            totals=[
                ScoreTotal(teamId="team1", total=85),
                ScoreTotal(teamId="team2", total=78),
            ]
        )

        title = sample_match.get_title()
        assert "85" in title
        assert "78" in title
        assert "vs" not in title
