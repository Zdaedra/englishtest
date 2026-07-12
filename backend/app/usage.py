"""Per-user estimated AI-cost ledger — the profitability guardrail.

Every billable AI call (phrase scoring, escalation, sequence exam, coach, server
STT) accrues a small estimated cost into a per-user, per-calendar-month counter
(micro-USD). `_check_rate` blocks further paid AI once the user crosses their
plan's monthly cost cap (graceful: the client falls back to self-grade), so even a
worst-case / abusive user can never push AI COGS above a known fraction of revenue.

Costs are FLAT ESTIMATES grounded in measured prompt sizes × the current OpenAI
prices (see TZ-ai-cost-strategy.md), not exact billing — deliberately conservative.
Update EST_USD if the ENGLISH_MODEL_* models or vendor prices change.
"""
from datetime import datetime, timezone

from sqlmodel import Session, select

from . import models

# Flat per-call cost (USD). Derived from system-prompt token counts + ~June-2026
# OpenAI rates: nano $0.10/$0.40, mini $0.40/$1.60 per 1M; STT $0.003/min.
EST_USD: dict[str, float] = {
    "score": 0.000076,            # phrase score, cheap model (gpt-4.1-nano)
    "score_escalated": 0.000379,  # phrase score escalated (nano + gpt-4.1-mini)
    "sequence": 0.000478,         # sequence exam (gpt-4.1-mini)
    "coach": 0.000445,            # AI coach (gpt-4.1-mini)
    "stt": 0.000250,              # one server transcription (~5s @ gpt-4o-mini-transcribe)
    "analyze": 0.002000,          # call-analyzer pass (~2k in / 500 out @ gpt-4.1-mini)
    "scenario": 0.001000,         # arena scene weave (~600 in / 500 out @ gpt-4.1-mini)
    "league": 0.002000,           # league placement, 7 answers in one call (~1.5k in / 800 out @ mini)
    "battle": 0.001500,           # battle/Live pick (~2.5k in / 180 out @ mini). Pool is
                                  # bounded either way: learned ≤160, "all" keyword-prefiltered ≤60.
}


def _period() -> int:
    n = datetime.now(timezone.utc)
    return n.year * 100 + n.month   # e.g. 202606


def score_key(via: str) -> str | None:
    """Map a scoring `via` to its cost key (gate/cache/fallback => no API cost)."""
    if via == "llm:escalated":
        return "score_escalated"
    if via == "llm":
        return "score"
    return None


def sequence_key(via: str) -> str | None:
    return "sequence" if via in ("llm", "llm:escalated") else None


def coach_key(via: str) -> str | None:
    return "coach" if via == "llm" else None


def month_cost_usd(session: Session, user_id: int) -> float:
    row = session.exec(select(models.UsageLedger).where(
        models.UsageLedger.user_id == user_id,
        models.UsageLedger.period == _period())).first()
    return (row.micros / 1_000_000.0) if row else 0.0


def accrue(session: Session, user_id: int, *keys: str | None) -> None:
    """Add the cost of the given call components to this month's ledger. Added to
    the session but NOT committed — rides the caller's transaction."""
    usd = sum(EST_USD.get(k, 0.0) for k in keys if k)
    if usd <= 0:
        return
    micros = int(round(usd * 1_000_000))
    period = _period()
    row = session.exec(select(models.UsageLedger).where(
        models.UsageLedger.user_id == user_id,
        models.UsageLedger.period == period)).first()
    if row:
        row.micros += micros
        row.updated_at = datetime.now(timezone.utc)
    else:
        row = models.UsageLedger(user_id=user_id, period=period, micros=micros)
    session.add(row)
