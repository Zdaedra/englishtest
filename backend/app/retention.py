"""Data-minimisation: auto-purge old voice transcripts (free text of spoken
answers) while keeping numeric scores/progress. Runs as an in-process daily task
on the single container (no extra infra). Idempotent — purges by absolute cutoff,
so a missed run just catches up on the next startup."""
import asyncio

from sqlalchemy import text
from sqlmodel import Session

from .config import get_settings
from .db import engine

# SQLModel default (lowercased) table names carrying user free-text.
_TRANSCRIPT_TABLES = ("phraseattempt", "sequenceattempt", "trainingevent")


def purge_old_transcripts(days: int | None = None) -> int:
    """Blank the transcript text (and trainingevent.ai_feedback) on rows older than
    `days`. Returns how many rows were cleared. No-op if retention is disabled."""
    d = int(days if days is not None else get_settings().transcript_retention_days)
    if d <= 0:
        return 0
    off = f"-{d} days"
    total = 0
    with Session(engine()) as s:
        for t in _TRANSCRIPT_TABLES:
            r = s.execute(text(
                f"UPDATE {t} SET transcript='' "
                "WHERE transcript != '' AND created_at < datetime('now', :off)"), {"off": off})
            total += r.rowcount or 0
        r = s.execute(text(
            "UPDATE trainingevent SET ai_feedback='' "
            "WHERE ai_feedback != '' AND created_at < datetime('now', :off)"), {"off": off})
        total += r.rowcount or 0
        s.commit()
    return total


async def retention_loop() -> None:
    """Purge shortly after startup, then once a day."""
    while True:
        try:
            purge_old_transcripts()
        except Exception:
            pass  # never let retention crash the app
        await asyncio.sleep(24 * 3600)


if __name__ == "__main__":  # manual run: python -m app.retention
    print("purged:", purge_old_transcripts())
