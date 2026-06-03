"""Load ONLY the 76 presence batches into the DB — business batches 01-13 untouched.

The full `app.seed` loads every content/*.json and upserts by slug, which would
clobber the business leadership-1/leadership-2 batches (presence files now use
distinct slugs lead-1..11, but this script is the belt-and-suspenders guarantee:
it loads a file ONLY if its section is one of the 7 presence directions).

auto_cover=False here so the load stays fast/predictable; covers are a separate
explicit step (`python -m app.gencovers`). auto_subtitle=True fills the
mnemonic-image subtitle (cheap LLM, consistent with business batches).

    python -m app.seed_presence
"""
import json

from sqlmodel import Session

from .content import BatchAuthor, content_dir, to_batch_in, upsert
from .db import engine, init_db

PRESENCE = {
    "charisma", "flirt", "intimacy", "lead-presence",
    "composure", "gravitas", "stage",
}


def main() -> None:
    init_db()
    paths = []
    for p in sorted(content_dir().glob("*.json")):
        try:
            sec = json.loads(p.read_text(encoding="utf-8")).get("section", "")
        except Exception:  # noqa: BLE001
            sec = ""
        if sec in PRESENCE:
            paths.append(p)

    print(f"Presence files to load: {len(paths)} (business 01-13 skipped)")
    created_n = updated_n = 0
    with Session(engine()) as s:
        for p in paths:
            data = json.loads(p.read_text(encoding="utf-8"))
            author = BatchAuthor(**data)
            batch_in, warnings = to_batch_in(author)
            # No LLM during load: titles are provided in JSON (auto_title only fills
            # when missing), subtitle/cover are deferred to separate steps. Keeps the
            # load bulletproof regardless of the host LLM provider config.
            batch, created = upsert(
                s, batch_in, slug=author.slug,
                auto_title=True, auto_subtitle=False, auto_cover=False,
            )
            created_n += created
            updated_n += not created
            verb = "created" if created else "updated"
            print(f"  {verb}: #{batch.id} {batch.slug:14s} [{batch.section}] «{batch.title}»")
            for w in warnings:
                print(f"        ⚠ {w}")
    print(f"DONE: {created_n} created, {updated_n} updated")


if __name__ == "__main__":
    main()
