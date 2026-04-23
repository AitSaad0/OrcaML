"""add_is_manual_to_runs

Revision ID: a79d812542e3
Revises: 241c8f211c40
Create Date: 2026-04-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a79d812542e3"
down_revision: Union[str, Sequence[str], None] = "241c8f211c40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("runs")]

    if "is_manual" not in columns:
        op.add_column("runs", sa.Column("is_manual", sa.Boolean(), nullable=True))
        op.execute("UPDATE runs SET is_manual = TRUE WHERE is_manual IS NULL")
        op.alter_column("runs", "is_manual", nullable=False)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("runs")]

    if "is_manual" in columns:
        op.drop_column("runs", "is_manual")