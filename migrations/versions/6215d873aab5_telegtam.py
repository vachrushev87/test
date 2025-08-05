"""telegtam

Revision ID: 6215d873aab5
Revises: 0a00258fd4d4
Create Date: 2025-08-04 23:19:46.242091

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6215d873aab5'
down_revision: Union[str, None] = '0a00258fd4d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
