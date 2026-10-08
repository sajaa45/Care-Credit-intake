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
"""


def now_iso(moment: datetime | None = None) -> str:
    """UTC timestamp in one fixed format, so stored values sort and compare correctly as text."""
    return (moment or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="microseconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
