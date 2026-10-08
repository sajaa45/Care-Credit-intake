"""Applicant identifiers are stored only as a keyed hash.

A plain SHA-256 of a short number can be reversed by hashing every possible
number, so we use HMAC with a secret key: the same number always gives the same
hash (so repeat applications link to one applicant), but without the key the
hash can't be traced back to the number.

Changing the key breaks the link between existing hashes and new submissions,
so in production it would live in a secrets manager and never be rotated casually.
"""

import hashlib
import hmac
import os

# Prototype fallback so the app runs out of the box; set APPLICANT_ID_KEY for anything real.
_KEY = os.environ.get("APPLICANT_ID_KEY", "dev-only-key-do-not-use-in-production").encode()


def hash_applicant_number(applicant_number: str) -> str:
    return hmac.new(_KEY, applicant_number.encode(), hashlib.sha256).hexdigest()
