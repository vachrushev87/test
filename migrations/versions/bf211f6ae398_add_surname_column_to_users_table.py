"""Add surname column to users table

Revision ID: bf211f6ae398
Revises: 7c9fa3630f7e
Create Date: 2025-08-04 10:59:45.737015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf211f6ae398'
down_revision: Union[str, None] = '7c9fa3630f7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
