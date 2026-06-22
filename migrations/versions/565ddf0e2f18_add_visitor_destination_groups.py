"""add visitor destination groups

Revision ID: 565ddf0e2f18
Revises: 5306a747dac8
Create Date: 2026-06-19 09:27:32.736550

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '565ddf0e2f18'
down_revision = '5306a747dac8'
branch_labels = None
depends_on = None


def upgrade():
    # Limpa restos de tentativas anteriores, caso existam
    op.execute("DROP TABLE IF EXISTS visitor_destination_places")
    op.execute("DROP TABLE IF EXISTS visitor_destination_groups")
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_visitors")
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_visits")

    op.create_table(
        'visitor_destination_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('is_root', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ['parent_id'],
            ['visitor_destination_groups.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'visitor_destination_places',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['group_id'],
            ['visitor_destination_groups.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )

    op.execute("DROP TABLE IF EXISTS app_settings")

    conn = op.get_bind()

    visitor_cols = [
        row[1]
        for row in conn.exec_driver_sql("PRAGMA table_info(visitors)").fetchall()
    ]

    if "photo_rel_path" in visitor_cols:
        op.execute("ALTER TABLE visitors DROP COLUMN photo_rel_path")

    with op.batch_alter_table('visits', schema=None) as batch_op:
        batch_op.alter_column(
            'destination',
            existing_type=sa.VARCHAR(length=180),
            type_=sa.String(length=255),
            existing_nullable=False
        )
        batch_op.alter_column(
            'reason',
            existing_type=sa.VARCHAR(length=255),
            type_=sa.Text(),
            existing_nullable=True
        )


def downgrade():
    conn = op.get_bind()

    visitor_cols = [
        row[1]
        for row in conn.exec_driver_sql("PRAGMA table_info(visitors)").fetchall()
    ]

    if "photo_rel_path" not in visitor_cols:
        op.add_column(
            'visitors',
            sa.Column('photo_rel_path', sa.TEXT(length=500), nullable=True)
        )

    op.create_table(
        'app_settings',
        sa.Column('key', sa.VARCHAR(length=64), nullable=False),
        sa.Column('value', sa.TEXT(), nullable=False),
        sa.PrimaryKeyConstraint('key')
    )

    op.drop_table('visitor_destination_places')
    op.drop_table('visitor_destination_groups')
