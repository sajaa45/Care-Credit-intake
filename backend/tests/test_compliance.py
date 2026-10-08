import sqlite3
import unittest
from datetime import datetime, timezone

from applicant.form import QUESTIONS
from compliance.router import application_record, purge_expired, retention_cutoff
from employee.router import record_decision
from employee.schemas import DecisionRequest
from helpers import DatabaseTestCase


class Record(DatabaseTestCase):
    def test_record_shows_what_was_asked_answered_concluded_and_done(self):
        application = self.submit()
        record_decision(application.id, DecisionRequest(outcome="decline", comment="Fraud check.", employee="A. Bakker"))
        record = application_record(application.id)

        # What we asked, word for word, and what the applicant answered.
        self.assertEqual([a.question for a in record.answers], [q["label"] for q in QUESTIONS])
        answers = {a.field: a for a in record.answers}
        self.assertEqual(answers["cost"].answer, "3500 EUR")
        self.assertIsNone(answers["partner_income"].answer)  # single applicant: not asked
        self.assertIsNone(answers["applicant_number"].answer)  # never stored, only its hash

        # What the system concluded, and every number it was based on.
        steps = record.assessments[0].calculation["steps"]
        self.assertEqual(steps["available_room"], "600.00")  # 2800 - 900 - 150 - 1150
        self.assertEqual(steps["instalment"], "159.74")
        self.assertEqual(record.assessments[0].outcome, "accept")

        # What an employee did afterwards, and the order of events.
        self.assertEqual(record.decisions[0].comment, "Fraud check.")
        self.assertEqual([e.event for e in record.timeline], ["Submitted", "System: accept", "Employee: accept → decline"])


class Retention(DatabaseTestCase):
    def test_cutoff_is_seven_years_and_handles_29_february(self):
        self.assertEqual(retention_cutoff(datetime(2033, 5, 1, tzinfo=timezone.utc)).year, 2026)
        self.assertEqual(retention_cutoff(datetime(2028, 2, 29, tzinfo=timezone.utc)).date().isoformat(), "2021-02-28")

    def test_purge_is_a_dry_run_unless_asked_and_removes_everything_about_the_application(self):
        old = self.submit()
        record_decision(old.id, DecisionRequest(outcome="decline", comment="Old.", employee="A. Bakker"))
        recent = self.submit()

        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE applications SET created_at = '2019-01-01T00:00:00.000000+00:00' WHERE id = ?", (old.id,))
        conn.commit()
        conn.close()

        self.assertEqual(purge_expired().application_ids, [old.id])
        self.assertIn(old.id, self.database_dump())  # dry run: nothing deleted

        purge_expired(dry_run=False)
        dump = self.database_dump()
        self.assertNotIn(old.id, dump)  # assessments, decisions and screening went with it
        self.assertIn(recent.id, dump)


if __name__ == "__main__":
    unittest.main()
