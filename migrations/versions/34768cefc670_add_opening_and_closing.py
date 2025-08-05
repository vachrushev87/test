"""Add opening and closing

Revision ID: 34768cefc670
Revises: 7a2027c18470
Create Date: 2025-08-05 03:39:15.272295

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34768cefc670'
down_revision: Union[str, None] = '7a2027c18470'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
