import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("INTAKE_DB", os.path.join(os.path.dirname(__file__), "intake.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id                      TEXT PRIMARY KEY,
    applicant_id            TEXT NOT NULL,
    application_number      INTEGER NOT NULL,
    treatment               TEXT NOT NULL,
    cost                    INTEGER NOT NULL,
    requested_term          INTEGER NOT NULL,
    income                  INTEGER NOT NULL,
    housing_cost            INTEGER NOT NULL,
    existing_obligations    INTEGER NOT NULL,
    household               TEXT NOT NULL,
    partner_income          INTEGER,
    additional_information  TEXT NOT NULL DEFAULT '',
    status                  TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    UNIQUE (applicant_id, application_number)
);

-- One row per run of the affordability rule. Money is TEXT (exact decimals, never float);
-- `calculation` is JSON with every input, constant and intermediate step.
CREATE TABLE IF NOT EXISTS assessments (
    id                    TEXT PRIMARY KEY,
    application_id        TEXT NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    rule_version          TEXT NOT NULL,
    outcome               TEXT NOT NULL CHECK (outcome IN ('accept', 'refer', 'decline')),
    reason                TEXT NOT NULL,
    term                  INTEGER NOT NULL,
    instalment            TEXT NOT NULL,
    available_room        TEXT NOT NULL,
    suggested_term        INTEGER,
    suggested_instalment  TEXT,
    calculation           TEXT NOT NULL,
    created_at            TEXT NOT NULL
);

-- Employee decisions. Append-only: a later decision overrides an earlier one by being newer,
-- never by editing it, so the full history of who changed what, and why, is kept.
CREATE TABLE IF NOT EXISTS decisions (
    id               TEXT PRIMARY KEY,
    application_id   TEXT NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    employee         TEXT NOT NULL,
    previous_status  TEXT NOT NULL,
    outcome          TEXT NOT NULL CHECK (outcome IN ('accept', 'decline')),
    comment          TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
"""


def now_iso(moment: datetime | None = None) -> str:
    """UTC timestamp in one fixed format, so stored values sort and compare correctly as text."""
    return (moment or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="microseconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Off by default in SQLite; needed so deleting an application also deletes its assessments.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
