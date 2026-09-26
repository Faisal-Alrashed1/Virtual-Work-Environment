"""
Smoke test for the Alembic setup (alembic/, app/migrations.py) — no server,
no LLM, just throwaway SQLite files.

What it proves:
  * a fresh database is built from the migrations and lands on the latest
    revision;
  * running it again is a harmless no-op;
  * a pre-Alembic database (built by the old create_all) is ADOPTED without
    losing any data;
  * an out-of-date pre-Alembic database (the historical onboarding-stage
    bug) is refused at startup with a clear message naming the missing column;
  * the migrations and the SQLAlchemy models agree — this is the drift
    guard: edit a model without writing a migration and this test fails;
  * every migration can be rolled all the way back.

Run: python smoke_test_migrations.py

Optional — also prove it on PostgreSQL (the production database). Point
MIGRATIONS_TEST_POSTGRES_URL at a DISPOSABLE database (this section drops
and recreates its `public` schema), e.g. after `docker compose up -d`:

  MIGRATIONS_TEST_POSTGRES_URL=postgresql://venv:venv@localhost:5432/venv_test \
      python smoke_test_migrations.py
"""
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///:memory:"  # nothing here touches a real db

from alembic import command  # noqa: E402
from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import create_engine, inspect, text  # noqa: E402

import app.models  # noqa: E402,F401
from app.database import Base  # noqa: E402
from app.migrations import (  # noqa: E402
    BASELINE_REVISION,
    LegacyDatabaseError,
    alembic_config,
    baseline_schema,
    upgrade_database,
)

TMP = tempfile.mkdtemp(prefix="venv_migrations_")


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def new_engine(name):
    return create_engine(f"sqlite:///{TMP}/{name}.db")


def head_revision(engine):
    with engine.connect() as conn:
        cfg = alembic_config(conn)
        return ScriptDirectory.from_config(cfg).get_current_head()


def current_revision(engine):
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def app_tables(engine):
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


MODEL_TABLES = set(Base.metadata.tables)


def make_legacy(engine):
    """A database exactly as the OLD code left it: the baseline schema (what
    create_all built before Alembic existed) and no alembic_version table.
    Built from the frozen baseline migration — not from today's models —
    so it stays a faithful "old" database no matter how the models evolve."""
    with engine.connect() as conn:
        command.upgrade(alembic_config(conn), BASELINE_REVISION)
        conn.commit()
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE alembic_version")

# ---- 1. fresh database -------------------------------------------------------
fresh = new_engine("fresh")
check("fresh database: upgrade reports 'fresh'", upgrade_database(fresh) == "fresh")
check("fresh database: every model table exists", app_tables(fresh) == MODEL_TABLES)
check("fresh database: lands on the latest revision", current_revision(fresh) == head_revision(fresh))

# ---- 2. idempotent -----------------------------------------------------------
check("second run is a no-op 'upgraded'", upgrade_database(fresh) == "upgraded")
check("second run keeps the revision", current_revision(fresh) == head_revision(fresh))

# ---- 3. drift guard: models vs migrations ------------------------------------
with fresh.connect() as conn:
    diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
check(
    "models and migrations agree (no drift) — if this fails, run: "
    "alembic revision --autogenerate -m '<what changed>'  " + (f"[diff: {diff}]" if diff else ""),
    diff == [],
)

# ---- 4. legacy (create_all) database is adopted, data intact ------------------
legacy = new_engine("legacy")
make_legacy(legacy)
with legacy.begin() as conn:
    conn.execute(text("INSERT INTO organizations (id, name, created_at) VALUES ('org-1', 'Acme', '2026-09-01 00:00:00')"))
check("legacy database has no alembic_version yet", "alembic_version" not in inspect(legacy).get_table_names())
check("legacy database is adopted", upgrade_database(legacy) == "adopted-legacy")
check("adopted database lands on the latest revision", current_revision(legacy) == head_revision(legacy))
check("adoption ran the post-baseline migrations too (users.suggested_track_reasoning)",
      "suggested_track_reasoning" in {c["name"] for c in inspect(legacy).get_columns("users")})
with legacy.connect() as conn:
    kept = conn.execute(text("SELECT name FROM organizations WHERE id = 'org-1'")).scalar()
check("adoption kept existing rows", kept == "Acme")
check("adopting again is a no-op", upgrade_database(legacy) == "upgraded")

# ---- 5. out-of-date legacy database is refused with a clear message -----------
stale = new_engine("stale")
make_legacy(stale)
with stale.begin() as conn:
    conn.exec_driver_sql("ALTER TABLE users DROP COLUMN onboarding_stage")
try:
    upgrade_database(stale)
    refused, message = False, ""
except LegacyDatabaseError as exc:
    refused, message = True, str(exc)
check("stale legacy database (missing users.onboarding_stage) is refused", refused)
check("the error names the missing column", "users.onboarding_stage" in message)
check("the error tells the developer how to fix it", "delete the file" in message)

missing_table = new_engine("missing_table")
make_legacy(missing_table)
with missing_table.begin() as conn:
    conn.exec_driver_sql("DROP TABLE user_agents")
try:
    upgrade_database(missing_table)
    refused = False
    message = ""
except LegacyDatabaseError as exc:
    refused, message = True, str(exc)
check("legacy database missing a whole table is refused too", refused and "user_agents" in message)

# ---- 6. the frozen baseline is what we think it is ----------------------------
baseline = baseline_schema()
check("baseline schema has the 12 original tables", len(baseline) == 12 and "users" in baseline)
check("baseline predates later migrations (frozen at 0001)", BASELINE_REVISION == "0001")

# ---- 7. every migration rolls back cleanly ------------------------------------
down = new_engine("down")
upgrade_database(down)
with down.connect() as conn:
    command.downgrade(alembic_config(conn), "base")
    conn.commit()
check("downgrade to base leaves no application tables", app_tables(down) == set())

# ---- 8. (optional) the same, on PostgreSQL ------------------------------------
PG_URL = os.environ.get("MIGRATIONS_TEST_POSTGRES_URL")
if not PG_URL:
    print("[SKIP] PostgreSQL section (set MIGRATIONS_TEST_POSTGRES_URL to a disposable database to run it)")
else:
    def pg_reset():
        eng = create_engine(PG_URL, isolation_level="AUTOCOMMIT")
        with eng.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        eng.dispose()

    def pg_enum_types(engine):
        with engine.connect() as conn:
            return {r[0] for r in conn.execute(text("SELECT typname FROM pg_type WHERE typtype = 'e'"))}

    pg_reset()
    pg = create_engine(PG_URL)
    check("[pg] fresh database builds from the migrations", upgrade_database(pg) == "fresh")
    check("[pg] every model table exists", app_tables(pg) == MODEL_TABLES)
    with pg.connect() as conn:
        pg_diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    check("[pg] models and migrations agree (no drift)", pg_diff == [])
    check("[pg] enum types were created", {"agenttype", "trackenum"} <= pg_enum_types(pg))

    with pg.connect() as conn:
        command.downgrade(alembic_config(conn), "base")
        conn.commit()
    check("[pg] downgrade drops the tables", app_tables(pg) == set())
    check("[pg] downgrade also drops the enum types (else a re-upgrade fails)", pg_enum_types(pg) == set())
    upgrade_database(pg)
    check("[pg] upgrade after downgrade works", app_tables(pg) == MODEL_TABLES)

    pg_reset()
    pg_legacy = create_engine(PG_URL)
    make_legacy(pg_legacy)
    with pg_legacy.begin() as conn:
        conn.execute(text("INSERT INTO organizations (id, name, created_at) VALUES ('org-1', 'Acme', now())"))
    check("[pg] legacy database is adopted", upgrade_database(pg_legacy) == "adopted-legacy")
    with pg_legacy.connect() as conn:
        check("[pg] adoption kept existing rows", conn.execute(text("SELECT name FROM organizations")).scalar() == "Acme")

    pg_reset()
    pg_stale = create_engine(PG_URL)
    make_legacy(pg_stale)
    with pg_stale.begin() as conn:
        conn.execute(text("ALTER TABLE users DROP COLUMN onboarding_stage"))
    try:
        upgrade_database(pg_stale)
        pg_refused = False
    except LegacyDatabaseError as exc:
        pg_refused = "users.onboarding_stage" in str(exc)
    check("[pg] stale legacy database is refused with a clear message", pg_refused)
    pg_reset()

print("\nAll migration checks passed.")
