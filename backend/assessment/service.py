"""Runs the rule for an application and stores the result with every number it used."""

import json
import sqlite3
import uuid
from decimal import Decimal

import db
from applicant.form import Household

from .rules import (
    ANNUAL_INTEREST_RATE,
    REFER_MARGIN,
    RULE_VERSION,
    Applicant,
    assess,
    to_cents,
)


def assess_and_store(conn: sqlite3.Connection, application: sqlite3.Row) -> sqlite3.Row:
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

    assessment_id = str(uuid.uuid4())
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
            "id": assessment_id,
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
    return conn.execute("SELECT * FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
