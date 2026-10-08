"""Shared setup for tests that need a database: each test gets its own empty file."""

import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import db
from applicant.router import submit_application
from applicant.schemas import IntakeSubmission
from assessment.free_text import ScreeningOutcome
from employee.router import list_applications

# A single applicant whose €3,500 over 24 months is accepted (room €600, instalment €159.74).
VALID = dict(
    applicant_number="123456789",
    treatment="dental",
    cost=3500,
    requested_term=24,
    income=2800,
    housing_cost=900,
    existing_obligations=150,
    household="single",
)

NOTHING_WRITTEN = ScreeningOutcome(status="skipped", summary=None, needs_review=False, reason="Left empty.")


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.addCleanup(os.remove, self.db_path)
        patcher = mock.patch.object(db, "DB_PATH", self.db_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        db.init_db()

    def submit(self, screening=NOTHING_WRITTEN, **answers):
        """Submit an application with the model call replaced (by a fixed result, or a function),
        and return it as an employee sees it: the applicant's response leaves out the internals."""
        replacement = {"side_effect": screening} if callable(screening) else {"return_value": screening}
        with mock.patch("applicant.router.screen", **replacement):
            submit_application(IntakeSubmission(**{**VALID, **answers}))
        return self.latest_application()

    def latest_application(self):
        return list_applications()[0]

    def database_dump(self) -> str:
        """Everything in the database as SQL text, to check what is (not) stored anywhere."""
        conn = sqlite3.connect(self.db_path)
        try:
            return "\n".join(conn.iterdump())
        finally:
            conn.close()
