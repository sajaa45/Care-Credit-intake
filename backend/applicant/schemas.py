import json
import sqlite3
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    ValidationInfo,
    field_validator,
)

from .form import (
    APPLICANT_NUMBER_MAX_LENGTH,
    FREE_TEXT_MAX_LENGTH,
    INTEGER_RANGES,
    PARTNER_HOUSEHOLDS,
    TREATMENT_OTHER_MAX_LENGTH,
    Household,
    TreatmentType,
)


def _bounded_int(field: str, description: str, example: int):
    # StrictInt rejects floats (1500.5 and also 1500.0), numeric strings
    # ("1500") and booleans, so only a real JSON integer gets through.
    lo, hi = INTEGER_RANGES[field]
    return Annotated[StrictInt, Field(ge=lo, le=hi, description=description, examples=[example])]


def _text(max_length: int):
    return Annotated[str, StringConstraints(strip_whitespace=True, max_length=max_length)]


class IntakeSubmission(BaseModel):
    """The applicant's answers to the intake form."""

    model_config = ConfigDict(extra="forbid")

    applicant_number: Annotated[
        str,
        StringConstraints(strip_whitespace=True, pattern=r"^[0-9]+$", max_length=APPLICANT_NUMBER_MAX_LENGTH),
        Field(
            description="The applicant's ID number (digits only, sent as a string so leading zeros are kept). "
            "Only a keyed hash is stored; submissions with the same number are linked to the same applicant.",
            examples=["123456789"],
        ),
    ]
    treatment: TreatmentType = Field(description="Type of treatment.")
    treatment_other: Annotated[
        _text(TREATMENT_OTHER_MAX_LENGTH),
        Field(
            validate_default=True,
            description="Required when `treatment` is `other`: the treatment in the applicant's own words. "
            "It is stored as `treatment`. Ignored for the other treatment types.",
            examples=["Hearing aids"],
        ),
    ] = ""
    cost: _bounded_int("cost", "Cost of the treatment, in whole euros.", 3500)
    requested_term: _bounded_int(
        "requested_term", "Preferred repayment term in months. A preference, not a hard input.", 24
    )
    income: _bounded_int("income", "The applicant's own net monthly income, in whole euros.", 2800)
    housing_cost: _bounded_int("housing_cost", "Monthly rent or mortgage, in whole euros.", 900)
    existing_obligations: _bounded_int(
        "existing_obligations", "Total monthly payments on existing loans and credit, in whole euros.", 150
    )
    household: Household = Field(description="Household situation; determines the living standard norm.")
    partner_income: Annotated[
        _bounded_int("partner_income", "The partner's net monthly income, in whole euros.", 2100) | None,
        Field(
            validate_default=True,
            description="The partner's net monthly income, in whole euros. Required when `household` is `couple` "
            "or `couple_with_children` (enter 0 if the partner has no income). Ignored and stored as null otherwise.",
            examples=[2100],
        ),
    ] = None
    additional_information: Annotated[
        _text(FREE_TEXT_MAX_LENGTH),
        Field(
            description='Answer to "Is there anything else we should know about your situation?"',
            examples=["I'm on a temporary contract until March."],
        ),
    ] = ""

    @field_validator("treatment_other")
    @classmethod
    def _other_needs_description(cls, value: str, info: ValidationInfo) -> str:
        # `treatment` is declared first, so it's already validated (or missing) here.
        if info.data.get("treatment") is TreatmentType.other and not value:
            raise ValueError("Please tell us which treatment it is.")
        return value

    @field_validator("partner_income")
    @classmethod
    def _partner_income_for_couples(cls, value: int | None, info: ValidationInfo) -> int | None:
        # `household` is declared first, so it's already validated (or missing) here.
        household = info.data.get("household")
        if household is None:
            return value
        if household not in PARTNER_HOUSEHOLDS:
            return None
        if value is None:
            raise ValueError("Please enter your partner's net monthly income (0 if they have none).")
        return value

    def treatment_value(self) -> str:
        """What gets stored as `treatment`: the applicant's own words when they chose 'other'."""
        if self.treatment is TreatmentType.other:
            return self.treatment_other
        return self.treatment.value


class ScheduleRow(BaseModel):
    month: int
    opening_balance: Decimal
    instalment: Decimal
    interest: Decimal
    principal: Decimal
    closing_balance: Decimal


class Assessment(BaseModel):
    """The result of the affordability rule, with every number it was based on."""

    outcome: Literal["accept", "refer", "decline"]
    reason: str = Field(description="The rule that applied, in words, with the numbers.")
    rule_version: str = Field(description="Version of the rule that produced this outcome.")
    term: int = Field(description="The term assessed, in months (the requested term).")
    instalment: Decimal = Field(description="Monthly instalment for `term` at 8.9% per year (annuity), in euros.")
    available_room: Decimal = Field(
        description="income - housing share - existing obligations - norm share, in euros. "
        "Housing and the living standard norm are split by the applicant's share of household income."
    )
    suggested_term: int | None = Field(
        description="If the requested term isn't accepted: the shortest longer term that would be. Null if none fits."
    )
    suggested_instalment: Decimal | None
    total_repayable: Decimal | None = Field(
        description="Sum of all instalments in `schedule`: exactly principal + total_interest. "
        "Null for assessments made before schedules existed."
    )
    total_interest: Decimal | None
    schedule: list[ScheduleRow] | None = Field(
        description="Month by month for `term`. The final instalment absorbs rounding, so the last "
        "closing balance is exactly 0.00."
    )
    calculation: dict = Field(description="All inputs, constants and intermediate steps, to redo the calculation by hand.")
    created_at: datetime

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Assessment":
        calculation = json.loads(row["calculation"])
        steps = calculation["steps"]
        return cls(
            **{
                **dict(row),
                # The stored record includes the schedule; it's returned once, as `schedule`.
                "calculation": {key: value for key, value in calculation.items() if key != "schedule"},
                "total_repayable": steps.get("total_repayable"),
                "total_interest": steps.get("total_interest"),
                "schedule": calculation.get("schedule"),
            }
        )


class Application(BaseModel):
    """An application as stored, with its latest assessment."""

    id: str = Field(description="Application reference (UUID).")
    applicant_id: str = Field(description="Keyed hash (HMAC-SHA256) of the applicant's ID number; never the number itself.")
    application_number: int = Field(description="1 for the applicant's first application, 2 for the second, and so on.")
    treatment: str = Field(description="`dental`, `eye`, `orthodontic`, or the applicant's own description.")
    cost: int
    requested_term: int = Field(description="Requested term in months.")
    income: int
    housing_cost: int
    existing_obligations: int
    household: Household
    partner_income: int | None = Field(description="Null when the household has no partner.")
    additional_information: str
    status: str = Field(
        description="`submitted`, the assessment outcome (`accept`, `refer`, `decline`), "
        "or the latest employee decision (`accept`, `decline`).",
        examples=["accept"],
    )
    created_at: datetime = Field(description="When the application was received (UTC).")
    assessment: Assessment | None = None


class FieldError(BaseModel):
    field: str | None = Field(description="The request field the error belongs to; null if it's about the whole request.")
    message: str = Field(description="A message that can be shown to the applicant as-is.")


class ValidationErrorResponse(BaseModel):
    errors: list[FieldError]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "errors": [
                    {"field": "cost", "message": "Please enter a whole number (no decimals, no text)."},
                    {"field": "requested_term", "message": "Must be at most 60."},
                ]
            }
        }
    )


class NotFoundResponse(BaseModel):
    detail: str = Field(examples=["Application not found"])
