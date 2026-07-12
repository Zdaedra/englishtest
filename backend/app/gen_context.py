"""Generate per-phrase RU active-recall prompts (situation + task), cached on the
Phrase row. Two-stage for quality (the consilium's generate→critique pattern):
  1. GPT (gpt-4o-mini) drafts {situation_ru, task_ru} from the phrase context.
  2. Claude (via meridian, or anthropic key) reviews & polishes — ensures the scene
     unambiguously leads to the target, the task names the right communicative
     function (opener vs reply vs pushback), and the English form is never leaked.

The card FRONT then shows СИТУАЦИЯ + ЗАДАЧА (RU) instead of an ambiguous English
stimulus; phrase_en is revealed only after answering.

Run (inside the app container / venv):
    python -m app.gen_context --batch 12        # one batch (validate first)
    python -m app.gen_context                    # all phrases missing context
    python -m app.gen_context --force            # regenerate everything
"""
import argparse
import json
from typing import Optional

import httpx
from sqlmodel import Session, select

from . import llm, models
from .config import get_secrets, get_settings
from .db import engine, init_db

_DRAFT_SYSTEM = (
    "Ты — методист приложения Executive English (учим деловому и светскому "
    "английскому носителями русского). Для ЦЕЛЕВОЙ фразы придумай русскую "
    "карточку-подсказку для активного припоминания: короткую СИТУАЦИЮ (1–2 "
    "предложения — конкретная живая сцена: где ты, с кем, что происходит) и "
    "ЗАДАЧУ (одно повелительное предложение: что ты хочешь сделать этой репликой "
    "— например открыть разговор, поддержать, мягко возразить, перехватить "
    "инициативу). Правила: пиши на «ты», живо и конкретно; НЕ переводи и НЕ "
    "упоминай английскую фразу или её слова; ситуация должна естественно "
    "подводить к тому, чтобы человек сам произнёс целевую фразу; не раскрывай "
    "ответ. Верни СТРОГО JSON {\"situation_ru\": str, \"task_ru\": str} без markdown."
)

_POLISH_SYSTEM = (
    "Ты — придирчивый редактор методических карточек Executive English. Тебе дают "
    "контекст целевой фразы и ЧЕРНОВИК русской подсказки. Улучши: (1) СИТУАЦИЯ — "
    "конкретная живая сцена на «ты», однозначно подводящая к нужной реплике; "
    "(2) ЗАДАЧА — одно ясное повелительное предложение про коммуникативное "
    "намерение, точно отражающее ФУНКЦИЮ фразы (это опенер? ответ на чью-то "
    "реплику? возражение? просьба?); (3) убери любое раскрытие или перевод "
    "английской фразы; (4) коротко, естественно, без канцелярита. Верни СТРОГО "
    "JSON {\"situation_ru\": str, \"task_ru\": str} без markdown."
)


def _ctx(phrase: models.Phrase, batch: models.Batch, zone: Optional[models.Zone]) -> str:
    parts = [
        f"Тема батча: {batch.title}" + (f" — {batch.theme}" if batch.theme else ""),
        f"Тон/зона: {zone.title} ({zone.intensity_label})" if zone else "",
        f"Якорь: {phrase.anchor}",
        f"Целевая фраза (НЕ показывать ученику — только для понимания смысла): \"{phrase.phrase_en}\"",
        f"Значение по-русски: {phrase.gloss_ru}" if phrase.gloss_ru else "",
    ]
    return "\n".join(p for p in parts if p)


def _claude(system: str, user: str) -> str:
    """Claude polish: prefer a direct Anthropic key when present (local runs), else
    the meridian proxy (free Claude on the Hetzner host). meridian needs no key."""
    s = get_settings(); sec = get_secrets()
    if sec.anthropic_api_key and s.llm_provider != "meridian":
        return llm._anthropic_call(sec.anthropic_base_url, sec.anthropic_api_key,
                                   system, user, temperature=0.4)
    httpx.get(s.meridian_url, timeout=1.5)   # raises if unreachable → caller falls back to draft
    return llm._anthropic_call(s.meridian_url, None, system, user, temperature=0.4)


def _parse(raw: str) -> dict:
    d = json.loads(llm._strip_json(raw))
    return {"situation_ru": str(d.get("situation_ru", "")).strip(),
            "task_ru": str(d.get("task_ru", "")).strip()}


def generate_one(phrase: models.Phrase, batch: models.Batch,
                 zone: Optional[models.Zone]) -> dict:
    ctx = _ctx(phrase, batch, zone)
    sec = get_secrets()
    # Stage 1 — GPT draft.
    draft = _parse(llm._openai_call(sec.openai_api_key, _DRAFT_SYSTEM, ctx, temperature=0.7))
    # Stage 2 — Claude polish (falls back to the draft if Claude is unavailable).
    try:
        polish_user = (f"{ctx}\n\nЧЕРНОВИК:\n"
                       f"{json.dumps(draft, ensure_ascii=False)}")
        out = _parse(_claude(_POLISH_SYSTEM, polish_user))
        if out["situation_ru"] and out["task_ru"]:
            return out
    except Exception as e:  # noqa: BLE001
        print(f"  (polish skipped: {e})")
    return draft


def run(batch_id: Optional[int] = None, force: bool = False, limit: Optional[int] = None) -> None:
    init_db()
    done = 0
    with Session(engine()) as session:
        bq = select(models.Batch).where(models.Batch.deleted_at == None)  # noqa: E711
        if batch_id:
            bq = bq.where(models.Batch.id == batch_id)
        batches = session.exec(bq.order_by(models.Batch.id)).all()
        zones = {z.id: z for z in session.exec(select(models.Zone)).all()}
        for b in batches:
            phrases = session.exec(select(models.Phrase)
                                   .where(models.Phrase.batch_id == b.id)
                                   .order_by(models.Phrase.order_index)).all()
            for p in phrases:
                if p.situation_ru and p.task_ru and not force:
                    continue
                try:
                    res = generate_one(p, b, zones.get(p.zone_id) if p.zone_id else None)
                except Exception as e:  # noqa: BLE001
                    print(f"[batch {b.id} phrase {p.id} {p.anchor}] ERROR: {e}")
                    continue
                p.situation_ru = res["situation_ru"]
                p.task_ru = res["task_ru"]
                session.add(p); session.commit()
                done += 1
                print(f"[batch {b.id} #{p.order_index} {p.anchor}] {p.situation_ru} || {p.task_ru}")
                if limit and done >= limit:
                    print(f"\nDone {done} (limit reached).")
                    return
    print(f"\nDone {done} phrase(s).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    run(batch_id=args.batch, force=args.force, limit=args.limit)
    from .doctor import verdict
    verdict("after gen_context")
