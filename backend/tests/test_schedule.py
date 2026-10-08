import random
import unittest
from decimal import Decimal

from assessment.rules import MAX_TERM, MIN_TERM, monthly_instalment, repayment_schedule

ZERO = Decimal("0.00")

# Boundaries and awkward amounts, plus a fixed random sample across the whole product range.
PRINCIPALS = [500, 501, 999, 1000, 1234, 3333, 3500, 9999, 12345, 24999, 25000]
PRINCIPALS += random.Random(42).sample(range(500, 25001), 100)


class ScheduleAddsUp(unittest.TestCase):
    def check(self, principal: int, months: int):
        schedule = repayment_schedule(principal, months)
        rows = schedule.rows
        with self.subTest(principal=principal, months=months):
            self.assertEqual(len(rows), months)
            self.assertEqual(rows[-1].closing_balance, ZERO)
            self.assertEqual(sum(r.principal for r in rows), Decimal(principal))
            self.assertEqual(schedule.total_repayable, sum(r.instalment for r in rows))
            self.assertEqual(schedule.total_repayable, Decimal(principal) + schedule.total_interest)
            for previous, row in zip(rows, rows[1:]):
                self.assertEqual(row.opening_balance, previous.closing_balance)
            for row in rows:
                self.assertEqual(row.instalment, row.interest + row.principal)
                self.assertEqual(row.closing_balance, row.opening_balance - row.principal)
                # Everything is whole cents, nothing finer.
                for amount in (row.instalment, row.interest, row.principal, row.closing_balance):
                    self.assertEqual(amount, amount.quantize(Decimal("0.01")))

    def test_every_term_for_a_spread_of_amounts(self):
        for principal in PRINCIPALS:
            for months in range(MIN_TERM, MAX_TERM + 1):
                self.check(principal, months)

    def test_only_the_final_instalment_differs_by_less_than_a_cent_per_month(self):
        for principal in PRINCIPALS:
            for months in (MIN_TERM, 24, MAX_TERM):
                rows = repayment_schedule(principal, months).rows
                instalment = monthly_instalment(principal, months)
                with self.subTest(principal=principal, months=months):
                    self.assertTrue(all(r.instalment == instalment for r in rows[:-1]))
                    # Rounding the instalment moves it by at most half a cent a month, so the
                    # final adjustment can't exceed a cent per month of term.
                    self.assertLess(abs(rows[-1].instalment - instalment), Decimal("0.01") * months)

    def test_known_example(self):
        schedule = repayment_schedule(3500, 24)
        self.assertEqual(schedule.rows[0].interest, Decimal("25.96"))  # 3500 * 0.089 / 12 = 25.958…
        self.assertEqual(schedule.rows[0].instalment, Decimal("159.74"))
        self.assertEqual(schedule.rows[-1].instalment, Decimal("159.65"))
        self.assertEqual(schedule.total_interest, Decimal("333.67"))
        self.assertEqual(schedule.total_repayable, Decimal("3833.67"))


if __name__ == "__main__":
    unittest.main()
