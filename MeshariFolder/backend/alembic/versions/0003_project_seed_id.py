"""project seed id

Which task-bank seed (agents/task_bank.py) a Manager-created project was based on.
Nullable: a graduate's own project, and every project created before the bank
existed, have none — and are planned exactly as before.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-21 11:41:40.200171
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('seed_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('seed_id')
