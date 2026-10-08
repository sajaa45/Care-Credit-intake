from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

import db

router = APIRouter(prefix="/compliance", tags=["Compliance"])

RETENTION_YEARS = 7


def retention_cutoff(now: datetime) -> datetime:
    """The moment exactly RETENTION_YEARS ago; 29 February falls back to 28 February."""
    try:
        return now.replace(year=now.year - RETENTION_YEARS)
    except ValueError:
        return now.replace(year=now.year - RETENTION_YEARS, day=28)


class PurgeResult(BaseModel):
    cutoff: datetime = Field(description="Applications created before this moment are past retention.")
    dry_run: bool
    application_ids: list[str] = Field(description="The applications that were (or, in a dry run, would be) deleted.")


@router.post("/retention/purge", summary="Delete applications past the retention period", response_model=PurgeResult)
def purge_expired(dry_run: bool = True) -> PurgeResult:
    """Delete every application created more than 7 years ago.
    The memo's rule is 7 years **after the loan is closed**. Loan closing isn't modelled yet, so
    `created_at` is used as a stand-in; once a closed date exists, the cutoff should apply to that.
    """
    cutoff = retention_cutoff(datetime.now(timezone.utc))
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id FROM applications WHERE created_at < ? ORDER BY created_at", (db.now_iso(cutoff),)
        ).fetchall()
        ids = [row["id"] for row in rows]
        if ids and not dry_run:
            conn.executemany("DELETE FROM applications WHERE id = ?", [(i,) for i in ids])
    return PurgeResult(cutoff=cutoff, dry_run=dry_run, application_ids=ids)
