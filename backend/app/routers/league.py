"""League placement 2.0 — production answers instead of multiple choice.

The user answers each of the 7 situations in their own English (voice transcript
or typed); ONE LLM call grades all answers against an explicit 4-criteria rubric
(idiom / register / economy / move — see scoring._LEAGUE_SYSTEM) and returns a
native-league upgrade line per answer. This is the pre-paywall placement test, so
it is open to every plan — abuse is bounded by a small per-user daily run cap
instead of an entitlement gate.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from .. import entitlements, scoring, usage
from ..auth import current_user_id
from ..db import get_session

router = APIRouter(prefix="/api/league", tags=["league"])

_MAX_ANSWER_CHARS = 400
_MAX_ITEMS = 10
_DAILY_RUNS = 3

# Per-process daily counter {user_id: (date, runs)}. A restart forgives the
# count — fine for a $0.002 placement call; the point is bounding abuse loops.
#
# It is deliberately soft, but on its own it was the ONLY guard here, and we
# redeploy several times on a busy day, so in practice the cap barely existed.
# The durable backstop is the monthly estimated-AI-cost ceiling that every other
# paid-AI endpoint already checks (training._check_rate) — league accrued cost to
# that ledger but never looked at it. Both now apply: the dict bounds a tight
# loop within one process, the ledger bounds the month across restarts.
_runs: dict[int, tuple[date, int]] = {}


class LeagueAnswer(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    situation: str = Field(min_length=1, max_length=400)
    text: str = Field(default="", max_length=_MAX_ANSWER_CHARS)


class LeagueIn(BaseModel):
    answers: list[LeagueAnswer] = Field(min_length=1, max_length=_MAX_ITEMS)


def _tier(avg: float) -> str:
    if avg < 4:
        return "functional"
    if avg < 6.5:
        return "confident"
    if avg < 8.5:
        return "sharp"
    return "native"


@router.post("/score")
def score(data: LeagueIn, user_id: int = Depends(current_user_id),
          session: Session = Depends(get_session)):
    if not any(a.text.strip() for a in data.answers):
        raise HTTPException(400, "empty")

    today = date.today()
    day, runs = _runs.get(user_id, (today, 0))
    if day != today:
        runs = 0
    if runs >= _DAILY_RUNS:
        raise HTTPException(429, "Daily league limit reached.")

    budget = entitlements.user_entitlements(session, user_id).get("monthly_ai_cost_cap_usd")
    if budget is not None and usage.month_cost_usd(session, user_id) >= budget:
        raise HTTPException(429, "Monthly AI limit reached.")

    graded = scoring.league_score([a.model_dump() for a in data.answers])
    if graded["via"] != "llm":
        raise HTTPException(503, "scoring_unavailable")

    _runs[user_id] = (today, runs + 1)
    usage.accrue(session, user_id, "league")
    session.commit()

    results = graded["results"]
    scores = [r["score"] for r in results]
    avg = sum(scores) / len(scores) if scores else 0.0
    return {
        "tier": _tier(avg),
        "avg": round(avg, 1),
        "results": results,
    }
