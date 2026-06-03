"""Pre-warm the TTS/audio cache for the 76 presence batches.

Calls the SAME route functions the app hits (batches.mnemo_audio /
batches.phrase_audio) so the content-addressed cache keys match exactly — the
first tap on the device is then instant. Idempotent and resumable: cached assets
are reused, so re-running only fills gaps. Cost-bearing (OpenAI TTS) — runs over
all presence batches; safe to interrupt.

    python -m app.warm_presence
"""
from sqlmodel import Session, select

from . import models
from .db import engine, init_db
from .routers import batches as B

PRESENCE = {
    "charisma", "flirt", "intimacy", "lead-presence",
    "composure", "gravitas", "stage",
}


def main() -> None:
    init_db()
    with Session(engine()) as s:
        rows = s.exec(
            select(models.Batch).where(models.Batch.deleted_at == None)  # noqa: E711
            .order_by(models.Batch.id)
        ).all()
        targets = [b for b in rows if b.section in PRESENCE]
        print(f"Warming {len(targets)} presence batches")
        for b in targets:
            ok_layouts = []
            for layout in ("full", "anchors", "shuffle"):
                try:
                    B.mnemo_audio(b.id, layout=layout, session=s)
                    ok_layouts.append(layout)
                except Exception as e:  # noqa: BLE001
                    print(f"    mnemo #{b.id} {layout}: {type(e).__name__} {e}")
            phrases = s.exec(
                select(models.Phrase).where(models.Phrase.batch_id == b.id)
            ).all()
            ok_ph = 0
            for p in phrases:
                try:
                    B.phrase_audio(p.id, session=s)
                    ok_ph += 1
                except Exception as e:  # noqa: BLE001
                    print(f"    phrase #{p.id} ({b.slug}): {type(e).__name__} {e}")
            print(f"  #{b.id} {b.slug:14s} mnemo[{','.join(ok_layouts)}] + {ok_ph}/{len(phrases)} phrases")
    print("DONE")


if __name__ == "__main__":
    main()
