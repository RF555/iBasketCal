"""ICS/iCalendar format utilities."""

import re
from datetime import datetime, timedelta
from typing import Optional
import hashlib


class ICSBuilder:
    """Builder for creating valid ICS calendar files."""

    # ICS requires CRLF line endings
    CRLF = "\r\n"

    # Maximum line length before folding (75 characters + CRLF)
    MAX_LINE_LENGTH = 75

    # Asia/Jerusalem timezone definition (using CRLF line endings)
    VTIMEZONE = (
        "BEGIN:VTIMEZONE\r\n"
        "TZID:Asia/Jerusalem\r\n"
        "X-LIC-LOCATION:Asia/Jerusalem\r\n"
        "BEGIN:STANDARD\r\n"
        "TZOFFSETFROM:+0300\r\n"
        "TZOFFSETTO:+0200\r\n"
        "TZNAME:IST\r\n"
        "DTSTART:19701025T020000\r\n"
        "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU\r\n"
        "END:STANDARD\r\n"
        "BEGIN:DAYLIGHT\r\n"
        "TZOFFSETFROM:+0200\r\n"
        "TZOFFSETTO:+0300\r\n"
        "TZNAME:IDT\r\n"
        "DTSTART:19700329T020000\r\n"
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1FR\r\n"
        "END:DAYLIGHT\r\n"
        "END:VTIMEZONE"
    )

    def __init__(self, calendar_name: str = "Israeli Basketball") -> None:
        """Initialize the ICS builder.

        Args:
            calendar_name: Name of the calendar
        """
        self.calendar_name = calendar_name
        self.events: list[str] = []

    @staticmethod
    def escape_text(text: str) -> str:
        """Escape special characters in ICS text.

        Args:
            text: Raw text to escape

        Returns:
            Escaped text safe for ICS
        """
        if not text:
            return ""
        # Escape backslash first, then others
        text = text.replace("\\", "\\\\")
        text = text.replace(";", "\\;")
        text = text.replace(",", "\\,")
        text = text.replace("\n", "\\n")
        text = text.replace("\r", "")
        return text

    @staticmethod
    def fold_line(line: str) -> str:
        """Fold lines longer than 75 characters per RFC 5545.

        Args:
            line: Line to fold

        Returns:
            Folded line with proper continuation
        """
        if len(line.encode('utf-8')) <= ICSBuilder.MAX_LINE_LENGTH:
            return line

        result = []
        current_line = ""

        for char in line:
            test_line = current_line + char
            if len(test_line.encode('utf-8')) > ICSBuilder.MAX_LINE_LENGTH:
                result.append(current_line)
                current_line = " " + char  # Space indicates continuation
            else:
                current_line = test_line

        if current_line:
            result.append(current_line)

        return ICSBuilder.CRLF.join(result)

    @staticmethod
    def format_datetime(dt: datetime) -> str:
        """Format datetime for ICS (UTC with Z suffix).

        Args:
            dt: Datetime to format

        Returns:
            ICS-formatted datetime string
        """
        # Convert to UTC if timezone-aware
        if dt.tzinfo is not None:
            # Convert to UTC timestamp then back to naive UTC
            import calendar
            timestamp = calendar.timegm(dt.utctimetuple())
            dt = datetime.utcfromtimestamp(timestamp)

        return dt.strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def generate_uid(match_id: str, base_url: str = "ibasketcal.local") -> str:
        """Generate a unique identifier for an event.

        Args:
            match_id: Match ID
            base_url: Base URL for UID domain

        Returns:
            Unique identifier string
        """
        return f"{match_id}@{base_url}"

    def add_event(
        self,
        uid: str,
        summary: str,
        dtstart: datetime,
        dtend: Optional[datetime] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        status: str = "CONFIRMED",
    ) -> None:
        """Add an event to the calendar.

        Args:
            uid: Unique identifier for the event
            summary: Event title/summary
            dtstart: Event start datetime
            dtend: Event end datetime (default: 2 hours after start)
            location: Event location
            description: Event description
            status: Event status (CONFIRMED, TENTATIVE, CANCELLED)
        """
        if dtend is None:
            dtend = dtstart + timedelta(hours=2)

        lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{self.format_datetime(datetime.utcnow())}",
            f"DTSTART:{self.format_datetime(dtstart)}",
            f"DTEND:{self.format_datetime(dtend)}",
            f"SUMMARY:{self.escape_text(summary)}",
        ]

        if location:
            lines.append(f"LOCATION:{self.escape_text(location)}")

        if description:
            lines.append(f"DESCRIPTION:{self.escape_text(description)}")

        lines.append(f"STATUS:{status}")
        lines.append("END:VEVENT")

        # Fold long lines
        folded_lines = [self.fold_line(line) for line in lines]
        self.events.append(self.CRLF.join(folded_lines))

    def build(self) -> str:
        """Build the complete ICS calendar.

        Returns:
            Complete ICS calendar as string
        """
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:-//Israeli Basketball Calendar//iBasketCal//HE",
            f"X-WR-CALNAME:{self.escape_text(self.calendar_name)}",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]

        # Add timezone
        lines.append(self.VTIMEZONE)

        # Add all events
        for event in self.events:
            lines.append(event)

        lines.append("END:VCALENDAR")

        return self.CRLF.join(lines)

    def clear(self) -> None:
        """Clear all events from the builder."""
        self.events.clear()
