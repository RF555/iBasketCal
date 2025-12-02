"""Tests for CalendarService - ICS generation."""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any

from src.services.calendar_service import CalendarService


class TestCalendarServiceBasic:
    """Basic calendar generation tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_generate_ics_basic(self):
        """Generate simple calendar."""
        matches = [
            {
                'id': 'match1',
                'date': '2024-10-15T18:00:00Z',
                'status': 'NOT_STARTED',
                'homeTeam': {'id': 'team1', 'name': 'Team A'},
                'awayTeam': {'id': 'team2', 'name': 'Team B'},
                'court': {'place': 'Arena'}
            }
        ]

        ics = self.service.generate_ics(matches)

        assert 'BEGIN:VCALENDAR' in ics
        assert 'END:VCALENDAR' in ics
        assert 'BEGIN:VEVENT' in ics
        assert 'END:VEVENT' in ics

    def test_generate_ics_with_custom_name(self):
        """Custom calendar name."""
        matches = []
        calendar_name = "My Custom Basketball Calendar"

        ics = self.service.generate_ics(matches, calendar_name)

        assert 'X-WR-CALNAME:My Custom Basketball Calendar' in ics

    def test_generate_ics_empty_matches(self):
        """Handle empty match list."""
        ics = self.service.generate_ics([])

        assert 'BEGIN:VCALENDAR' in ics
        assert 'END:VCALENDAR' in ics
        # Should have no VEVENT blocks
        assert ics.count('BEGIN:VEVENT') == 0

    def test_generate_ics_includes_vcalendar_headers(self):
        """Valid ICS headers."""
        ics = self.service.generate_ics([])

        required_headers = [
            'VERSION:2.0',
            'PRODID:-//Israeli Basketball Calendar//ibasketcal//EN',
            'CALSCALE:GREGORIAN',
            'METHOD:PUBLISH',
            'X-WR-TIMEZONE:Asia/Jerusalem'
        ]

        for header in required_headers:
            assert header in ics, f"Missing header: {header}"

    def test_generate_ics_includes_timezone(self):
        """Timezone component present."""
        ics = self.service.generate_ics([])

        assert 'BEGIN:VTIMEZONE' in ics
        assert 'TZID:Asia/Jerusalem' in ics
        assert 'END:VTIMEZONE' in ics


class TestMatchToVEvent:
    """Tests for match conversion to VEVENT."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_generate_ics_match_to_vevent(self):
        """Match converted to VEVENT."""
        matches = [
            {
                'id': 'match123',
                'date': '2024-10-15T18:00:00Z',
                'status': 'NOT_STARTED',
                'homeTeam': {'id': 'team1', 'name': 'Home Team'},
                'awayTeam': {'id': 'team2', 'name': 'Away Team'},
                'court': {'place': 'Test Arena'}
            }
        ]

        ics = self.service.generate_ics(matches)

        assert 'UID:match123@ibasketball.calendar' in ics
        assert 'SUMMARY:Home Team vs Away Team' in ics
        assert 'LOCATION:Test Arena' in ics

    def test_vevent_uid_generation(self):
        """Stable UID generation."""
        match = {
            'id': 'stable_id_123',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        ics = self.service.generate_ics([match])

        assert 'UID:stable_id_123@ibasketball.calendar' in ics

    def test_vevent_dtstart_dtend_format(self):
        """Date/time formatting."""
        match = {
            'id': 'm1',
            'date': '2024-12-25T20:30:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        ics = self.service.generate_ics([match])

        # Should have UTC timestamps
        assert 'DTSTART:20241225T203000Z' in ics
        # DTEND should be 2 hours later
        assert 'DTEND:20241225T223000Z' in ics

    def test_vevent_summary_not_started(self):
        """Summary for upcoming match."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Maccabi Tel Aviv'},
            'awayTeam': {'id': 't2', 'name': 'Hapoel Jerusalem'},
            'court': {}
        }

        ics = self.service.generate_ics([match])

        assert 'SUMMARY:Maccabi Tel Aviv vs Hapoel Jerusalem' in ics

    def test_vevent_summary_closed_with_scores(self):
        """Summary with final scores."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'status': 'CLOSED',
            'homeTeam': {'id': 'team_home', 'name': 'Home Team'},
            'awayTeam': {'id': 'team_away', 'name': 'Away Team'},
            'court': {},
            'score': {
                'totals': [
                    {'teamId': 'team_home', 'total': 85},
                    {'teamId': 'team_away', 'total': 78}
                ]
            }
        }

        ics = self.service.generate_ics([match])

        # Score should be in parentheses for RTL display
        assert 'SUMMARY:Home Team (85) vs Away Team (78)' in ics

    def test_vevent_summary_live(self):
        """Summary for live match."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'status': 'LIVE',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match])

        assert 'SUMMARY:LIVE: Team A vs Team B' in ics

    def test_vevent_description_includes_metadata(self):
        """Competition/group/season in description."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {},
            '_competition': 'Premier League',
            '_group': 'Division A',
            '_season': '2024-2025',
            'status': 'NOT_STARTED'
        }

        ics = self.service.generate_ics([match])

        # Description should contain metadata (with \\n escaping and line folding)
        assert 'DESCRIPTION:' in ics
        # Remove line folding to check content (folding adds \r\n + space)
        unfolded = ics.replace('\r\n ', '')
        assert 'Competition: Premier League' in unfolded
        assert 'Group: Division A' in unfolded
        assert 'Season: 2024-2025' in unfolded

    def test_vevent_location_formatting(self):
        """Location from court data."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {
                'place': 'Menora Arena',
                'town': 'Tel Aviv',
                'address': 'Yigal Alon 51'
            }
        }

        ics = self.service.generate_ics([match])

        assert 'LOCATION:Menora Arena\\, Tel Aviv\\, Yigal Alon 51' in ics

    def test_vevent_location_missing_data(self):
        """Handle missing court info."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        ics = self.service.generate_ics([match])

        assert 'LOCATION:TBD' in ics


class TestEscaping:
    """Tests for ICS special character escaping."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_escape_special_characters(self):
        """ICS escaping (backslash, semicolon, comma)."""
        assert self.service._escape('test\\backslash') == 'test\\\\backslash'
        assert self.service._escape('test;semicolon') == 'test\\;semicolon'
        assert self.service._escape('test,comma') == 'test\\,comma'

    def test_escape_newlines(self):
        """Newline escaping."""
        assert self.service._escape('line1\nline2') == 'line1\\nline2'
        assert self.service._escape('line1\r\nline2') == 'line1\\nline2'


class TestLineFolding:
    """Tests for RFC 5545 line folding."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_fold_line_short_line(self):
        """No folding for short lines."""
        short_line = "SUMMARY:Short event"
        folded = self.service._fold_line(short_line)

        assert folded == short_line
        assert '\r\n' not in folded

    def test_fold_line_long_line(self):
        """Fold lines > 75 octets."""
        # Create a line longer than 75 bytes
        long_line = "SUMMARY:" + "A" * 100

        folded = self.service._fold_line(long_line)

        # Should be folded
        assert '\r\n' in folded
        # Continuation lines start with space
        assert '\r\n ' in folded

    def test_fold_line_with_unicode(self):
        """Fold lines with Hebrew text."""
        # Hebrew characters are multi-byte in UTF-8
        hebrew_line = "SUMMARY:מכבי תל אביב נגד הפועל ירושלים - משחק חשוב מאוד במסגרת ליגת העל"

        folded = self.service._fold_line(hebrew_line)

        # Should handle multi-byte characters correctly
        # Each line segment should not exceed 75 bytes
        for segment in folded.split('\r\n'):
            # Remove leading space from continuation lines
            check_segment = segment.lstrip(' ')
            assert len(check_segment.encode('utf-8')) <= self.service.MAX_LINE_OCTETS

    def test_fold_line_preserves_content(self):
        """Folding doesn't lose data."""
        long_line = "DESCRIPTION:" + "X" * 200

        folded = self.service._fold_line(long_line)

        # Remove folding (CRLF + space) to get original content
        unfolded = folded.replace('\r\n ', '')

        assert unfolded == long_line


class TestRTLScoreDisplay:
    """Tests for RTL score display formatting."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_rtl_score_display_parentheses(self):
        """Scores in parentheses for RTL."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'status': 'CLOSED',
            'homeTeam': {'id': 'home', 'name': 'מכבי תל אביב'},
            'awayTeam': {'id': 'away', 'name': 'הפועל ירושלים'},
            'court': {},
            'score': {
                'totals': [
                    {'teamId': 'home', 'total': 92},
                    {'teamId': 'away', 'total': 88}
                ]
            }
        }

        ics = self.service.generate_ics([match])

        # Scores should be in parentheses for better RTL display
        assert '(92)' in ics
        assert '(88)' in ics


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_match_with_missing_teams(self):
        """Handle missing team data."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': {},
            'awayTeam': {},
            'court': {}
        }

        ics = self.service.generate_ics([match])

        # Should use TBD for missing teams
        assert 'SUMMARY:TBD vs TBD' in ics

    def test_match_with_invalid_date(self):
        """Handle invalid date formats."""
        match = {
            'id': 'm1',
            'date': 'invalid-date',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        # Should not raise, uses current time as fallback
        ics = self.service.generate_ics([match])
        assert 'BEGIN:VEVENT' in ics

    def test_sequence_number_by_status(self):
        """SEQUENCE increments with status changes."""
        # NOT_STARTED should have SEQUENCE:0
        match_not_started = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        ics = self.service.generate_ics([match_not_started])
        assert 'SEQUENCE:0' in ics

        # CLOSED should have SEQUENCE:1
        match_closed = {
            'id': 'm2',
            'date': '2024-10-15T18:00:00Z',
            'status': 'CLOSED',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        ics = self.service.generate_ics([match_closed])
        assert 'SEQUENCE:1' in ics

        # LIVE should have SEQUENCE:2
        match_live = {
            'id': 'm3',
            'date': '2024-10-15T18:00:00Z',
            'status': 'LIVE',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        ics = self.service.generate_ics([match_live])
        assert 'SEQUENCE:2' in ics
