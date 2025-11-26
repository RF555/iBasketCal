"""Match data model."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Team(BaseModel):
    """Represents a basketball team."""

    id: str
    name: str
    logo: Optional[str] = None


class ScoreTotal(BaseModel):
    """Score total for a team."""

    team_id: str = Field(..., alias="teamId")
    total: int

    class Config:
        """Pydantic configuration."""

        populate_by_name = True


class Score(BaseModel):
    """Match score."""

    totals: list[ScoreTotal] = []


class Court(BaseModel):
    """Match venue/court information."""

    place: Optional[str] = None
    address: Optional[str] = None
    town: Optional[str] = None

    def get_location(self) -> str:
        """Get formatted location string."""
        parts = [p for p in [self.place, self.town, self.address] if p]
        return ", ".join(parts) if parts else "TBD"


class Match(BaseModel):
    """Represents a basketball match."""

    id: str
    date: datetime
    status: str = "NOT_STARTED"  # NOT_STARTED, LIVE, CLOSED
    home_team: Team = Field(..., alias="homeTeam")
    away_team: Team = Field(..., alias="awayTeam")
    score: Optional[Score] = None
    court: Optional[Court] = None

    # These are added when processing
    competition_name: str = ""
    group_name: str = ""

    class Config:
        """Pydantic configuration."""

        populate_by_name = True

    def get_home_score(self) -> Optional[int]:
        """Get home team score if available."""
        if not self.score or not self.score.totals:
            return None
        for total in self.score.totals:
            if total.team_id == self.home_team.id:
                return total.total
        # Fallback: first score is usually home
        return self.score.totals[0].total if self.score.totals else None

    def get_away_score(self) -> Optional[int]:
        """Get away team score if available."""
        if not self.score or not self.score.totals:
            return None
        for total in self.score.totals:
            if total.team_id == self.away_team.id:
                return total.total
        # Fallback: second score is usually away
        return self.score.totals[1].total if len(self.score.totals) > 1 else None

    def get_title(self) -> str:
        """Get event title based on match status."""
        home = self.home_team.name
        away = self.away_team.name

        if self.status == "CLOSED":
            home_score = self.get_home_score()
            away_score = self.get_away_score()
            if home_score is not None and away_score is not None:
                return f"{home} {home_score} - {away_score} {away}"
        elif self.status == "LIVE":
            home_score = self.get_home_score()
            away_score = self.get_away_score()
            if home_score is not None and away_score is not None:
                return f"[LIVE] {home} {home_score} - {away_score} {away}"

        return f"{home} vs {away}"

    def get_location(self) -> str:
        """Get match location."""
        if self.court:
            return self.court.get_location()
        return "TBD"

    def get_description(self) -> str:
        """Get event description."""
        lines = []
        if self.competition_name:
            lines.append(f"Competition: {self.competition_name}")
        if self.group_name:
            lines.append(f"Stage: {self.group_name}")
        if self.status == "CLOSED":
            home_score = self.get_home_score()
            away_score = self.get_away_score()
            if home_score is not None and away_score is not None:
                lines.append(f"Final Score: {home_score} - {away_score}")
        return "\n".join(lines)
