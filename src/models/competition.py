"""Competition data model."""

from pydantic import BaseModel, Field


class Group(BaseModel):
    """Represents a competition group (e.g., regular season, playoffs)."""

    id: str
    name: str
    order: int = 1
    type: str = "LEAGUE"  # LEAGUE or PLAYOFF


class Competition(BaseModel):
    """Represents a basketball competition/league."""

    id: str
    name: str
    project_key: str = Field(default="ibba", alias="projectKey")
    groups: list[Group] = []

    class Config:
        """Pydantic configuration."""

        populate_by_name = True
