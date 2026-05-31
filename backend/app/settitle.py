"""Set explicit, hand-chosen batch titles (no LLM).

Sibling to `retitle` (LLM-suggested) — this one writes exact titles you pass in,
for when the card title should be a curated short *skill* name and the mnemonic
image lives in the subtitle. Idempotent.

Usage:
    python -m app.settitle 1="Несогласие" 2="Узнать мнение" 3="Тактичная эмпатия"
    python -m app.settitle --dry-run 1="Несогласие"
"""
import sys

from sqlmodel import Session

from . import models
from .db import engine, init_db


def _parse(pairs: list[str]) -> dict[int, str]:
    out: dict[int, str] = {}
    for p in pairs:
        if "=" not in p:
            raise SystemExit(f"bad pair {p!r}; expected <id>=<title>")
        sid, title = p.split("=", 1)
        out[int(sid)] = title.strip()
    return out


def run(titles: dict[int, str], *, dry: bool) -> list[tuple[int, str, str]]:
    init_db()
    rows: list[tuple[int, str, str]] = []
    with Session(engine()) as s:
        for bid, new in titles.items():
            b = s.get(models.Batch, bid)
            if not b:
                rows.append((bid, "—", "NOT FOUND"))
                continue
            rows.append((bid, b.title, new))
            if new and not dry:
                b.title = new
                s.add(b)
        if not dry:
            s.commit()
    return rows


def main(argv: list[str]) -> None:
    dry = "--dry-run" in argv
    pairs = [a for a in argv if "=" in a]
    if not pairs:
        print('usage: python -m app.settitle <id>="Title" [...] [--dry-run]')
        return
    rows = run(_parse(pairs), dry=dry)
    for bid, old, new in rows:
        print(f"#{bid}: {old!r} -> {new!r}")
    print("DRY-RUN — no changes written" if dry else f"COMMITTED {len(rows)} batch(es)")


if __name__ == "__main__":
    main(sys.argv[1:])
