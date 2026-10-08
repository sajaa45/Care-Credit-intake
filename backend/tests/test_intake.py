import unittest

from pydantic import ValidationError

from applicant.schemas import ApplicantOffer, ApplicationStatus, IntakeSubmission
from helpers import VALID


def submission(**changes) -> IntakeSubmission:
    return IntakeSubmission(**{**VALID, **changes})


class Validation(unittest.TestCase):
    def test_amounts_must_be_whole_numbers(self):
        for value in (3500.5, 3500.0, "3500", True):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                submission(cost=value)

    def test_cost_and_term_stay_within_the_product_range(self):
        for changes in ({"cost": 499}, {"cost": 25_001}, {"requested_term": 5}, {"requested_term": 61}):
            with self.subTest(**changes), self.assertRaises(ValidationError):
                submission(**changes)
        submission(cost=500, requested_term=6)
        submission(cost=25_000, requested_term=60)

    def test_couples_must_give_partner_income_and_singles_never_store_one(self):
        with self.assertRaises(ValidationError):
            submission(household="couple")
        self.assertEqual(submission(household="couple", partner_income=0).partner_income, 0)
        self.assertIsNone(submission(household="single", partner_income=2100).partner_income)

    def test_other_treatment_needs_a_description_which_becomes_the_treatment(self):
        with self.assertRaises(ValidationError):
            submission(treatment="other")
        self.assertEqual(submission(treatment="other", treatment_other="Hearing aids").treatment_value(), "Hearing aids")

    def test_id_number_is_digits_only(self):
        for value in ("12AB", "12 34", "", 123456789):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                submission(applicant_number=value)
        self.assertEqual(submission(applicant_number="0042").applicant_number, "0042")


class ApplicantResponse(unittest.TestCase):
    def test_applicant_sees_their_offer_but_never_the_internal_calculation(self):
        visible = set(ApplicationStatus.model_fields) | set(ApplicantOffer.model_fields)
        for internal in ("id", "applicant_id", "calculation", "available_room", "reason", "income"):
            self.assertNotIn(internal, visible)


if __name__ == "__main__":
    unittest.main()
