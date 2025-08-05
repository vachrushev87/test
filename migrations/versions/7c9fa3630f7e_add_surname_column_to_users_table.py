"""Add surname column to users table

Revision ID: 7c9fa3630f7e
Revises: c2fa184481a3
Create Date: 2025-08-04 10:55:51.143253

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c9fa3630f7e'
down_revision: Union[str, None] = 'c2fa184481a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
