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
    # Freemium: one catalog batch is fully free (rest need a paid plan).
    if "is_free" not in cols:
        s.execute(text("ALTER TABLE batch ADD COLUMN is_free BOOLEAN DEFAULT 0"))
        s.commit()
    # Content i18n: per-language JSON blobs (NULL = no translations yet → fall back
    # to the base ru field). See app/localize.py / app/i18n_content.py.
    for col in ("title_i18n", "subtitle_i18n", "theme_i18n"):
        if col not in cols:
            s.execute(text(f"ALTER TABLE batch ADD COLUMN {col} JSON"))
            s.commit()
    zcols = {row[1] for row in s.execute(text("PRAGMA table_info(zone)")).all()}
    if zcols and "title_i18n" not in zcols:
        s.execute(text("ALTER TABLE zone ADD COLUMN title_i18n JSON"))
        s.commit()
    pcols = {row[1] for row in s.execute(text("PRAGMA table_info(phrase)")).all()}
    if pcols and "gloss_i18n" not in pcols:
        s.execute(text("ALTER TABLE phrase ADD COLUMN gloss_i18n JSON"))
        s.commit()
    # LLM-generated active-recall prompt (RU scene + task), cached per phrase.
    for col in ("situation_ru", "task_ru"):
        if pcols and col not in pcols:
            s.execute(text(f"ALTER TABLE phrase ADD COLUMN {col} VARCHAR DEFAULT ''"))
            s.commit()
    # Drop legacy single-user phrase-stat columns. They moved to UserPhraseStat in the
    # multi-tenant refactor, but old prod DBs kept them — and `srs_status` is NOT NULL
    # with no default, which broke EVERY new phrase INSERT (i.e. batch imports). Current
    # code reads none of these on Phrase. DROP COLUMN needs SQLite ≥ 3.35; swallow per
    # column so an unsupported/blocked drop never breaks startup.
    for col in ("srs_status", "avg_score", "attempts", "last_score", "last_seen_at",
                "self_ewma", "last_failed_at", "last_success_at"):
        if pcols and col in pcols:
            try:
                s.execute(text(f"ALTER TABLE phrase DROP COLUMN {col}"))
                s.commit()
            except Exception:
                s.rollback()
    mcols = {row[1] for row in s.execute(text("PRAGMA table_info(mnemostory)")).all()}
    for col in ("story_i18n", "spans_i18n"):
        if mcols and col not in mcols:
            s.execute(text(f"ALTER TABLE mnemostory ADD COLUMN {col} JSON"))
            s.commit()

    # SM-2-lite spaced-repetition schedule on the per-user phrase state. Existing
    # rows default to interval 0 / ease 2.3 / reps 0 / next_review NULL → they get
    # seeded from avg_score the first time they're scored (see app/srs.py).
    spcols = {row[1] for row in s.execute(text("PRAGMA table_info(userphrasestat)")).all()}
    if spcols:
        if "interval_days" not in spcols:
            s.execute(text("ALTER TABLE userphrasestat ADD COLUMN interval_days FLOAT DEFAULT 0"))
            s.commit()
        if "ease" not in spcols:
            s.execute(text("ALTER TABLE userphrasestat ADD COLUMN ease FLOAT DEFAULT 2.3"))
            s.commit()
        if "reps" not in spcols:
            s.execute(text("ALTER TABLE userphrasestat ADD COLUMN reps INTEGER DEFAULT 0"))
            s.commit()
        if "next_review_at" not in spcols:
            s.execute(text("ALTER TABLE userphrasestat ADD COLUMN next_review_at DATETIME"))
            s.commit()
        if "latency_ewma_ms" not in spcols:
            s.execute(text("ALTER TABLE userphrasestat ADD COLUMN latency_ewma_ms FLOAT"))
            s.commit()
        if "shown_count" not in spcols:
            s.execute(text("ALTER TABLE userphrasestat ADD COLUMN shown_count INTEGER DEFAULT 0"))
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
    ucols = {row[1] for row in uinfo}
    if uinfo and "is_admin" not in ucols:
        s.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
        s.commit()
    # UI language preference (NULL = let the client decide / device default).
    if uinfo and "ui_lang" not in ucols:
        s.execute(text("ALTER TABLE user ADD COLUMN ui_lang VARCHAR"))
        s.commit()
    # Billing (Apple IAP) columns.
    if uinfo and "plan_source" not in ucols:
        s.execute(text("ALTER TABLE user ADD COLUMN plan_source VARCHAR DEFAULT 'manual'"))
        s.commit()
    if uinfo and "plan_expires_at" not in ucols:
        s.execute(text("ALTER TABLE user ADD COLUMN plan_expires_at DATETIME"))
        s.commit()
    if uinfo and "apple_original_tx_id" not in ucols:
        s.execute(text("ALTER TABLE user ADD COLUMN apple_original_tx_id VARCHAR"))
        s.commit()
    # Mandatory email verification. Backfill existing accounts to verified (1) so
    # the new gate never locks out anyone who registered before it shipped; only
    # fresh signups (created with email_verified=0) must confirm.
    if uinfo and "email_verified" not in ucols:
        s.execute(text("ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 1"))
        s.commit()

    # Two-axis batch management: on_path (curated learning path) + activated (deck).
    # One-time backfill (consilium P0): everything currently "engaged" stays on the
    # path AND in the deck. The deck source switches from isEngaged → activated, so
    # we MUST also set activated for engaged rows — otherwise users who did lessons
    # but never pressed Activate would silently lose their practice deck + review pool.
    bpinfo = s.execute(text("PRAGMA table_info(batchprogress)")).all()
    if bpinfo and "on_path" not in {row[1] for row in bpinfo}:
        s.execute(text("ALTER TABLE batchprogress ADD COLUMN on_path BOOLEAN DEFAULT 0"))
        s.execute(text("ALTER TABLE batchprogress ADD COLUMN on_path_at DATETIME"))
        engaged = ("activated=1 OR l1_listened=1 OR l1_retold=1 "
                   "OR l3_s1=1 OR l3_s2=1 OR l3_passed=1")
        s.execute(text(f"UPDATE batchprogress SET on_path=1, activated=1 WHERE {engaged}"))
        s.execute(text("UPDATE batchprogress SET on_path_at=COALESCE(on_path_at, activated_at, updated_at) WHERE on_path=1"))
        s.execute(text("UPDATE batchprogress SET activated_at=COALESCE(activated_at, updated_at) WHERE activated=1"))
        s.commit()
    # Manual path order (drag), synced cross-device. NULL = computed order.
    if bpinfo and "path_rank" not in {row[1] for row in bpinfo}:
        s.execute(text("ALTER TABLE batchprogress ADD COLUMN path_rank INTEGER"))
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
