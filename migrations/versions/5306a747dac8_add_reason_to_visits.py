"""add reason to visits

Revision ID: 5306a747dac8
Revises: 71cb9dafd972
Create Date: 2026-06-19 09:20:11.924966

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5306a747dac8'
down_revision = '71cb9dafd972'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("visits", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reason", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("visits", schema=None) as batch_op:
        batch_op.drop_column("reason")
