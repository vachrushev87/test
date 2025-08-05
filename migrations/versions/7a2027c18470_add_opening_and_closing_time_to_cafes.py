"""Add opening and closing time to cafes

Revision ID: 7a2027c18470
Revises: 6c52a240014d
Create Date: 2025-08-05 03:36:13.119468

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a2027c18470'
down_revision: Union[str, None] = '6c52a240014d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
