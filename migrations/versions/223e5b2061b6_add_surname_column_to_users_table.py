"""Add surname column to users table

Revision ID: 223e5b2061b6
Revises: bf211f6ae398
Create Date: 2025-08-04 11:03:12.397752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '223e5b2061b6'
down_revision: Union[str, None] = 'bf211f6ae398'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
