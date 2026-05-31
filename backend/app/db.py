from collections.abc import Iterator

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from .config import get_settings
from . import models  # noqa: F401  (register tables)

_settings = get_settings()
_engine = create_engine(
    f"sqlite:///{_settings.db_path}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def _migrate(s: Session) -> None:
    # Lightweight additive migrations: create_all never ALTERs existing tables,
    # so new columns on old DBs must be added by hand.
    cols = {row[1] for row in s.execute(text("PRAGMA table_info(batch)")).all()}
    if "cover_path" not in cols:
        s.execute(text("ALTER TABLE batch ADD COLUMN cover_path VARCHAR"))
        s.commit()
    if "subtitle" not in cols:
        s.execute(text("ALTER TABLE batch ADD COLUMN subtitle VARCHAR DEFAULT ''"))
        s.commit()
    if "section" not in cols:
        s.execute(text("ALTER TABLE batch ADD COLUMN section VARCHAR DEFAULT ''"))
        s.commit()

    # Feedback-training rollup columns on phrase (Test B).
    pcols = {row[1] for row in s.execute(text("PRAGMA table_info(phrase)")).all()}
    if "avg_score" not in pcols:
        s.execute(text("ALTER TABLE phrase ADD COLUMN avg_score FLOAT"))
        s.commit()
    if "attempts" not in pcols:
        s.execute(text("ALTER TABLE phrase ADD COLUMN attempts INTEGER DEFAULT 0"))
        s.commit()
    if "last_score" not in pcols:
        s.execute(text("ALTER TABLE phrase ADD COLUMN last_score INTEGER"))
        s.commit()
    if "last_seen_at" not in pcols:
        s.execute(text("ALTER TABLE phrase ADD COLUMN last_seen_at DATETIME"))
        s.commit()


def init_db() -> None:
    SQLModel.metadata.create_all(_engine)
    with Session(_engine) as s:
        _migrate(s)
        # ensure singleton Setting row
        existing = s.exec(select(models.Setting).where(models.Setting.id == 1)).first()
        if existing is None:
            s.add(models.Setting(id=1))
            s.commit()


def get_session() -> Iterator[Session]:
    with Session(_engine) as session:
        yield session


def engine() -> Engine:
    return _engine
