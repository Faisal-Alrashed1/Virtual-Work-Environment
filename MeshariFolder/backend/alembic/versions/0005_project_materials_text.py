"""project materials text

Project.materials_text: real material about a graduate's OWN project (pasted notes
and/or text extracted from uploaded files), so the Manager can plan real subtasks
instead of working from a one-line description. Nullable — every existing project,
and every Manager-authored one, has none. See docs/STAGE2_OWN_PROJECT.md.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-22 05:36:29.540025
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('materials_text', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('materials_text')
