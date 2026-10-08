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


class FreeTextReview(BaseModel):
    """What the language model made of the free-text answer: all that's kept once the raw text is deleted."""

    status: Literal["screened", "failed", "skipped"] = Field(
        description="`screened`; `failed` (not stored, flagged for follow-up); `skipped` (left empty)."
    )
    summary: str | None = Field(description="Short summary for the employee, without medical detail.")
    needs_review: bool
    reason: str = Field(description="Why it does (or doesn't) need a human to look at it.")
    referred_by_flag: bool = Field(description="True if this flag turned the rule's `accept` into `refer`.")
    model: str
    prompt_version: str
    created_at: datetime
    raw_text_deleted_at: datetime | None = Field(description="When the raw text was deleted; null if there was none.")


class ReviewedApplication(Application):
    """An application with its latest assessment, free-text review and every employee decision, oldest first."""

    free_text_review: FreeTextReview | None = None
    decisions: list[Decision] = []
