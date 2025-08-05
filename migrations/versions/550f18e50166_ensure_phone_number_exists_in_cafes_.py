"""Ensure phone_number exists in cafes table

Revision ID: 550f18e50166
Revises: 2d5dbfa7da48
Create Date: 2025-08-05 03:59:47.225323

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '550f18e50166'
down_revision: Union[str, None] = '2d5dbfa7da48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
