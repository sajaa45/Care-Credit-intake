import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

import db
from applicant.identity import hash_applicant_number
from applicant.schemas import Application, Assessment, NotFoundResponse
from employee.schemas import Decision, FreeTextReview

from .schemas import AnsweredQuestion, ApplicantSearch, ApplicationSummary, ComplianceRecord, TimelineEvent

router = APIRouter(prefix="/compliance", tags=["Compliance"])

_SUMMARY_QUERY = """
    SELECT a.id, a.applicant_id, a.application_number, a.treatment, a.cost, a.requested_term, a.status,
           a.created_at, EXISTS (SELECT 1 FROM decisions d WHERE d.application_id = a.id) AS decided_by_employee
    FROM applications a
"""


@router.get("/applications", summary="List all applications", response_model=list[ApplicationSummary])
def list_applications() -> list[ApplicationSummary]:
    """Every application on record, newest first."""
    with db.connect() as conn:
        rows = conn.execute(_SUMMARY_QUERY + " ORDER BY a.created_at DESC").fetchall()
    return [ApplicationSummary(**dict(row)) for row in rows]


@router.post("/applications/search", summary="Find an applicant's applications", response_model=list[ApplicationSummary])
def search_applications(search: ApplicantSearch) -> list[ApplicationSummary]:
    """All applications for one ID number, newest first.

    A POST with the number in the body rather than a GET with it in the URL, so the ID number
    doesn't end up in server logs or browser history.
    """
    with db.connect() as conn:
        rows = conn.execute(
            _SUMMARY_QUERY + " WHERE a.applicant_id = ? ORDER BY a.created_at DESC",
            (hash_applicant_number(search.applicant_number),),
        ).fetchall()
    return [ApplicationSummary(**dict(row)) for row in rows]


def _answers(
    questions: list[dict], application: sqlite3.Row, review: FreeTextReview | None
) -> list[AnsweredQuestion]:
    """Pair each question as it was asked with the stored answer."""
    treatment = application["treatment"]
    standard_treatments = {
        option["value"]: option["label"] for q in questions if q["field"] == "treatment" for option in q["options"]
    }
    chose_other = treatment not in standard_treatments

    answers = []
    for q in questions:
        field, note = q["field"], None
        if field == "additional_information":
            answer = None
            if review is None or review.status == "skipped":
                note = "Left empty (optional question)."
            elif review.status == "screened":
                note = (
                    f"Raw text deleted after screening ({review.raw_text_deleted_at:%Y-%m-%d %H:%M} UTC). "
                    "Kept: the summary and reason under 'Free-text answer'."
                )
            else:
                note = f"Raw text deleted ({review.raw_text_deleted_at:%Y-%m-%d %H:%M} UTC) without being screened."
        elif field == "applicant_number":
            answer = None
            note = f"Not stored. Kept only as a keyed hash: {application['applicant_id']}"
        elif field == "treatment":
            answer = standard_treatments["other"] if chose_other else standard_treatments[treatment]
        elif field == "treatment_other":
            answer = treatment if chose_other else None
        elif q["type"] == "choice":
            labels = {option["value"]: option["label"] for option in q["options"]}
            answer = labels.get(application[field], application[field])
        elif q["type"] == "integer":
            value = application[field]
            answer = None if value is None else f"{value} {q['unit']}"
        else:
            answer = application[field]
        if answer == "":
            answer, note = None, "Left empty (optional question)."
        elif answer is None and note is None:
            note = "Not asked: didn't apply to this applicant."
        answers.append(AnsweredQuestion(field=field, question=q["label"], answer=answer, note=note))
    return answers


@router.get(
    "/applications/{application_id}/record",
    summary="Full record of an application",
    response_model=ComplianceRecord,
    responses={404: {"model": NotFoundResponse, "description": "No application with this id."}},
)
def application_record(application_id: str) -> ComplianceRecord:
    """What we asked, what the applicant answered, what the system concluded and on what basis,
    and what any employee did afterwards, with a timeline of everything that happened."""
    with db.connect() as conn:
        application = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        if application is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
        form = conn.execute("SELECT * FROM forms WHERE id = ?", (application["form_id"],)).fetchone()
        assessments = conn.execute(
            "SELECT * FROM assessments WHERE application_id = ? ORDER BY created_at", (application_id,)
        ).fetchall()
        decisions = conn.execute(
            "SELECT * FROM decisions WHERE application_id = ? ORDER BY created_at", (application_id,)
        ).fetchall()
        review = conn.execute("SELECT * FROM free_text_reviews WHERE application_id = ?", (application_id,)).fetchone()

    review = FreeTextReview(**dict(review)) if review else None
    assessments = [Assessment.from_row(a) for a in assessments]
    decisions = [Decision(**dict(d)) for d in decisions]

    timeline = [TimelineEvent(at=application["created_at"], event="Submitted", detail=f"Form version {form['version']}")]
    timeline += [
        TimelineEvent(at=a.created_at, event=f"System: {a.outcome}", detail=f"Rule {a.rule_version}. {a.reason}")
        for a in assessments
    ]
    if review and review.status != "skipped":
        flag = "flagged for review" if review.needs_review else "nothing flagged"
        referred = " The accept was turned into a referral." if review.referred_by_flag else ""
        timeline.append(
            TimelineEvent(
                at=review.created_at,
                event=f"Free text {review.status}: {flag}",
                detail=f"{review.model}, prompt {review.prompt_version}. {review.reason}{referred}",
            )
        )
    if review and review.raw_text_deleted_at:
        timeline.append(
            TimelineEvent(
                at=review.raw_text_deleted_at,
                event="Raw free text deleted",
                detail="Only the summary and reason are kept, so no medical detail stays on record.",
            )
        )
    timeline += [
        TimelineEvent(
            at=d.created_at,
            event=f"Employee: {d.previous_status} → {d.outcome}",
            detail=f"{d.employee}: {d.comment}",
        )
        for d in decisions
    ]
    timeline.sort(key=lambda event: event.at)

    return ComplianceRecord(
        application=Application(**dict(application), assessment=assessments[-1] if assessments else None),
        form_id=form["id"],
        form_version=form["version"],
        answers=_answers(json.loads(form["definition"]), application, review),
        assessments=assessments,
        free_text_review=review,
        decisions=decisions,
        timeline=timeline,
    )

RETENTION_YEARS = 7


def retention_cutoff(now: datetime) -> datetime:
    """The moment exactly RETENTION_YEARS ago; 29 February falls back to 28 February."""
    try:
        return now.replace(year=now.year - RETENTION_YEARS)
    except ValueError:
        return now.replace(year=now.year - RETENTION_YEARS, day=28)


class PurgeResult(BaseModel):
    cutoff: datetime = Field(description="Applications created before this moment are past retention.")
    dry_run: bool
    application_ids: list[str] = Field(description="The applications that were (or, in a dry run, would be) deleted.")


@router.post("/retention/purge", summary="Delete applications past the retention period", response_model=PurgeResult)
def purge_expired(dry_run: bool = True) -> PurgeResult:
    """Delete every application created more than 7 years ago.
    The memo's rule is 7 years **after the loan is closed**. Loan closing isn't modelled yet, so
    `created_at` is used as a stand-in; once a closed date exists, the cutoff should apply to that.
    """
    cutoff = retention_cutoff(datetime.now(timezone.utc))
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id FROM applications WHERE created_at < ? ORDER BY created_at", (db.now_iso(cutoff),)
        ).fetchall()
        ids = [row["id"] for row in rows]
        if ids and not dry_run:
            conn.executemany("DELETE FROM applications WHERE id = ?", [(i,) for i in ids])
    return PurgeResult(cutoff=cutoff, dry_run=dry_run, application_ids=ids)
