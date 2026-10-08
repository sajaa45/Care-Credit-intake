"""The affordability rule: accept, refer or decline.

    available room = income - housing - existing obligations - living standard norm

For a household with a partner, the applicant carries their share of the
household: housing and the norm are both multiplied by
income / (income + partner_income). A single applicant's share is 1.

    instalment <= room          -> accept
    instalment <= room * 1.10   -> refer (an employee reviews it)
    otherwise                   -> decline

All money is Decimal and rounded half-up to the cent, so the stored numbers
are exactly the ones the decision was made on.

The repayment schedule charges interest on the outstanding balance each month
(rounded to the cent) and pays the fixed instalment; the final instalment is
whatever is left plus that month's interest. So the closing balance is exactly
zero and the instalments add up to principal + interest to the cent.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from applicant.form import INTEGER_RANGES, Household

# Stored with every assessment. The numbers are stored too, but the logic isn't, so bump this whenever
# the formula, thresholds, norms, rate, rounding or term suggestion change: it's how a decision years
# from now can still be traced to the rule that made it.
RULE_VERSION = "2026-10-08.1"

ANNUAL_INTEREST_RATE = Decimal("0.089")
MONTHLY_INTEREST_RATE = ANNUAL_INTEREST_RATE / 12
REFER_MARGIN = Decimal("0.10")

LIVING_STANDARD_NORMS = {
    Household.single: Decimal(1150),
    Household.single_with_children: Decimal(1400),
    Household.couple: Decimal(1600),
    Household.couple_with_children: Decimal(1850),
}

MIN_TERM, MAX_TERM = INTEGER_RANGES["requested_term"]

CENT = Decimal("0.01")


def to_cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def monthly_instalment(principal: int, months: int) -> Decimal:
    """Standard annuity: principal * r / (1 - (1 + r)^-n), rounded to the cent."""
    r = MONTHLY_INTEREST_RATE
    return to_cents(Decimal(principal) * r / (1 - (1 + r) ** -months))


@dataclass(frozen=True)
class ScheduleRow:
    month: int
    opening_balance: Decimal
    instalment: Decimal
    interest: Decimal
    principal: Decimal
    closing_balance: Decimal


@dataclass(frozen=True)
class Schedule:
    rows: list[ScheduleRow]
    total_repayable: Decimal
    total_interest: Decimal


def repayment_schedule(principal: int, months: int) -> Schedule:
    instalment = monthly_instalment(principal, months)
    balance = Decimal(principal).quantize(CENT)
    rows = []
    for month in range(1, months + 1):
        interest = to_cents(balance * MONTHLY_INTEREST_RATE)
        # The fixed instalment is rounded to the cent, so a few cents of difference build up
        # over the term; the final instalment absorbs them by paying off exactly what's left.
        payment = balance + interest if month == months else instalment
        principal_part = payment - interest
        rows.append(ScheduleRow(month, balance, payment, interest, principal_part, balance - principal_part))
        balance -= principal_part
    return Schedule(
        rows=rows,
        total_repayable=sum((row.instalment for row in rows), Decimal(0)),
        total_interest=sum((row.interest for row in rows), Decimal(0)),
    )


@dataclass(frozen=True)
class Applicant:
    income: int
    partner_income: int | None
    housing_cost: int
    existing_obligations: int
    household: Household


@dataclass(frozen=True)
class Room:
    income_share: Decimal  # applicant's share of household income, 0..1 (unrounded)
    housing_share: Decimal
    norm: Decimal
    norm_share: Decimal
    available: Decimal


def available_room(applicant: Applicant) -> Room:
    income = Decimal(applicant.income)
    partner = Decimal(applicant.partner_income or 0)
    household_income = income + partner
    # With no household income at all there is nothing to split; the applicant carries everything.
    share = income / household_income if household_income else Decimal(1)

    norm = LIVING_STANDARD_NORMS[applicant.household]
    housing_share = to_cents(Decimal(applicant.housing_cost) * share)
    norm_share = to_cents(norm * share)
    available = income - housing_share - Decimal(applicant.existing_obligations) - norm_share
    return Room(share, housing_share, norm, norm_share, available)


def outcome_for(instalment: Decimal, room: Decimal) -> str:
    if instalment <= room:
        return "accept"
    if instalment <= room * (1 + REFER_MARGIN):
        return "refer"
    return "decline"


@dataclass(frozen=True)
class AssessmentResult:
    outcome: str
    reason: str
    room: Room
    term: int
    instalment: Decimal
    refer_limit: Decimal
    schedule: Schedule
    suggested_term: int | None
    suggested_instalment: Decimal | None


def assess(applicant: Applicant, principal: int, requested_term: int) -> AssessmentResult:
    room = available_room(applicant)
    instalment = monthly_instalment(principal, requested_term)
    refer_limit = room.available * (1 + REFER_MARGIN)
    outcome = outcome_for(instalment, room.available)

    # The requested term is a preference: if it doesn't fit, find the shortest longer term that
    # does. Shortest, because every extra month costs the applicant more interest.
    suggested_term = suggested_instalment = None
    if outcome != "accept":
        for term in range(requested_term + 1, MAX_TERM + 1):
            candidate = monthly_instalment(principal, term)
            if outcome_for(candidate, room.available) == "accept":
                suggested_term, suggested_instalment = term, candidate
                break

    if outcome == "accept":
        reason = f"Instalment €{instalment} fits within the available room of €{room.available}."
    elif outcome == "refer":
        reason = (
            f"Instalment €{instalment} exceeds the available room of €{room.available}, "
            f"but by no more than 10% (limit €{to_cents(refer_limit)}): an employee reviews it."
        )
    elif room.available <= 0:
        reason = (
            f"There is no room for an instalment: after housing, existing obligations and the living "
            f"standard norm, the available room is €{room.available}."
        )
    else:
        reason = (
            f"Instalment €{instalment} exceeds the available room of €{room.available} "
            f"by more than 10% (limit €{to_cents(refer_limit)})."
        )

    return AssessmentResult(
        outcome=outcome,
        reason=reason,
        room=room,
        term=requested_term,
        instalment=instalment,
        refer_limit=refer_limit,
        schedule=repayment_schedule(principal, requested_term),
        suggested_term=suggested_term,
        suggested_instalment=suggested_instalment,
    )
