"""Season data model."""

from datetime import datetime
from pydantic import BaseModel, Field


class Season(BaseModel):
    """Represents a basketball season."""

    id: str = Field(..., alias="_id")
    name: str
    start_date: datetime = Field(..., alias="startDate")
    end_date: datetime = Field(..., alias="endDate")

    class Config:
        """Pydantic configuration."""

        populate_by_name = True

    def is_current(self) -> bool:
        """Check if this is the current season."""
        now = datetime.utcnow()
        return self.start_date <= now <= self.end_date
