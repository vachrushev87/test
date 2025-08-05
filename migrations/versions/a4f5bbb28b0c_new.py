"""new

Revision ID: a4f5bbb28b0c
Revises: 6215d873aab5
Create Date: 2025-08-05 01:03:53.525737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4f5bbb28b0c'
down_revision: Union[str, None] = '6215d873aab5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
