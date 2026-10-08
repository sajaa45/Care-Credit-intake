import json
import sqlite3
import uuid
from typing import Annotated

from fastapi import APIRouter, Body, status

import db
from assessment.free_text import screen
from assessment.service import assess_and_store, store_free_text_review

from .form import FORM_ID, QUESTIONS, form_definition
from .identity import hash_applicant_number
from .schemas import (
    ApplicantOffer,
    ApplicantSearch,
    ApplicationStatus,
    Assessment,
    IntakeSubmission,
    ValidationErrorResponse,
)

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
        "summary": "Invalid: letters in ID number, decimal amount, term too long, unknown household",
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


def _statuses(conn: sqlite3.Connection, where: str, value: str) -> list[ApplicationStatus]:
    """What the applicant may see of the matching applications, newest first.

    `where` is always a fixed condition written in this file; only `value` comes from the request.
    """
    rows = conn.execute(
        f"""
        SELECT a.id, a.application_number, a.treatment, a.cost, a.requested_term, a.status,
               a.created_at AS submitted_at,
               COALESCE(MAX(d.created_at), a.created_at) AS updated_at,
               COUNT(d.id) > 0 AS reviewed_by_employee
        FROM applications a
        LEFT JOIN decisions d ON d.application_id = a.id
        WHERE {where}
        GROUP BY a.id
        ORDER BY a.application_number DESC
        """,
        (value,),
    ).fetchall()
    result = []
    for row in rows:
        assessment = conn.execute(
            "SELECT * FROM assessments WHERE application_id = ? ORDER BY created_at DESC LIMIT 1", (row["id"],)
        ).fetchone()
        offer = ApplicantOffer(**Assessment.from_row(assessment).model_dump()) if assessment else None
        result.append(ApplicationStatus(**dict(row), offer=offer))
    return result


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
    response_model=ApplicationStatus,
    responses={422: {"model": ValidationErrorResponse, "description": "One or more answers are invalid."}},
)
def submit_application(
    submission: Annotated[IntakeSubmission, Body(openapi_examples=SUBMISSION_EXAMPLES)],
) -> ApplicationStatus:
    """Validate the applicant's answers, store them as a new application, and assess affordability.

    The assessment runs straight away and is stored with every number it used; the application's
    `status` becomes the outcome (`accept`, `refer` or `decline`).

    `additional_information` is held only until a language model has read it: the model writes a short
    summary and says whether a human needs to look at something, then the raw text is deleted. If it
    flags something, an accepted application is referred instead. If screening fails, the text is
    deleted anyway and the application is flagged.

    Every submission is a new application; earlier ones are never changed. Submissions with the same
    `applicant_number` are linked to one applicant and numbered 1, 2, 3, … in the order they arrive.

    All amounts are whole numbers: decimals (`3500.5`, `3500.0`), numeric strings (`"3500"`) and booleans
    are rejected. `cost` must be €500–25,000 and `requested_term` 6–60 months; the other amounts can't be negative.
    `partner_income` is required for couples and stored as null for single households.
    """
    application_id = str(uuid.uuid4())
    with db.connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO forms (id, definition, created_at) VALUES (?, ?, ?)",
            (FORM_ID, json.dumps(QUESTIONS), db.now_iso()),
        )
        # The next application_number is computed inside the INSERT itself, so two
        # submissions for the same applicant can't both get the same number.
        conn.execute(
            """
            INSERT INTO applications (
                id, applicant_id, application_number, form_id, treatment, cost, requested_term, income,
                housing_cost, existing_obligations, household, partner_income, status, created_at
            )
            SELECT
                :id, :applicant_id, COALESCE(MAX(application_number), 0) + 1, :form_id, :treatment, :cost,
                :requested_term, :income, :housing_cost, :existing_obligations, :household,
                :partner_income, :status, :created_at
            FROM applications WHERE applicant_id = :applicant_id
            """,
            {
                "id": application_id,
                "applicant_id": hash_applicant_number(submission.applicant_number),
                "form_id": FORM_ID,
                "treatment": submission.treatment_value(),
                "cost": submission.cost,
                "requested_term": submission.requested_term,
                "income": submission.income,
                "housing_cost": submission.housing_cost,
                "existing_obligations": submission.existing_obligations,
                "household": submission.household.value,
                "partner_income": submission.partner_income,
                "status": "submitted",
                "created_at": db.now_iso(),
            },
        )
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        # Same transaction: an application is never stored without its assessment.
        assess_and_store(conn, row)
        if submission.additional_information:
            conn.execute(
                "INSERT INTO free_text_pending (application_id, text, created_at) VALUES (?, ?, ?)",
                (application_id, submission.additional_information, db.now_iso()),
            )

    # The model call is a network request, so it runs between transactions, not inside one.
    screening = screen(submission.additional_information)

    with db.connect() as conn:
        # Stores the summary and reason, and deletes the raw text in the same transaction.
        store_free_text_review(conn, application_id, screening)
        # The applicant gets their offer and status, never the internal calculation or screening.
        return _statuses(conn, "a.id = ?", application_id)[0]


@router.post(
    "/applications/lookup",
    summary="Look up my applications",
    response_model=list[ApplicationStatus],
    responses={422: {"model": ValidationErrorResponse, "description": "The ID number isn't digits only."}},
)
def lookup_applications(search: ApplicantSearch) -> list[ApplicationStatus]:
    """The applicant's own applications and their current status, newest first.

    Shows a status an employee changed later, too. Internal details (calculation, screening,
    employee names and comments) are left out. The ID number goes in the body, not the URL,
    so it stays out of logs and browser history.
    """
    with db.connect() as conn:
        return _statuses(conn, "a.applicant_id = ?", hash_applicant_number(search.applicant_number))
