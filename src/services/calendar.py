"""Calendar service for generating ICS files from matches."""

import logging
from typing import Optional
from datetime import timedelta

from src.models.match import Match
from src.utils.ics import ICSBuilder

logger = logging.getLogger(__name__)


class CalendarService:
    """Service for generating ICS calendars from basketball matches."""

    DEFAULT_MATCH_DURATION = timedelta(hours=2)

    def __init__(self, base_url: str = "ibasketcal.local") -> None:
        """Initialize the calendar service.

        Args:
            base_url: Base URL for generating UIDs
        """
        self.base_url = base_url

    def generate_ics(
        self,
        matches: list[Match],
        calendar_name: str = "Israeli Basketball",
    ) -> str:
        """Generate an ICS calendar from a list of matches.

        Args:
            matches: List of Match objects to include
            calendar_name: Name for the calendar

        Returns:
            Complete ICS calendar as string
        """
        builder = ICSBuilder(calendar_name=calendar_name)

        for match in matches:
            self._add_match_event(builder, match)

        logger.info(f"Generated ICS calendar with {len(matches)} events")
        return builder.build()

    def _add_match_event(self, builder: ICSBuilder, match: Match) -> None:
        """Add a match as an event to the ICS builder.

        Args:
            builder: ICS builder instance
            match: Match to add
        """
        # Generate unique ID
        uid = builder.generate_uid(match.id, self.base_url)

        # Get event details
        summary = match.get_title()
        location = match.get_location()
        description = match.get_description()

        # Determine event status
        if match.status == "CLOSED":
            status = "CONFIRMED"
        elif match.status == "LIVE":
            status = "CONFIRMED"
        else:
            status = "TENTATIVE"

        # Calculate end time
        dtend = match.date + self.DEFAULT_MATCH_DURATION

        builder.add_event(
            uid=uid,
            summary=summary,
            dtstart=match.date,
            dtend=dtend,
            location=location,
            description=description,
            status=status,
        )

    def generate_calendar_name(
        self,
        competition: Optional[str] = None,
        team: Optional[str] = None,
    ) -> str:
        """Generate a descriptive calendar name based on filters.

        Args:
            competition: Competition filter
            team: Team filter

        Returns:
            Descriptive calendar name
        """
        parts = ["כדורסל ישראלי"]  # Israeli Basketball

        if competition:
            parts.append(competition)
        if team:
            parts.append(team)

        return " - ".join(parts)
