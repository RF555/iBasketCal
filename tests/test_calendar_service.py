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


class TestPlayerMode:
    """Tests for player mode calendar generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_player_mode_event_timing(self):
        """Event starts prep_time before game in player mode."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T20:00:00Z',  # 8 PM game
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60)

        # Event should start at 7 PM (60 min before)
        assert 'DTSTART:20241015T190000Z' in ics
        # Event should end at 10 PM (game end = game time + 2hr)
        assert 'DTEND:20241015T220000Z' in ics

    def test_player_mode_summary_includes_game_time(self):
        """Summary includes actual game time in player mode."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T21:00:00Z',  # 9 PM game (UTC)
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, display_timezone='UTC')

        # Summary should include time (UTC)
        assert 'SUMMARY:21:00 Team A vs Team B' in ics

    def test_player_mode_uid_includes_mode(self):
        """UID differentiates player mode calendars."""
        match = {
            'id': 'match123',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        ics_fan = self.service.generate_ics([match], player_mode=False)
        ics_player = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60)

        assert 'UID:match123@ibasketball.calendar' in ics_fan
        assert 'UID:match123-player60@ibasketball.calendar' in ics_player

    def test_player_mode_description_includes_prep_info(self):
        """Description includes game time and prep time in player mode."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T20:30:00Z',
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=90, display_timezone='UTC')

        unfolded = ics.replace('\r\n ', '')
        assert 'Game Time: 20:30' in unfolded
        assert 'Prep Time: 90 minutes' in unfolded

    def test_player_mode_with_scores(self):
        """Player mode handles completed games with scores."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T19:00:00Z',
            'status': 'CLOSED',
            'homeTeam': {'id': 'home', 'name': 'Home Team'},
            'awayTeam': {'id': 'away', 'name': 'Away Team'},
            'court': {},
            'score': {
                'totals': [
                    {'teamId': 'home', 'total': 92},
                    {'teamId': 'away', 'total': 88}
                ]
            }
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, display_timezone='UTC')

        assert 'SUMMARY:19:00 Home Team (92) vs Away Team (88)' in ics

    def test_fan_mode_unchanged(self):
        """Fan mode (default) behavior unchanged."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T20:00:00Z',
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=False)

        # Should start at game time, not before
        assert 'DTSTART:20241015T200000Z' in ics
        assert 'DTEND:20241015T220000Z' in ics
        # Summary should NOT include time prefix
        assert 'SUMMARY:Team A vs Team B' in ics

    def test_various_prep_times(self):
        """Different prep times work correctly."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T20:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        # 15 minutes prep
        ics_15 = self.service.generate_ics([match], player_mode=True, prep_time_minutes=15)
        assert 'DTSTART:20241015T194500Z' in ics_15  # 19:45

        # 120 minutes prep (2 hours)
        ics_120 = self.service.generate_ics([match], player_mode=True, prep_time_minutes=120)
        assert 'DTSTART:20241015T180000Z' in ics_120  # 18:00

        # 180 minutes prep (3 hours)
        ics_180 = self.service.generate_ics([match], player_mode=True, prep_time_minutes=180)
        assert 'DTSTART:20241015T170000Z' in ics_180  # 17:00

    def test_player_mode_live_game(self):
        """Player mode handles live games."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'status': 'LIVE',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, display_timezone='UTC')

        assert 'SUMMARY:18:00 LIVE: Team A vs Team B' in ics


class TestTimeFormat:
    """Tests for time format selection in player mode."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_time_format_24h_default(self):
        """24-hour format is default."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T21:00:00Z',  # 9 PM UTC
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, display_timezone='UTC')

        assert 'SUMMARY:21:00 Team A vs Team B' in ics

    def test_time_format_24h_explicit(self):
        """24-hour format when explicitly specified."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T14:30:00Z',  # 2:30 PM UTC
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, time_format='24h', display_timezone='UTC')

        assert 'SUMMARY:14:30 Team A vs Team B' in ics

    def test_time_format_12h_pm(self):
        """12-hour format for PM times."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T21:00:00Z',  # 9 PM UTC
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, time_format='12h', display_timezone='UTC')

        assert 'SUMMARY:9:00 PM Team A vs Team B' in ics

    def test_time_format_12h_am(self):
        """12-hour format for AM times."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T09:30:00Z',  # 9:30 AM UTC
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, time_format='12h', display_timezone='UTC')

        assert 'SUMMARY:9:30 AM Team A vs Team B' in ics

    def test_time_format_12h_noon(self):
        """12-hour format for noon."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T12:00:00Z',  # 12 PM (noon) UTC
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, time_format='12h', display_timezone='UTC')

        assert 'SUMMARY:12:00 PM Team A vs Team B' in ics

    def test_time_format_12h_midnight(self):
        """12-hour format for midnight."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T00:30:00Z',  # 12:30 AM (midnight) UTC
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, time_format='12h', display_timezone='UTC')

        assert 'SUMMARY:12:30 AM Team A vs Team B' in ics

    def test_time_format_12h_with_scores(self):
        """12-hour format with completed game scores."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T19:00:00Z',  # 7 PM UTC
            'status': 'CLOSED',
            'homeTeam': {'id': 'home', 'name': 'Home Team'},
            'awayTeam': {'id': 'away', 'name': 'Away Team'},
            'court': {},
            'score': {
                'totals': [
                    {'teamId': 'home', 'total': 92},
                    {'teamId': 'away', 'total': 88}
                ]
            }
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, time_format='12h', display_timezone='UTC')

        assert 'SUMMARY:7:00 PM Home Team (92) vs Away Team (88)' in ics

    def test_time_format_12h_live_game(self):
        """12-hour format with live game."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T20:00:00Z',  # 8 PM UTC
            'status': 'LIVE',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, time_format='12h', display_timezone='UTC')

        assert 'SUMMARY:8:00 PM LIVE: Team A vs Team B' in ics

    def test_time_format_fan_mode_ignored(self):
        """Time format parameter doesn't affect fan mode."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T20:00:00Z',
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=False, time_format='12h', display_timezone='UTC')

        # Fan mode should NOT include time in summary
        assert 'SUMMARY:Team A vs Team B' in ics
        assert '8:00 PM' not in ics

    def test_time_format_description_uses_24h(self):
        """Description always uses 24-hour format for clarity."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T20:30:00Z',  # 8:30 PM UTC
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=90, time_format='12h', display_timezone='UTC')

        # Description should still have 24h format for consistency
        unfolded = ics.replace('\r\n ', '')
        assert 'Game Time: 20:30' in unfolded


class TestTimezoneValidation:
    """Tests for timezone validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_invalid_timezone_falls_back_to_default(self):
        """Invalid timezone falls back to Asia/Jerusalem."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T17:00:00Z',  # 5 PM UTC = 8 PM Jerusalem
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics(
            [match],
            player_mode=True,
            prep_time_minutes=60,
            display_timezone='Invalid/TZ'
        )

        # Should fall back to Jerusalem time (UTC+3 in October)
        assert 'SUMMARY:20:00 Team A vs Team B' in ics

    def test_valid_custom_timezone(self):
        """Valid custom timezone is accepted and used."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T20:00:00Z',  # 8 PM UTC = 4 PM New York (UTC-4 in Oct)
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics(
            [match],
            player_mode=True,
            prep_time_minutes=60,
            display_timezone='America/New_York'
        )

        # Should show New York time (UTC-4 in October = EDT)
        assert 'SUMMARY:16:00 Team A vs Team B' in ics


class TestLocationBuilding:
    """Tests for location field building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_location_with_all_parts(self):
        """Location with place, town, and address."""
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

        # All parts joined with comma and space (comma is escaped)
        assert 'LOCATION:Menora Arena\\, Tel Aviv\\, Yigal Alon 51' in ics

    def test_location_with_only_place(self):
        """Location with only place specified."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {
                'place': 'Stadium',
                'town': '',  # Empty
                'address': None  # None
            }
        }

        ics = self.service.generate_ics([match])

        assert 'LOCATION:Stadium' in ics
        # Should not have trailing commas or 'None'
        assert 'LOCATION:Stadium\\, \\,' not in ics

    def test_location_with_no_court_data(self):
        """Location with empty court dict."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        ics = self.service.generate_ics([match])

        assert 'LOCATION:TBD' in ics


class TestNullTeamData:
    """Tests for null/missing team data."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_home_team_is_none(self):
        """Handle None for homeTeam."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': None,  # Explicitly None
            'awayTeam': {'id': 't2', 'name': 'Away Team'},
            'court': {}
        }

        ics = self.service.generate_ics([match])

        # Should use TBD for missing team
        assert 'SUMMARY:TBD vs Away Team' in ics

    def test_away_team_is_none(self):
        """Handle None for awayTeam."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'homeTeam': {'id': 't1', 'name': 'Home Team'},
            'awayTeam': None,  # Explicitly None
            'court': {}
        }

        ics = self.service.generate_ics([match])

        # Should use TBD for missing team
        assert 'SUMMARY:Home Team vs TBD' in ics


class TestScoreEdgeCases:
    """Tests for score data edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_score_totals_with_non_dict_entry(self):
        """Score totals containing non-dict values."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'status': 'CLOSED',
            'homeTeam': {'id': 'home', 'name': 'Home Team'},
            'awayTeam': {'id': 'away', 'name': 'Away Team'},
            'court': {},
            'score': {
                'totals': [
                    "invalid_entry",  # Non-dict
                    {'teamId': 'home', 'total': 85},
                    None,  # None
                    {'teamId': 'away', 'total': 78}
                ]
            }
        }

        ics = self.service.generate_ics([match])

        # Should handle gracefully and extract valid scores
        assert 'SUMMARY:Home Team (85) vs Away Team (78)' in ics

    def test_score_with_missing_team_id(self):
        """Score total without teamId field."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'status': 'CLOSED',
            'homeTeam': {'id': 'home', 'name': 'Home Team'},
            'awayTeam': {'id': 'away', 'name': 'Away Team'},
            'court': {},
            'score': {
                'totals': [
                    {'total': 100},  # Missing teamId
                    {'teamId': '', 'total': 50}  # Empty teamId
                ]
            }
        }

        ics = self.service.generate_ics([match])

        # Scores should default to 0 when teamId not matched
        assert 'SUMMARY:Home Team (0) vs Away Team (0)' in ics


class TestModeAndFormatCombinations:
    """Tests for combinations of player mode, time format, and timezone."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_player_mode_12h_custom_timezone(self):
        """Player mode with 12-hour format and custom timezone."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T20:00:00Z',  # 8 PM UTC = 4 PM New York
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics(
            [match],
            player_mode=True,
            prep_time_minutes=90,
            time_format='12h',
            display_timezone='America/New_York'
        )

        # Should show 4 PM in 12-hour format
        assert 'SUMMARY:4:00 PM Team A vs Team B' in ics
        # Event should start 90 minutes before (2:30 PM = 18:30 UTC)
        assert 'DTSTART:20241015T183000Z' in ics

    def test_live_game_fan_mode(self):
        """LIVE status in fan mode."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'status': 'LIVE',
            'homeTeam': {'id': 't1', 'name': 'Home'},
            'awayTeam': {'id': 't2', 'name': 'Away'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=False)

        # Fan mode: "LIVE: Home vs Away" (no time prefix)
        assert 'SUMMARY:LIVE: Home vs Away' in ics

    def test_live_game_player_mode(self):
        """LIVE status in player mode."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T18:00:00Z',
            'status': 'LIVE',
            'homeTeam': {'id': 't1', 'name': 'Home'},
            'awayTeam': {'id': 't2', 'name': 'Away'},
            'court': {}
        }

        ics = self.service.generate_ics(
            [match],
            player_mode=True,
            prep_time_minutes=60,
            display_timezone='UTC'
        )

        # Player mode: "HH:MM LIVE: Home vs Away"
        assert 'SUMMARY:18:00 LIVE: Home vs Away' in ics


class TestTimezoneConversion:
    """Tests for timezone conversion in player mode."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CalendarService()

    def test_jerusalem_timezone_conversion(self):
        """Times are converted to Jerusalem timezone."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T17:00:00Z',  # 5 PM UTC = 8 PM Jerusalem (UTC+3 in Oct)
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, display_timezone='Asia/Jerusalem')

        # Should show Jerusalem time (UTC+3 in October = IDT)
        assert 'SUMMARY:20:00 Team A vs Team B' in ics

    def test_new_york_timezone_conversion(self):
        """Times are converted to New York timezone."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T20:00:00Z',  # 8 PM UTC = 4 PM New York (UTC-4 in Oct)
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, display_timezone='America/New_York')

        # Should show New York time (UTC-4 in October = EDT)
        assert 'SUMMARY:16:00 Team A vs Team B' in ics

    def test_utc_timezone_no_conversion(self):
        """UTC timezone shows times as-is."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T19:30:00Z',
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, display_timezone='UTC')

        assert 'SUMMARY:19:30 Team A vs Team B' in ics

    def test_invalid_timezone_falls_back_to_jerusalem(self):
        """Invalid timezone falls back to Jerusalem."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T17:00:00Z',  # 5 PM UTC = 8 PM Jerusalem
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, display_timezone='Invalid/Timezone')

        # Should fall back to Jerusalem time
        assert 'SUMMARY:20:00 Team A vs Team B' in ics

    def test_default_timezone_is_jerusalem(self):
        """Default timezone is Jerusalem when not specified."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T17:00:00Z',  # 5 PM UTC = 8 PM Jerusalem
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        # Don't pass display_timezone - should default to Jerusalem
        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60)

        # Should show Jerusalem time
        assert 'SUMMARY:20:00 Team A vs Team B' in ics

    def test_timezone_with_12h_format(self):
        """Timezone conversion works with 12-hour format."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T17:00:00Z',  # 5 PM UTC = 8 PM Jerusalem
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'Team A'},
            'awayTeam': {'id': 't2', 'name': 'Team B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, time_format='12h', display_timezone='Asia/Jerusalem')

        assert 'SUMMARY:8:00 PM Team A vs Team B' in ics

    def test_timezone_in_description(self):
        """Description shows time in selected timezone."""
        match = {
            'id': 'm1',
            'date': '2024-10-15T17:00:00Z',  # 5 PM UTC = 8 PM Jerusalem
            'status': 'NOT_STARTED',
            'homeTeam': {'id': 't1', 'name': 'A'},
            'awayTeam': {'id': 't2', 'name': 'B'},
            'court': {}
        }

        ics = self.service.generate_ics([match], player_mode=True, prep_time_minutes=60, display_timezone='Asia/Jerusalem')

        unfolded = ics.replace('\r\n ', '')
        assert 'Game Time: 20:00' in unfolded
