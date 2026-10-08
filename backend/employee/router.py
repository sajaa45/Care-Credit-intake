import sqlite3
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, status

import db
from applicant.schemas import Assessment, NotFoundResponse, ValidationErrorResponse

from .schemas import Decision, DecisionRequest, ReviewedApplication

router = APIRouter(prefix="/employee", tags=["Employee"])

Status = Literal["submitted", "accept", "refer", "decline"]


def _load(conn: sqlite3.Connection, applications: list[sqlite3.Row]) -> list[ReviewedApplication]:
    """Attach each application's latest assessment and all its decisions."""
    result = []
    for application in applications:
        assessment = conn.execute(
            "SELECT * FROM assessments WHERE application_id = ? ORDER BY created_at DESC LIMIT 1", (application["id"],)
        ).fetchone()
        decisions = conn.execute(
            "SELECT * FROM decisions WHERE application_id = ? ORDER BY created_at", (application["id"],)
        ).fetchall()
        result.append(
            ReviewedApplication(
                **dict(application),
                assessment=Assessment.from_row(assessment) if assessment else None,
                decisions=[Decision(**dict(d)) for d in decisions],
            )
        )
    return result


@router.get("/applications", summary="List applications", response_model=list[ReviewedApplication])
def list_applications(status: Status | None = None) -> list[ReviewedApplication]:
    """All applications, newest first, with their assessment and decisions. Filter with `status`, e.g. `refer`."""
    query = "SELECT * FROM applications"
    params: tuple = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    with db.connect() as conn:
        return _load(conn, conn.execute(query + " ORDER BY created_at DESC", params).fetchall())


@router.post(
    "/applications/{application_id}/decisions",
    summary="Record a decision",
    status_code=status.HTTP_201_CREATED,
    response_model=ReviewedApplication,
    responses={
        404: {"model": NotFoundResponse, "description": "No application with this id."},
        422: {"model": ValidationErrorResponse, "description": "Missing comment or employee, or unknown outcome."},
    },
)
def record_decision(application_id: str, decision: DecisionRequest) -> ReviewedApplication:
    """Accept or decline an application, whatever the system concluded, with a required comment.

    Works in either direction (e.g. accept a declined application, or decline an accepted one) and
    on referred applications. The decision becomes the application's status; earlier assessments and
    decisions are kept, never changed.
    """
    with db.connect() as conn:
        application = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        if application is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
        conn.execute(
            """
            INSERT INTO decisions (id, application_id, employee, previous_status, outcome, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                application_id,
                decision.employee,
                application["status"],
                decision.outcome,
                decision.comment,
                db.now_iso(),
            ),
        )
        conn.execute("UPDATE applications SET status = ? WHERE id = ?", (decision.outcome, application_id))
        updated = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        return _load(conn, [updated])[0]
