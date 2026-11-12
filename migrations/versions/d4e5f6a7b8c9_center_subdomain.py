"""centers.subdomain — markaz subdomain'i ({sub}.testvix.uz)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('centers', sa.Column('subdomain', sa.String(100), nullable=True))
    op.create_index('ix_centers_subdomain', 'centers', ['subdomain'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_centers_subdomain', table_name='centers')
    op.drop_column('centers', 'subdomain')
