from datetime import datetime

from pydantic import BaseModel, Field

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
    answers: list[AnsweredQuestion]
    assessments: list[Assessment] = Field(description="Every assessment, oldest first.")
    free_text_review: FreeTextReview | None
    decisions: list[Decision] = Field(description="Every employee decision, oldest first.")
    timeline: list[TimelineEvent] = Field(description="Everything that happened, in order.")
