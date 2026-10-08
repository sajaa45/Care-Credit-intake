from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from applicant.schemas import Application


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["accept", "decline"] = Field(description="The employee's decision; it becomes the status.")
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)] = Field(
        description="Why. Required: every decision must be explainable later.",
        examples=["Temporary contract is being made permanent per employer letter; income is stable."],
    )
    employee: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] = Field(
        description="Who made the decision. A name for now; the logged-in user once there is authentication.",
        examples=["J. de Vries"],
    )


class Decision(BaseModel):
    id: str
    employee: str
    previous_status: str = Field(description="The status before this decision, so every change shows from → to.")
    outcome: Literal["accept", "decline"]
    comment: str
    created_at: datetime


class ReviewedApplication(Application):
    """An application with its latest assessment and every employee decision, oldest first."""

    decisions: list[Decision] = []
