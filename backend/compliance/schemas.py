from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from applicant.form import APPLICANT_NUMBER_MAX_LENGTH
from applicant.schemas import Application, Assessment
from employee.schemas import Decision, FreeTextReview


class ApplicationSummary(BaseModel):
    id: str
    applicant_id: str
    application_number: int
    treatment: str
    cost: int
    requested_term: int
    status: str
    created_at: datetime
    decided_by_employee: bool


class ApplicantSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applicant_number: Annotated[
        str,
        StringConstraints(strip_whitespace=True, pattern=r"^[0-9]+$", max_length=APPLICANT_NUMBER_MAX_LENGTH),
    ] = Field(description="The applicant's ID number. Hashed the same way as at intake; never stored or logged.")


class AnsweredQuestion(BaseModel):
    field: str
    question: str = Field(description="The question exactly as it was shown to the applicant.")
    answer: str | None = Field(description="What the applicant answered, as stored. Null if the question didn't apply.")
    note: str | None = None


class TimelineEvent(BaseModel):
    at: datetime
    event: str
    detail: str


class ComplianceRecord(BaseModel):
    """Everything about one application: what we asked, what they answered, what we concluded and why,
    and what employees did afterwards."""

    application: Application
    form_id: str
    form_version: str
    answers: list[AnsweredQuestion]
    assessments: list[Assessment] = Field(description="Every assessment, oldest first.")
    free_text_review: FreeTextReview | None
    decisions: list[Decision] = Field(description="Every employee decision, oldest first.")
    timeline: list[TimelineEvent] = Field(description="Everything that happened, in order.")
