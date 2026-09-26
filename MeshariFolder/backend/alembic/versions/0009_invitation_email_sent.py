"""invitation email_sent flag

Adds invitations.email_sent (Boolean, default False, NOT NULL) — whether
app/email.py actually sent a real invitation email (docs/
STAGE3_COMPANY_RAG.md). A plain boolean with a server_default, no enum
involved, so none of migration 0007's Postgres-enum lessons apply here —
straightforward on both dialects.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-25 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('invitations', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('email_sent', sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table('invitations', schema=None) as batch_op:
        batch_op.drop_column('email_sent')
