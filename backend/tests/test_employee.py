import unittest

from fastapi import HTTPException
from pydantic import ValidationError

from employee.router import record_decision
from employee.schemas import DecisionRequest
from helpers import DatabaseTestCase


def decision(outcome: str, comment: str = "Checked the payslips.", employee: str = "J. de Vries") -> DecisionRequest:
    return DecisionRequest(outcome=outcome, comment=comment, employee=employee)


class Overrides(DatabaseTestCase):
    def test_employee_can_overturn_in_either_direction_and_history_is_kept(self):
        application = self.submit()  # accepted by the rule
        record_decision(application.id, decision("decline", "Income could not be verified."))
        result = record_decision(application.id, decision("accept", "Employer confirmed the contract."))

        self.assertEqual(result.status, "accept")
        self.assertEqual(
            [(d.previous_status, d.outcome) for d in result.decisions], [("accept", "decline"), ("decline", "accept")]
        )
        self.assertEqual(result.assessment.outcome, "accept")  # the system's conclusion is never edited

    def test_a_referred_application_can_be_decided(self):
        # Room €250 (2000 - 600 - 1150); €5,000 over 20 months is €269.92, within 10% over.
        application = self.submit(cost=5000, requested_term=20, income=2000, housing_cost=600, existing_obligations=0)
        self.assertEqual(application.status, "refer")
        self.assertEqual(record_decision(application.id, decision("accept")).status, "accept")

    def test_every_decision_needs_a_reason_and_a_name(self):
        for changes in ({"comment": "  "}, {"employee": ""}):
            with self.subTest(**changes), self.assertRaises(ValidationError):
                decision("accept", **changes)
        with self.assertRaises(ValidationError):
            decision("refer")  # employees accept or decline; referring is the system's job

    def test_unknown_application_is_not_found(self):
        with self.assertRaises(HTTPException) as caught:
            record_decision("no-such-id", decision("accept"))
        self.assertEqual(caught.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
