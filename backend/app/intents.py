"""Conversational-move (intent) taxonomy for Live mode.

The relevance axis is the MOVE, not word overlap: every dictated moment maps
to a conversational move (осадить, попросить, удержать позицию…), the LLM
ranks the top moves for the moment, the user can override with one tap, and
the candidate pool is prefiltered to batches whose SECTION serves that move.

A batch's "answer type" derives from Batch.section via SECTION_INTENTS —
zero content migration; imported/custom batches (empty section) serve every
intent. The key list is FIXED: prompt, client chips and tests all speak it.
"""

# key -> RU gloss (prompt-side; the client localizes labels itself)
INTENTS: dict[str, str] = {
    "pushback": "осадить / не согласиться",
    "hold": "удержать позицию",
    "ask": "попросить / добиться",
    "warm": "расположить",
    "buy_time": "выиграть время",
    "clarify": "уточнить / переспросить",
    "close": "зафиксировать / закрыть",
    "smooth": "сгладить / извиниться",
}

SECTION_INTENTS: dict[str, tuple[str, ...]] = {
    "live-tone": ("pushback", "clarify", "hold"),
    "pressure": ("pushback", "hold", "buy_time"),
    "negotiation": ("hold", "close", "buy_time", "clarify"),
    "composure": ("hold", "buy_time"),
    "gravitas": ("hold",),
    "lead-presence": ("hold",),
    "leadership": ("hold", "ask"),
    "requests": ("ask",),
    "small-talk": ("warm",),
    "charisma": ("warm",),
    "flirt": ("warm",),
    "intimacy": ("warm", "smooth"),
    "repair": ("smooth",),
    "pitch": ("close",),
    "stage": ("close", "hold"),
    "written": ("clarify", "ask"),
}

_MIN_POOL = 8


def filter_rows(rows, intent: str):
    """Rows whose batch section serves the intent; sectionless batches always
    qualify. Falls back to ALL rows when the filter leaves too little to pick
    from — a starved pool gives the LLM nothing to work with."""
    keep = []
    for r in rows:
        sec = (r[2].section or "").strip()
        if not sec or intent in SECTION_INTENTS.get(sec, ()):
            keep.append(r)
    return keep if len(keep) >= _MIN_POOL else rows
