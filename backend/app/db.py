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
    # owner_id: NULL keeps every existing batch in the shared curated catalog;
    # only user imports set it (private). Added with no FK clause (SQLite ALTER).
    if "owner_id" not in cols:
        s.execute(text("ALTER TABLE batch ADD COLUMN owner_id INTEGER"))
        s.commit()

    # Per-user scoping (commercial multi-user): add user_id to the per-user event
    # tables on existing DBs. The old per-user columns on `phrase` are left in
    # place but orphaned — the model no longer maps them (state moved to
    # userphrasestat, created by create_all alongside the user table).
    for tbl in ("phraseattempt", "sequenceattempt", "reviewevent", "batchprogress",
                "trainingevent", "playbacksession"):
        info = s.execute(text(f"PRAGMA table_info({tbl})")).all()
        if info and "user_id" not in {row[1] for row in info}:
            s.execute(text(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER DEFAULT 0"))
            s.commit()

    # Owner/admin flag on existing user tables (new DBs get it via create_all).
    uinfo = s.execute(text("PRAGMA table_info(user)")).all()
    if uinfo and "is_admin" not in {row[1] for row in uinfo}:
        s.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
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
