"""add subdomain to deployments

Revision ID: 1c261bccd767
Revises: c3b473a5af52
Create Date: 2026-06-10 17:51:56.886109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1c261bccd767'
down_revision: Union[str, Sequence[str], None] = 'c3b473a5af52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('deployments', sa.Column('subdomain', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('deployments', 'subdomain')