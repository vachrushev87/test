"""Ensure phone_number exists in cafes table

Revision ID: eed2af8a8c63
Revises: 8277963288a5
Create Date: 2025-08-05 03:56:40.005563

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eed2af8a8c63'
down_revision: Union[str, None] = '8277963288a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cafes', sa.Column('phone_number', sa.String(), nullable=True))


def downgrade() -> None:
    pass
