"""ten agents: new AgentType + ReviewKind values

Adds three new AgentType values (QA_ENGINEER, UX_REVIEWER,
TECHNICAL_WRITER — docs/TEN_AGENTS.md) and one new ReviewKind value
(CAREER_CHECKIN, for the Career Coach's new dedicated action,
app/agents/career_coach.py).

Unlike every other migration so far, this one genuinely has to ALTER an
EXISTING Postgres enum type rather than create a fresh one or reuse an
existing one unchanged — agenttype and reviewkind are both used across
several already-populated tables (chat_messages, task_messages, reviews,
team_messages, knowledge_chunks, ...), so there's no "just add a new
column with its own type" option the way 0007's account_type had.

ALTER TYPE ... ADD VALUE is genuinely safer than it sounds here, and
narrower than the ProjectSource case this project deliberately avoided
(see 0007/0008's docstrings): PostgreSQL 12+ (this project targets 16)
allows it inside a transaction, and the ONLY restriction is that the
new value can't be *used* in the same transaction that added it. This
migration only adds enum labels — nothing in it inserts or updates a
row using any of them — so that restriction never bites. SQLite needs
no equivalent action at all (confirmed earlier this project: no CHECK
constraint is generated for an Enum column here, so a new Python-side
enum member just works immediately).

**Not verified against real PostgreSQL as of this migration** — per
Meshari's steer this round, local (SQLite) verification is the bar for
now; re-run smoke_test_migrations.py's Postgres section before trusting
this against a real Postgres instance. See docs/TEN_AGENTS.md.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-26 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_AGENT_TYPES = ('QA_ENGINEER', 'UX_REVIEWER', 'TECHNICAL_WRITER')
_NEW_REVIEW_KINDS = ('CAREER_CHECKIN',)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in _NEW_AGENT_TYPES:
            op.execute(f"ALTER TYPE agenttype ADD VALUE IF NOT EXISTS '{value}'")
        for value in _NEW_REVIEW_KINDS:
            op.execute(f"ALTER TYPE reviewkind ADD VALUE IF NOT EXISTS '{value}'")
        return

    # SQLite: no CHECK constraint exists on these columns (confirmed in
    # earlier migrations), so a new Python-side enum member is usable
    # immediately — EXCEPT sa.Enum sizes its SQLite VARCHAR to the
    # longest member *name* at the column's original creation time.
    # reviews.kind was VARCHAR(13) (sized for 'SKILLS_ROLLUP');
    # 'CAREER_CHECKIN' is 14 characters — a real drift the model-diff
    # guard correctly caught (confirmed by actually running it), even
    # though SQLite never enforces the length at the data level. None of
    # the three new agent names exceed the existing 18-character max
    # ('SECURITY_REVIEWER'), so agenttype-typed columns need no change.
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.alter_column(
            'kind',
            existing_type=sa.String(length=13),
            type_=sa.Enum(
                'TASK_REVIEW', 'WEEK_PROGRESS', 'BEHAVIORAL', 'SKILLS_ROLLUP',
                'CAREER_CHECKIN', name='reviewkind',
            ),
            existing_nullable=False,
        )


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE for an enum type — removing a label
    # that may already be in use would require rewriting every row and
    # recreating the type. Consistent with this project's other enum
    # migrations, downgrade never attempts that: rolling back doesn't
    # un-use rows already written with the new agent/review types (the
    # model-drift guard only checks schema shape, not which labels have
    # been used, so this doesn't fail it). SQLite's column-width change
    # is safe to reverse, though, since it's purely metadata:
    if op.get_bind().dialect.name != "postgresql":
        with op.batch_alter_table('reviews', schema=None) as batch_op:
            batch_op.alter_column(
                'kind',
                existing_type=sa.Enum(
                    'TASK_REVIEW', 'WEEK_PROGRESS', 'BEHAVIORAL', 'SKILLS_ROLLUP',
                    'CAREER_CHECKIN', name='reviewkind',
                ),
                type_=sa.String(length=13),
                existing_nullable=False,
            )
