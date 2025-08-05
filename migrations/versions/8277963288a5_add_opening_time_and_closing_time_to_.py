"""Add opening_time and closing_time to cafes table

Revision ID: 8277963288a5
Revises: 34768cefc670
Create Date: 2025-08-05 03:44:37.812752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8277963288a5'
down_revision: Union[str, None] = '34768cefc670'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cafes', sa.Column('opening_time', sa.Time(), nullable=True))
    op.add_column('cafes', sa.Column('closing_time', sa.Time(), nullable=True))


def downgrade() -> None:
    pass
