"""team messages (Team Room)

Adds team_messages: one shared-room thread per user, for the Team Room
(the Meeting Room's group mode, docs/TEAM_ROOM.md) — the whole team and
the graduate in one running conversation, unlike chat_messages' one-
thread-per-agent shape. agent_type/sender_type reuse the same enum types
chat_messages already created (agenttype/sendertype), so create_type is
False here — CREATE TYPE already ran for chat_messages in the baseline.

Uses postgresql.ENUM specifically, not the generic sa.Enum, for the
reused-type columns: confirmed against a real Postgres 16 instance that
generic sa.Enum(create_type=False) does NOT reliably suppress CREATE
TYPE inside op.create_table (SQLAlchemy's dialect-adaptation path for
the generic type drops the create_type=False setting before the DDL
event that actually emits CREATE TYPE fires) — it errored with
'type "sendertype" already exists'. postgresql.ENUM(create_type=False)
honors it correctly, and — verified — degrades to an ordinary VARCHAR-
backed column on SQLite, so this is safe to use unconditionally rather
than branching per dialect.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-22 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'team_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column(
            'sender_type',
            postgresql.ENUM('USER', 'AGENT', name='sendertype', create_type=False),
            nullable=False,
        ),
        sa.Column(
            'agent_type',
            postgresql.ENUM(
                'MANAGER', 'MENTOR', 'HR', 'SECURITY_REVIEWER', 'DATA_REVIEWER',
                'CAREER_COACH', 'DEVOPS', name='agenttype', create_type=False,
            ),
            nullable=True,
        ),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('team_messages')
