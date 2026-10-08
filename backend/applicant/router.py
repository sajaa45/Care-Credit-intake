import uuid
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status

import db

from .form import form_definition
from .identity import hash_applicant_number
from .schemas import Application, IntakeSubmission, NotFoundResponse, ValidationErrorResponse

router = APIRouter(prefix="/applicant", tags=["Applicant intake"])

_VALID = {
    "applicant_number": "123456789",
    "treatment": "dental",
    "cost": 3500,
    "requested_term": 24,
    "income": 2800,
    "housing_cost": 900,
    "existing_obligations": 150,
    "household": "single",
    "additional_information": "I'm on a temporary contract until March.",
}

SUBMISSION_EXAMPLES = {
    "dental": {"summary": "Dental treatment", "value": _VALID},
    "other": {
        "summary": "Other treatment (described by the applicant)",
        "description": "With `treatment: other`, `treatment_other` is required and is stored as `treatment`.",
        "value": {
            **_VALID,
            "treatment": "other",
            "treatment_other": "Hearing aids",
            "household": "couple_with_children",
            "partner_income": 2100,
            "additional_information": "",
        },
    },
    "couple_missing_partner_income": {
        "summary": "Invalid: couple without partner income",
        "description": "Returns 422: `partner_income` is required for `couple` and `couple_with_children`.",
        "value": {**_VALID, "household": "couple"},
    },
    "invalid": {
        "summary": "Invalid: letters in applicant number, decimal amount, term too long, unknown household",
        "description": "Returns 422 with one message per field.",
        "value": {
            **_VALID,
            "applicant_number": "12AB",
            "cost": 3500.5,
            "requested_term": 72,
            "household": "divorced",
        },
    },
}


@router.get("/form", summary="Get the intake form")
def get_form() -> dict:
    """The questions the applicant answers, with the choice options and the allowed range for each number.

    A client can render the form from this, so the options and limits always match what the API accepts.
    """
    return form_definition()


@router.post(
    "/applications",
    summary="Submit an application",
    status_code=status.HTTP_201_CREATED,
    response_model=Application,
    responses={422: {"model": ValidationErrorResponse, "description": "One or more answers are invalid."}},
)
def submit_application(
    submission: Annotated[IntakeSubmission, Body(openapi_examples=SUBMISSION_EXAMPLES)],
) -> Application:
    """Validate the applicant's answers and store them as a new application with status `submitted`.

    Every submission is a new application; earlier ones are never changed. Submissions with the same
    `applicant_number` are linked to one applicant and numbered 1, 2, 3, … in the order they arrive.

    All amounts are whole numbers: decimals (`3500.5`, `3500.0`), numeric strings (`"3500"`) and booleans
    are rejected. `cost` must be €500–25,000 and `requested_term` 6–60 months; the other amounts can't be negative.
    `partner_income` is required for couples and stored as null for single households.
    """
    application_id = str(uuid.uuid4())
    with db.connect() as conn:
        # The next application_number is computed inside the INSERT itself, so two
        # submissions for the same applicant can't both get the same number.
        conn.execute(
            """
            INSERT INTO applications (
                id, applicant_id, application_number, treatment, cost, requested_term, income,
                housing_cost, existing_obligations, household, partner_income,
                additional_information, status, created_at
            )
            SELECT
                :id, :applicant_id, COALESCE(MAX(application_number), 0) + 1, :treatment, :cost,
                :requested_term, :income, :housing_cost, :existing_obligations, :household,
                :partner_income, :additional_information, :status, :created_at
            FROM applications WHERE applicant_id = :applicant_id
            """,
            {
                "id": application_id,
                "applicant_id": hash_applicant_number(submission.applicant_number),
                "treatment": submission.treatment_value(),
                "cost": submission.cost,
                "requested_term": submission.requested_term,
                "income": submission.income,
                "housing_cost": submission.housing_cost,
                "existing_obligations": submission.existing_obligations,
                "household": submission.household.value,
                "partner_income": submission.partner_income,
                "additional_information": submission.additional_information,
                "status": "submitted",
                "created_at": db.now_iso(),
            },
        )
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
    return Application(**dict(row))


@router.get(
    "/applications/{application_id}",
    summary="Get an application",
    response_model=Application,
    responses={404: {"model": NotFoundResponse, "description": "No application with this id."}},
)
def get_application(application_id: str) -> Application:
    """Return a stored application exactly as it was saved."""
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return Application(**dict(row))
