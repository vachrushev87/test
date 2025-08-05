"""Add surname column to users table55

Revision ID: 0a00258fd4d4
Revises: 85213fa18735
Create Date: 2025-08-04 12:01:31.544590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a00258fd4d4'
down_revision: Union[str, None] = '85213fa18735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
