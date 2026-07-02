"""Call Analyzer (AI plan): paste notes/transcript of a real work call, get up to
5 native-league phrasing upgrades. The Fluently-style bridge from the app to the
user's actual meetings — upgrades feed the import flow to become trainable phrases.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from .. import scoring, usage
from ..auth import current_user_id
from ..db import get_session
from ..entitlements import user_entitlements

router = APIRouter(prefix="/api/analyzer", tags=["analyzer"])

_MIN_CHARS = 40
_MAX_CHARS = 8000


class CallIn(BaseModel):
    text: str


@router.post("/call")
def analyze_call(body: CallIn, user_id: int = Depends(current_user_id),
                 session: Session = Depends(get_session)):
    ents = user_entitlements(session, user_id)
    if not ents.get("ai_coach"):
        raise HTTPException(403, "locked")
    text = (body.text or "").strip()
    if len(text) < _MIN_CHARS:
        raise HTTPException(400, "too_short")
    budget = ents.get("monthly_ai_cost_cap_usd")
    if budget is not None and usage.month_cost_usd(session, user_id) >= budget:
        raise HTTPException(429, "Monthly AI limit reached.")
    res = scoring.analyze_call(text[:_MAX_CHARS])
    if res["via"] == "llm":
        usage.accrue(session, user_id, "analyze")
        session.commit()
    return res
