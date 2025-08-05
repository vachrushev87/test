"""st

Revision ID: 6c52a240014d
Revises: 8e62dcda289b
Create Date: 2025-08-05 01:21:50.705758

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c52a240014d'
down_revision: Union[str, None] = '8e62dcda289b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
