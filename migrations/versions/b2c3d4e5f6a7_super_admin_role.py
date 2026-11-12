"""super_admin role + users.center_id nullable

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'SUPER_ADMIN'")
    op.alter_column('users', 'center_id',
               existing_type=sa.Integer(),
               nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'center_id',
               existing_type=sa.Integer(),
               nullable=False)
    # PostgreSQL enum dan qiymatni olib bo'lmaydi - downgrade'da
    # super_admin rolli user'lar bo'lmasligi kerak
