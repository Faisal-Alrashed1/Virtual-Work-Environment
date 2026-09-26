"""
Runs Alembic migrations when the app starts — replaces the old
`Base.metadata.create_all()` call, which could create missing *tables* but
never add a missing *column* to an existing one. That gap is the exact bug
that once stranded graduates on the onboarding screen (a new column with no
migration to backfill it). See docs/MIGRATIONS.md.

Three situations, all handled by upgrade_database():

  1. Fresh, empty database          -> run every migration from scratch.
  2. Database already under Alembic -> run whatever is newer than its version.
  3. "Legacy" database: created by the old create_all() before Alembic
     existed, so it has tables but no alembic_version. It is verified
     against the frozen baseline schema (revision 0001); if it matches it is
     stamped 0001 and upgraded like any other. If it doesn't (a table or
     column is missing — the classic out-of-date dev DB), we stop with a
     plain-language error instead of letting it 500 deep inside a request.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import StaticPool

logger = logging.getLogger("venv.migrations")

BASELINE_REVISION = "0001"
_BACKEND_DIR = Path(__file__).resolve().parent.parent

# Arbitrary constant: lets two API processes that boot at the same moment on
# Postgres take turns migrating instead of racing each other.
_PG_ADVISORY_LOCK_KEY = 7_262_026


class LegacyDatabaseError(RuntimeError):
    """A pre-Alembic database that doesn't match the baseline schema."""


def alembic_config(connection: Connection) -> Config:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    cfg.attributes["connection"] = connection
    cfg.attributes["configure_logger"] = False  # don't reset the app's logging
    return cfg


def _schema_of(connection: Connection) -> dict[str, set[str]]:
    insp = inspect(connection)
    return {
        table: {col["name"] for col in insp.get_columns(table)}
        for table in insp.get_table_names()
        if table != "alembic_version"
    }


def baseline_schema() -> dict[str, set[str]]:
    """What a database looks like at revision 0001, table -> column names.

    Computed by actually running the baseline migration into a throwaway
    in-memory SQLite database, so it can never drift from the migration
    itself (and stays frozen even as later migrations add columns).
    """
    scratch = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    try:
        with scratch.connect() as conn:
            command.upgrade(alembic_config(conn), BASELINE_REVISION)
            conn.commit()
            return _schema_of(conn)
    finally:
        scratch.dispose()


def legacy_schema_problems(connection: Connection) -> list[str]:
    """Missing tables/columns in a pre-Alembic database vs the baseline."""
    have = _schema_of(connection)
    problems = []
    for table, columns in sorted(baseline_schema().items()):
        if table not in have:
            problems.append(f"table '{table}' is missing")
            continue
        for column in sorted(columns - have[table]):
            problems.append(f"column '{table}.{column}' is missing")
    return problems


def _legacy_help(problems: list[str], url: str) -> str:
    listing = "\n".join(f"  - {p}" for p in problems)
    return (
        "This database was created before Venv used migrations, and it is out of date:\n"
        f"{listing}\n\n"
        "Fix it once, then restart:\n"
        "  * Local SQLite dev database: delete the file (it is disposable) and start the app —\n"
        "    it will be rebuilt from the migrations.\n"
        "  * A shared/Postgres database with data you want to keep: add the missing columns by\n"
        "    hand (ALTER TABLE ... ADD COLUMN ...), then restart — the app will adopt it.\n"
        f"(database: {url})"
    )


def upgrade_database(engine: Engine) -> str:
    """Bring `engine`'s database to the latest schema. Returns what it did:
    "fresh", "adopted-legacy" or "upgraded" (also used by the smoke test)."""
    with engine.connect() as conn:
        is_pg = conn.dialect.name == "postgresql"
        if is_pg:
            conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _PG_ADVISORY_LOCK_KEY})
            conn.commit()
        try:
            tables = set(inspect(conn).get_table_names())
            cfg = alembic_config(conn)

            if "alembic_version" in tables:
                outcome = "upgraded"
            elif tables - {"alembic_version"}:
                problems = legacy_schema_problems(conn)
                if problems:
                    raise LegacyDatabaseError(_legacy_help(problems, engine.url.render_as_string(hide_password=True)))
                logger.info("Adopting pre-Alembic database: stamping baseline %s", BASELINE_REVISION)
                command.stamp(cfg, BASELINE_REVISION)
                conn.commit()
                outcome = "adopted-legacy"
            else:
                outcome = "fresh"

            command.upgrade(cfg, "head")
            conn.commit()
            return outcome
        finally:
            if is_pg:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _PG_ADVISORY_LOCK_KEY})
                conn.commit()
