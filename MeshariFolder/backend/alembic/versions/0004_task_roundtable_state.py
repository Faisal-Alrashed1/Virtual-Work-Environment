"""task roundtable state

When the agent roundtable started and finished for a task's latest review. It now runs
in the background after the Mentor's review is returned, and these timestamps (in the
database, so any worker can read them) are how the frontend knows to keep refreshing.
Both nullable: tasks reviewed before this, and tasks with no specialists, have neither.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-21 12:50:13.468102
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('roundtable_started_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('roundtable_finished_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_column('roundtable_finished_at')
        batch_op.drop_column('roundtable_started_at')
