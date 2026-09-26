"""onboarding resume state

Persists what the onboarding graph produced at each pause (the track
suggestion's reasoning and the suggested agent roster) so a graduate can
resume from the database alone. Both columns are nullable: existing rows
need no backfill, and a NULL simply means "nothing saved yet".

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-19 17:37:43.195403
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('suggested_track_reasoning', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('suggested_agent_ids_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('suggested_agent_ids_json')
        batch_op.drop_column('suggested_track_reasoning')
