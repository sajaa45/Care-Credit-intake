import os
import sqlite3
import unittest
from unittest import mock

from applicant.router import submit_application
from applicant.schemas import IntakeSubmission
from assessment.free_text import ScreeningOutcome
from assessment.service import discard_unscreened_free_text
from compliance.router import application_record
from helpers import VALID, DatabaseTestCase

RAW_TEXT = "I have diabetes and my contract ends in March."
FLAGGED = ScreeningOutcome(
    status="screened",
    summary="Fixed-term contract ending in March.",
    needs_review=True,
    reason="The contract ends in March, so income after that is uncertain.",
)
NOT_FLAGGED = ScreeningOutcome(
    status="screened", summary="Has been saving for the treatment.", needs_review=False, reason="Nothing affects repayment."
)


class RawTextIsDeleted(DatabaseTestCase):
    def test_raw_text_is_held_during_screening_and_gone_after(self):
        seen_during_call = []

        def screen(text):
            conn = sqlite3.connect(self.db_path)
            seen_during_call.extend(row[0] for row in conn.execute("SELECT text FROM free_text_pending"))
            conn.close()
            return FLAGGED

        application = self.submit(screening=screen, additional_information=RAW_TEXT)

        self.assertEqual(seen_during_call, [RAW_TEXT])
        self.assertNotIn("diabetes", self.database_dump())
        review = application_record(application.id).free_text_review
        self.assertEqual(review.summary, FLAGGED.summary)
        self.assertIsNotNone(review.raw_text_deleted_at)

    def test_failed_screening_still_deletes_the_text_and_flags_it(self):
        # With a key but no answer from Groq, the call fails safely and says why in the log (never the text).
        with (
            mock.patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}),
            mock.patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")),
            self.assertLogs("uvicorn.error", "WARNING") as logs,
        ):
            submit_application(IntakeSubmission(**VALID, additional_information=RAW_TEXT))
        self.assertNotIn("diabetes", "".join(logs.output))
        application = self.latest_application()

        self.assertNotIn("diabetes", self.database_dump())
        self.assertEqual(application.status, "refer")
        self.assertEqual(application_record(application.id).free_text_review.status, "failed")

    def test_without_an_api_key_the_call_is_stubbed_and_says_so(self):
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": ""}), mock.patch("urllib.request.urlopen") as urlopen:
            submit_application(IntakeSubmission(**VALID, additional_information=RAW_TEXT))
        application = self.latest_application()

        urlopen.assert_not_called()
        self.assertEqual(application.free_text_review.status, "stubbed")
        self.assertIn("GROQ_API_KEY", application.free_text_review.reason)
        self.assertEqual(application.status, "accept")  # a stub never changes the decision
        self.assertNotIn("diabetes", self.database_dump())

    def test_text_left_behind_by_a_crash_is_deleted_at_startup(self):
        # The state after a crash: application and raw text stored, screening never finished.
        application = self.submit()
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM free_text_reviews WHERE application_id = ?", (application.id,))
        conn.execute(
            "INSERT INTO free_text_pending VALUES (?, ?, ?)", (application.id, RAW_TEXT, "2026-01-01T00:00:00+00:00")
        )
        conn.commit()
        conn.close()

        discard_unscreened_free_text()

        self.assertNotIn("diabetes", self.database_dump())
        self.assertTrue(application_record(application.id).free_text_review.needs_review)


class FlagOnlyEscalates(DatabaseTestCase):
    def test_flag_sends_an_accepted_application_to_review(self):
        application = self.submit(screening=FLAGGED, additional_information=RAW_TEXT)
        self.assertEqual(application.status, "refer")
        self.assertEqual(application.assessment.outcome, "accept")  # the rule's own result stays on record

    def test_no_flag_keeps_the_accept(self):
        application = self.submit(screening=NOT_FLAGGED, additional_information="I've been saving up.")
        self.assertEqual(application.status, "accept")

    def test_flag_never_changes_a_decline(self):
        application = self.submit(screening=FLAGGED, additional_information=RAW_TEXT, cost=25_000, requested_term=6)
        self.assertEqual(application.status, "decline")


if __name__ == "__main__":
    unittest.main()
