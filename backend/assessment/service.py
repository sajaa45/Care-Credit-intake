"""Runs the rule for an application and stores the result with every number it used."""

import json
import sqlite3
import uuid
from decimal import Decimal

import db
from applicant.form import Household

from .free_text import FAILED_REASON, MODEL, PROMPT_VERSION, ScreeningOutcome
from .rules import (
    ANNUAL_INTEREST_RATE,
    REFER_MARGIN,
    RULE_VERSION,
    Applicant,
    assess,
    to_cents,
)


def assess_and_store(conn: sqlite3.Connection, application: sqlite3.Row) -> None:
    """Assess the application, store the assessment and set the application's status to the outcome."""
    applicant = Applicant(
        income=application["income"],
        partner_income=application["partner_income"],
        housing_cost=application["housing_cost"],
        existing_obligations=application["existing_obligations"],
        household=Household(application["household"]),
    )
    result = assess(applicant, application["cost"], application["requested_term"])

    # Everything needed to redo the calculation by hand: the inputs, the constants
    # in force, and each intermediate number. Money is stored as text, never float.
    calculation = {
        "inputs": {
            "cost": application["cost"],
            "requested_term": application["requested_term"],
            "income": application["income"],
            "partner_income": application["partner_income"],
            "housing_cost": application["housing_cost"],
            "existing_obligations": application["existing_obligations"],
            "household": application["household"],
        },
        "constants": {
            "annual_interest_rate": str(ANNUAL_INTEREST_RATE),
            "refer_margin": str(REFER_MARGIN),
            "living_standard_norm": str(result.room.norm),
        },
        "steps": {
            "income_share": str(result.room.income_share.quantize(Decimal("0.0001"))),
            "housing_share": str(result.room.housing_share),
            "norm_share": str(result.room.norm_share),
            "available_room": str(result.room.available),
            "instalment": str(result.instalment),
            "refer_limit": str(to_cents(result.refer_limit)),
            "total_repayable": str(result.schedule.total_repayable),
            "total_interest": str(result.schedule.total_interest),
        },
        # Stored as produced, so the schedule shown later is the one the applicant was offered,
        # even if the rule or rate changes afterwards.
        "schedule": [
            {
                "month": row.month,
                "opening_balance": str(row.opening_balance),
                "instalment": str(row.instalment),
                "interest": str(row.interest),
                "principal": str(row.principal),
                "closing_balance": str(row.closing_balance),
            }
            for row in result.schedule.rows
        ],
    }

    conn.execute(
        """
        INSERT INTO assessments (
            id, application_id, rule_version, outcome, reason, term, instalment, available_room,
            suggested_term, suggested_instalment, calculation, created_at
        ) VALUES (
            :id, :application_id, :rule_version, :outcome, :reason, :term, :instalment, :available_room,
            :suggested_term, :suggested_instalment, :calculation, :created_at
        )
        """,
        {
            "id": str(uuid.uuid4()),
            "application_id": application["id"],
            "rule_version": RULE_VERSION,
            "outcome": result.outcome,
            "reason": result.reason,
            "term": result.term,
            "instalment": str(result.instalment),
            "available_room": str(result.room.available),
            "suggested_term": result.suggested_term,
            "suggested_instalment": str(result.suggested_instalment) if result.suggested_instalment else None,
            "calculation": json.dumps(calculation),
            "created_at": db.now_iso(),
        },
    )
    conn.execute("UPDATE applications SET status = ? WHERE id = ?", (result.outcome, application["id"]))


def store_free_text_review(conn: sqlite3.Connection, application_id: str, screening: ScreeningOutcome) -> None:
    """Store the screening, delete the raw text, and send flagged accepted applications to an employee.

    The model can only ever send a case to a human. It never accepts or declines anything itself,
    and the rule's own assessment stays on record unchanged.
    """
    deleted = conn.execute("DELETE FROM free_text_pending WHERE application_id = ?", (application_id,)).rowcount
    status = conn.execute("SELECT status FROM applications WHERE id = ?", (application_id,)).fetchone()["status"]
    referred_by_flag = screening.needs_review and status == "accept"
    if referred_by_flag:
        conn.execute("UPDATE applications SET status = 'refer' WHERE id = ?", (application_id,))
    conn.execute(
        """
        INSERT INTO free_text_reviews (
            application_id, status, summary, needs_review, reason, referred_by_flag, model, prompt_version,
            created_at, raw_text_deleted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,
            screening.status,
            screening.summary,
            screening.needs_review,
            screening.reason,
            referred_by_flag,
            MODEL,
            PROMPT_VERSION,
            db.now_iso(),
            db.now_iso() if deleted else None,
        ),
    )


def discard_unscreened_free_text() -> None:
    """Delete raw text left behind if the server stopped between storing it and screening it.

    Called at startup, so raw text never outlives a crash. Those applications are flagged like
    any failed screening.
    """
    with db.connect() as conn:
        pending = conn.execute("SELECT application_id FROM free_text_pending").fetchall()
        for row in pending:
            store_free_text_review(
                conn,
                row["application_id"],
                ScreeningOutcome(status="failed", summary=None, needs_review=True, reason=FAILED_REASON),
            )
