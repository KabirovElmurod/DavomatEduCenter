"""parent_links.user_id nullable

Revision ID: a1b2c3d4e5f6
Revises: 0e00b776ce49
Create Date: 2026-11-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "0e00b776ce49"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("parent_links", "user_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("parent_links", "user_id", existing_type=sa.Integer(), nullable=False)
