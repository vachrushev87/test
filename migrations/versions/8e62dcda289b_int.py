"""int

Revision ID: 8e62dcda289b
Revises: a4f5bbb28b0c
Create Date: 2025-08-05 01:15:18.531923

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e62dcda289b'
down_revision: Union[str, None] = 'a4f5bbb28b0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
