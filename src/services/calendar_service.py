"""
Calendar Service - Generates ICS calendar files from match data.

Creates RFC 5545 compliant iCalendar files for Israeli basketball games.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib


class CalendarService:
    """
    Generates ICS calendar files from match data.
    """

    def generate_ics(
        self,
        matches: list,
        calendar_name: str = "Israeli Basketball"
    ) -> str:
        """
        Generate ICS calendar content from matches.

        Args:
            matches: List of match dicts from DataService
            calendar_name: Name for the calendar

        Returns:
            ICS file content as string
        """
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Israeli Basketball Calendar//ibasketcal//EN",
            f"X-WR-CALNAME:{self._escape(calendar_name)}",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-TIMEZONE:Asia/Jerusalem",
        ]

        # Add timezone definition
        lines.extend(self._get_timezone_component())

        for match in matches:
            event = self._match_to_vevent(match)
            lines.extend(event)

        lines.append("END:VCALENDAR")

        return "\r\n".join(lines)

    def _get_timezone_component(self) -> list:
        """Generate VTIMEZONE component for Israel timezone."""
        return [
            "BEGIN:VTIMEZONE",
            "TZID:Asia/Jerusalem",
            "BEGIN:STANDARD",
            "DTSTART:19701025T020000",
            "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
            "TZOFFSETFROM:+0300",
            "TZOFFSETTO:+0200",
            "TZNAME:IST",
            "END:STANDARD",
            "BEGIN:DAYLIGHT",
            "DTSTART:19700329T020000",
            "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1FR",
            "TZOFFSETFROM:+0200",
            "TZOFFSETTO:+0300",
            "TZNAME:IDT",
            "END:DAYLIGHT",
            "END:VTIMEZONE",
        ]

    def _match_to_vevent(self, match: dict) -> list:
        """Convert a match to VEVENT lines."""
        match_id = match.get('id', 'unknown')

        # Generate a stable UID based on match ID
        uid = f"{match_id}@ibasketball.calendar"

        # Parse date
        date_str = match.get('date', '')
        try:
            # Handle ISO format with Z or +00:00
            if date_str.endswith('Z'):
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            elif '+' in date_str or (date_str.count('-') > 2):
                dt = datetime.fromisoformat(date_str)
            else:
                dt = datetime.fromisoformat(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            dt = datetime.now(timezone.utc)

        # Format times in UTC
        dtstart = dt.strftime("%Y%m%dT%H%M%SZ")
        dtend = (dt + timedelta(hours=2)).strftime("%Y%m%dT%H%M%SZ")
        dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        # Get team info
        home_team = match.get('homeTeam', {}) or {}
        away_team = match.get('awayTeam', {}) or {}
        home = home_team.get('name', 'TBD')
        away = away_team.get('name', 'TBD')
        status = match.get('status', '')

        # Build summary based on match status
        if status == 'CLOSED':
            # Get scores for completed matches
            scores = match.get('score', {}) or {}
            totals = scores.get('totals', []) or []

            home_score = 0
            away_score = 0

            for t in totals:
                if isinstance(t, dict):
                    team_id = t.get('teamId', '')
                    total = t.get('total', 0)
                    if team_id == home_team.get('id'):
                        home_score = total
                    elif team_id == away_team.get('id'):
                        away_score = total

            summary = f"{home} {home_score}-{away_score} {away}"
        elif status == 'LIVE':
            summary = f"LIVE: {home} vs {away}"
        else:
            summary = f"{home} vs {away}"

        # Build description
        desc_parts = []
        if match.get('_competition'):
            desc_parts.append(f"Competition: {match['_competition']}")
        if match.get('_group'):
            desc_parts.append(f"Group: {match['_group']}")
        if match.get('_season'):
            desc_parts.append(f"Season: {match['_season']}")
        if status:
            desc_parts.append(f"Status: {status}")

        description = "\\n".join(desc_parts)

        # Location
        court = match.get('court', {}) or {}
        location_parts = []
        if court.get('place'):
            location_parts.append(court['place'])
        if court.get('town'):
            location_parts.append(court['town'])
        if court.get('address'):
            location_parts.append(court['address'])

        location = ', '.join(location_parts) if location_parts else 'TBD'

        # Generate SEQUENCE based on last modification (use status as proxy)
        sequence = 0
        if status == 'CLOSED':
            sequence = 1
        elif status == 'LIVE':
            sequence = 2

        return [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{self._escape(summary)}",
            f"DESCRIPTION:{self._escape(description)}",
            f"LOCATION:{self._escape(location)}",
            f"SEQUENCE:{sequence}",
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
            "END:VEVENT",
        ]

    def _escape(self, text: str) -> str:
        """Escape special characters for ICS format."""
        if not text:
            return ""

        # ICS escaping rules
        text = text.replace("\\", "\\\\")
        text = text.replace(";", "\\;")
        text = text.replace(",", "\\,")
        text = text.replace("\n", "\\n")
        text = text.replace("\r", "")

        return text

    def filter_matches_by_date_range(
        self,
        matches: list,
        days_ahead: Optional[int] = None,
        days_behind: Optional[int] = None
    ) -> list:
        """
        Filter matches to a specific date range.

        Args:
            matches: List of match dictionaries
            days_ahead: Only include matches within this many days in the future
            days_behind: Only include matches within this many days in the past

        Returns:
            Filtered list of matches
        """
        now = datetime.now(timezone.utc)
        filtered = []

        for match in matches:
            date_str = match.get('date', '')
            if not date_str:
                continue

            try:
                if date_str.endswith('Z'):
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    dt = datetime.fromisoformat(date_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)

                # Check date range
                if days_ahead is not None:
                    cutoff = now + timedelta(days=days_ahead)
                    if dt > cutoff:
                        continue

                if days_behind is not None:
                    cutoff = now - timedelta(days=days_behind)
                    if dt < cutoff:
                        continue

                filtered.append(match)

            except (ValueError, TypeError):
                # Skip matches with invalid dates
                continue

        return filtered


# CLI entry point for testing
if __name__ == '__main__':
    from .data_service import DataService

    data_service = DataService()
    calendar_service = CalendarService()

    # Get some matches
    matches = data_service.get_all_matches()
    print(f"Total matches: {len(matches)}")

    # Filter to next 30 days
    filtered = calendar_service.filter_matches_by_date_range(
        matches,
        days_ahead=30,
        days_behind=7
    )
    print(f"Matches in date range: {len(filtered)}")

    # Generate calendar
    ics_content = calendar_service.generate_ics(filtered, "Israeli Basketball - Test")
    print(f"\nGenerated ICS ({len(ics_content)} bytes)")
    print("\n--- First 1000 chars ---")
    print(ics_content[:1000])
