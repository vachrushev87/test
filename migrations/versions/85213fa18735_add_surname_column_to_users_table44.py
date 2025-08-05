"""Add surname column to users table44

Revision ID: 85213fa18735
Revises: 223e5b2061b6
Create Date: 2025-08-04 11:41:27.210326

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85213fa18735'
down_revision: Union[str, None] = '223e5b2061b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
