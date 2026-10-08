"""
Both the GET /form response and the submission validation are built from this, 
so the questions shown to the applicant and the rules enforced on their
answers can't drift apart.
"""

import hashlib
import json
from enum import Enum

class TreatmentType(str, Enum):
    dental = "dental"
    eye = "eye"
    orthodontic = "orthodontic"
    other = "other"


class Household(str, Enum):
    single = "single"
    single_with_children = "single_with_children"
    couple = "couple"
    couple_with_children = "couple_with_children"


PARTNER_HOUSEHOLDS = {Household.couple, Household.couple_with_children}


TREATMENT_LABELS = {
    TreatmentType.dental: "Dental",
    TreatmentType.eye: "Eye",
    TreatmentType.orthodontic: "Orthodontic",
    TreatmentType.other: "Other",
}

HOUSEHOLD_LABELS = {
    Household.single: "Single",
    Household.single_with_children: "Single with children",
    Household.couple: "Couple",
    Household.couple_with_children: "Couple with children",
}

# Whole euros / months only. The loan amount and term bounds come from the
# product definition; the monthly amounts only get a very high ceiling so an
# absurd value is rejected with a clear message instead of reaching the database.
MAX_MONTHLY_AMOUNT = 1_000_000

INTEGER_RANGES = {
    "cost": (500, 25_000),
    "requested_term": (6, 60),
    "income": (0, MAX_MONTHLY_AMOUNT),
    "housing_cost": (0, MAX_MONTHLY_AMOUNT),
    "existing_obligations": (0, MAX_MONTHLY_AMOUNT),
    "partner_income": (0, MAX_MONTHLY_AMOUNT),
}

APPLICANT_NUMBER_MAX_LENGTH = 20
TREATMENT_OTHER_MAX_LENGTH = 100
FREE_TEXT_MAX_LENGTH = 2_000


def _integer_question(field: str, label: str, unit: str) -> dict:
    lo, hi = INTEGER_RANGES[field]
    return {"field": field, "label": label, "type": "integer", "unit": unit, "min": lo, "max": hi, "required": True}


def _choice_question(field: str, label: str, labels: dict) -> dict:
    return {
        "field": field,
        "label": label,
        "type": "choice",
        "required": True,
        "options": [{"value": k.value, "label": v} for k, v in labels.items()],
    }


QUESTIONS = [
    {
        "field": "applicant_number",
        "label": "Your ID number",
        "type": "digits",
        "required": True,
        "max_length": APPLICANT_NUMBER_MAX_LENGTH,
    },
    _choice_question("treatment", "Type of treatment", TREATMENT_LABELS),
    {
        "field": "treatment_other",
        "label": "Which treatment is it?",
        "type": "short_text",
        "required": True,
        "max_length": TREATMENT_OTHER_MAX_LENGTH,
        "show_when": {"field": "treatment", "values": [TreatmentType.other.value]},
    },
    _integer_question("cost", "Cost of the treatment", "EUR"),
    _integer_question("requested_term", "Preferred repayment term", "months"),
    _integer_question("income", "Your net monthly income", "EUR"),
    _integer_question("housing_cost", "Monthly housing costs (rent or mortgage)", "EUR"),
    _integer_question("existing_obligations", "Total monthly payments on existing loans and credit", "EUR"),
    _choice_question("household", "Household situation", HOUSEHOLD_LABELS),
    {
        **_integer_question("partner_income", "Your partner's net monthly income", "EUR"),
        "show_when": {"field": "household", "values": sorted(h.value for h in PARTNER_HOUSEHOLDS)},
    },
    {
        "field": "additional_information",
        "label": "Is there anything else we should know about your situation?",
        "type": "text",
        "required": False,
        "max_length": FREE_TEXT_MAX_LENGTH,
    },
]


# Identifies the exact questions, labels, options and limits: any edit to a question gives a new id,
# with nothing to remember to bump.
FORM_ID = hashlib.sha256(json.dumps(QUESTIONS, sort_keys=True).encode()).hexdigest()


def form_definition() -> dict:
    return {"id": FORM_ID, "questions": QUESTIONS}
