"""Schema migration: the legacy single-user `phrase.srs_status` column (NOT NULL,
no default) must be dropped so the normal phrase-insert / import path works. This is
a core-invariant (import parse→commit) fix per the testing rule."""
import os
import tempfile

from sqlalchemy import create_engine, text
from sqlmodel import SQLModel, Session

import app.models  # noqa: F401 — registers tables on SQLModel.metadata
from app.db import _migrate


def test_migrate_drops_legacy_phrase_stat_columns():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        eng = create_engine(f"sqlite:///{path}")
        SQLModel.metadata.create_all(eng)
        with Session(eng) as s:
            # Simulate the legacy columns old prod DBs still carry (the NOT NULL one
            # is what broke every new INSERT).
            s.execute(text("ALTER TABLE phrase ADD COLUMN srs_status VARCHAR NOT NULL DEFAULT 'new'"))
            s.execute(text("ALTER TABLE phrase ADD COLUMN avg_score FLOAT"))
            s.commit()
            before = {r[1] for r in s.execute(text("PRAGMA table_info(phrase)")).all()}
            assert "srs_status" in before and "avg_score" in before

            _migrate(s)

            after = {r[1] for r in s.execute(text("PRAGMA table_info(phrase)")).all()}
            assert "srs_status" not in after, "legacy NOT-NULL srs_status must be dropped"
            assert "avg_score" not in after
            # The real import path (ORM insert, no srs_status) now succeeds.
            b = app.models.Batch(title="t", slug="t-mig")
            s.add(b); s.commit(); s.refresh(b)
            s.add(app.models.Phrase(batch_id=b.id, order_index=1, anchor="a",
                                    phrase_en="b", gloss_ru="c", intensity_score=0.0))
            s.commit()
    finally:
        os.remove(path)
