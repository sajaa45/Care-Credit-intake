import unittest
from decimal import Decimal

from applicant.form import Household
from assessment.rules import Applicant, assess, available_room, monthly_instalment, outcome_for


class OutcomeBoundaries(unittest.TestCase):
    def test_instalment_equal_to_room_is_accepted(self):
        self.assertEqual(outcome_for(Decimal("250.00"), Decimal("250.00")), "accept")

    def test_exactly_ten_percent_over_is_referred(self):
        self.assertEqual(outcome_for(Decimal("275.00"), Decimal("250.00")), "refer")

    def test_one_cent_past_ten_percent_is_declined(self):
        self.assertEqual(outcome_for(Decimal("275.01"), Decimal("250.00")), "decline")

    def test_no_room_is_declined(self):
        self.assertEqual(outcome_for(Decimal("10.00"), Decimal("0.00")), "decline")


class Instalment(unittest.TestCase):
    def test_annuity_at_8_9_percent(self):
        # 3500 over 24 months at 8.9%/year: 159.736... rounds to 159.74
        self.assertEqual(monthly_instalment(3500, 24), Decimal("159.74"))


class Room(unittest.TestCase):
    def test_single_carries_everything(self):
        room = available_room(Applicant(2000, None, 600, 100, Household.single))
        self.assertEqual(room.available, Decimal("150.00"))  # 2000 - 600 - 100 - 1150

    def test_couple_splits_housing_and_norm_by_income_share(self):
        room = available_room(Applicant(2800, 2100, 1200, 150, Household.couple))
        self.assertEqual(room.housing_share, Decimal("685.71"))  # 1200 * 2800/4900
        self.assertEqual(room.norm_share, Decimal("914.29"))  # 1600 * 2800/4900
        self.assertEqual(room.available, Decimal("1050.00"))

    def test_partner_without_income_means_applicant_carries_everything(self):
        room = available_room(Applicant(3000, 0, 1000, 0, Household.couple))
        self.assertEqual(room.available, Decimal("400.00"))  # 3000 - 1000 - 1600

    def test_no_household_income_does_not_divide_by_zero(self):
        room = available_room(Applicant(0, 0, 0, 0, Household.couple))
        self.assertEqual(room.available, Decimal("-1600.00"))


class TermSuggestion(unittest.TestCase):
    def test_suggests_shortest_longer_term_that_is_accepted(self):
        result = assess(Applicant(2000, None, 600, 0, Household.single), 5000, 12)  # room 250
        self.assertEqual(result.outcome, "decline")
        self.assertEqual(result.suggested_term, 22)
        self.assertLessEqual(result.suggested_instalment, Decimal("250.00"))
        self.assertGreater(monthly_instalment(5000, 21), Decimal("250.00"))

    def test_no_suggestion_when_nothing_fits(self):
        result = assess(Applicant(1500, None, 600, 100, Household.single), 5000, 12)  # room -350
        self.assertIsNone(result.suggested_term)

    def test_no_suggestion_when_accepted(self):
        result = assess(Applicant(2800, 2100, 1200, 150, Household.couple), 3500, 24)
        self.assertEqual(result.outcome, "accept")
        self.assertIsNone(result.suggested_term)


if __name__ == "__main__":
    unittest.main()
