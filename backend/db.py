import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("INTAKE_DB", os.path.join(os.path.dirname(__file__), "intake.db"))

SCHEMA = """
-- Every form ever answered, word for word, so an application always shows what we asked.
CREATE TABLE IF NOT EXISTS forms (
    id          TEXT PRIMARY KEY,  -- sha256 of the question definitions
    version     TEXT NOT NULL,
    definition  TEXT NOT NULL,     -- JSON: questions, labels, options, limits
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    id                      TEXT PRIMARY KEY,
    applicant_id            TEXT NOT NULL,
    application_number      INTEGER NOT NULL,
    form_id                 TEXT NOT NULL REFERENCES forms (id),
    treatment               TEXT NOT NULL,
    cost                    INTEGER NOT NULL,
    requested_term          INTEGER NOT NULL,
    income                  INTEGER NOT NULL,
    housing_cost            INTEGER NOT NULL,
    existing_obligations    INTEGER NOT NULL,
    household               TEXT NOT NULL,
    partner_income          INTEGER,
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

-- The applicant's raw free-text answer, held only until the model has read it. It may contain
-- medical detail, so it lives apart from the permanent record and is deleted after screening.
CREATE TABLE IF NOT EXISTS free_text_pending (
    application_id  TEXT PRIMARY KEY REFERENCES applications (id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

-- The model's reading of the free-text answer, one per application: what's kept once the raw text is gone.
CREATE TABLE IF NOT EXISTS free_text_reviews (
    application_id      TEXT PRIMARY KEY REFERENCES applications (id) ON DELETE CASCADE,
    status              TEXT NOT NULL CHECK (status IN ('screened', 'failed', 'skipped')),
    summary             TEXT,
    needs_review        INTEGER NOT NULL,
    reason              TEXT NOT NULL,
    referred_by_flag    INTEGER NOT NULL,  -- 1 if the flag turned the rule's 'accept' into 'refer'
    model               TEXT NOT NULL,
    prompt_version      TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    raw_text_deleted_at TEXT  -- null only when there was no text to delete
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
