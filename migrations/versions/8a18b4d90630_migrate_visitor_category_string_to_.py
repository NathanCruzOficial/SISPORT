"""migrate visitor category string to category id

Revision ID: 8a18b4d90630
Revises: d3cb0ac9d94d
Create Date: 2026-06-24 11:51:32.484869

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "8a18b4d90630"
down_revision = "d3cb0ac9d94d"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # 0. Limpeza preventiva caso uma tentativa anterior tenha falhado
    # ------------------------------------------------------------------

    bind.execute(text("DROP TABLE IF EXISTS _alembic_tmp_visitors"))

    # ------------------------------------------------------------------
    # 1. Garante categorias padrão obrigatórias
    # ------------------------------------------------------------------

    default_categories = [
        {
            "value": "civil",
            "label": "Civil",
            "icon": "bi-person",
            "btn_class": "btn-outline-secondary",
            "badge_class": "bg-secondary",
            "sort_order": 10,
            "is_active": 1,
        },
        {
            "value": "militar",
            "label": "Militar",
            "icon": "bi-shield-fill",
            "btn_class": "btn-outline-success",
            "badge_class": "text-bg-success",
            "sort_order": 20,
            "is_active": 1,
        },
        {
            "value": "ex-militar",
            "label": "Ex-Militar",
            "icon": "bi-shield-check",
            "btn_class": "btn-outline-warning",
            "badge_class": "text-bg-warning text-dark",
            "sort_order": 30,
            "is_active": 1,
        },
    ]

    for category in default_categories:
        existing_category = bind.execute(
            text("""
                SELECT id
                FROM visitor_categories
                WHERE value = :value
                LIMIT 1
            """),
            {"value": category["value"]},
        ).fetchone()

        if existing_category:
            bind.execute(
                text("""
                    UPDATE visitor_categories
                    SET label = :label,
                        icon = :icon,
                        btn_class = :btn_class,
                        badge_class = :badge_class,
                        sort_order = :sort_order,
                        is_active = :is_active
                    WHERE value = :value
                """),
                category,
            )
        else:
            bind.execute(
                text("""
                    INSERT INTO visitor_categories
                    (
                        value,
                        label,
                        icon,
                        btn_class,
                        badge_class,
                        sort_order,
                        is_active
                    )
                    VALUES
                    (
                        :value,
                        :label,
                        :icon,
                        :btn_class,
                        :badge_class,
                        :sort_order,
                        :is_active
                    )
                """),
                category,
            )

    # ------------------------------------------------------------------
    # 2. Adiciona a nova coluna category_id sem recriar a tabela
    # ------------------------------------------------------------------
    # Importante:
    # Não usamos batch_alter_table aqui porque a tabela antiga tem:
    # category TEXT(30) DEFAULT (civil) NOT NULL
    # e o SQLite rejeita esse default ao recriar a tabela.

    existing_visitor_columns = {
        row[1]
        for row in bind.execute(text("PRAGMA table_info(visitors)")).fetchall()
    }

    if "category_id" not in existing_visitor_columns:
        op.add_column(
            "visitors",
            sa.Column("category_id", sa.Integer(), nullable=True),
        )

    # ------------------------------------------------------------------
    # 3. Busca o ID da categoria Civil
    # ------------------------------------------------------------------

    civil_id = bind.execute(
        text("""
            SELECT id
            FROM visitor_categories
            WHERE value = 'civil'
            LIMIT 1
        """)
    ).scalar()

    if not civil_id:
        raise RuntimeError("Categoria padrão 'civil' não encontrada.")

    # ------------------------------------------------------------------
    # 4. Migra visitors.category string para visitors.category_id
    # ------------------------------------------------------------------
    # Regra:
    # - Compara visitors.category com visitor_categories.value
    # - Se encontrar, usa o ID correspondente
    # - Se não encontrar, vira Civil

    bind.execute(
        text("""
            UPDATE visitors
            SET category_id = (
                SELECT vc.id
                FROM visitor_categories vc
                WHERE lower(trim(vc.value)) = lower(trim(coalesce(visitors.category, '')))
                LIMIT 1
            )
        """)
    )

    bind.execute(
        text("""
            UPDATE visitors
            SET category_id = :civil_id
            WHERE category_id IS NULL
        """),
        {"civil_id": civil_id},
    )

    # ------------------------------------------------------------------
    # 5. Remove category antiga, força category_id NOT NULL e cria FK
    # ------------------------------------------------------------------
    # Agora sim usamos batch_alter_table.
    # Como a coluna antiga category será removida neste mesmo batch,
    # o default inválido dela não entra na nova tabela temporária.

    with op.batch_alter_table("visitors", schema=None) as batch_op:
        batch_op.alter_column(
            "name",
            existing_type=sa.TEXT(length=220),
            type_=sa.String(length=220),
            existing_nullable=False,
        )

        batch_op.alter_column(
            "father_name",
            existing_type=sa.TEXT(length=220),
            type_=sa.String(length=220),
            existing_nullable=True,
        )

        batch_op.alter_column(
            "mom_name",
            existing_type=sa.TEXT(length=220),
            type_=sa.String(length=220),
            existing_nullable=False,
        )

        batch_op.alter_column(
            "cpf",
            existing_type=sa.TEXT(length=16),
            type_=sa.String(length=16),
            existing_nullable=False,
        )

        batch_op.alter_column(
            "phone",
            existing_type=sa.TEXT(length=20),
            type_=sa.String(length=20),
            existing_nullable=False,
        )

        batch_op.alter_column(
            "email",
            existing_type=sa.TEXT(length=254),
            type_=sa.String(length=254),
            existing_nullable=True,
        )

        batch_op.alter_column(
            "empresa",
            existing_type=sa.TEXT(length=120),
            type_=sa.String(length=120),
            existing_nullable=True,
        )

        batch_op.alter_column(
            "category_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

        batch_op.create_foreign_key(
            "fk_visitors_category_id_visitor_categories",
            "visitor_categories",
            ["category_id"],
            ["id"],
        )

        batch_op.drop_column("category")

    # ------------------------------------------------------------------
    # 6. Cria índice após a recriação da tabela
    # ------------------------------------------------------------------

    existing_indexes = {
        row[1]
        for row in bind.execute(text("PRAGMA index_list(visitors)")).fetchall()
    }

    if "ix_visitors_category_id" not in existing_indexes:
        op.create_index(
            "ix_visitors_category_id",
            "visitors",
            ["category_id"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # 0. Limpeza preventiva
    # ------------------------------------------------------------------

    bind.execute(text("DROP TABLE IF EXISTS _alembic_tmp_visitors"))

    # ------------------------------------------------------------------
    # 1. Recria a coluna antiga category
    # ------------------------------------------------------------------

    existing_visitor_columns = {
        row[1]
        for row in bind.execute(text("PRAGMA table_info(visitors)")).fetchall()
    }

    if "category" not in existing_visitor_columns:
        op.add_column(
            "visitors",
            sa.Column(
                "category",
                sa.String(length=60),
                nullable=True,
            ),
        )

    # ------------------------------------------------------------------
    # 2. Preenche category usando visitor_categories.value
    # ------------------------------------------------------------------

    bind.execute(
        text("""
            UPDATE visitors
            SET category = (
                SELECT vc.value
                FROM visitor_categories vc
                WHERE vc.id = visitors.category_id
                LIMIT 1
            )
        """)
    )

    bind.execute(
        text("""
            UPDATE visitors
            SET category = 'civil'
            WHERE category IS NULL OR trim(category) = ''
        """)
    )

    # ------------------------------------------------------------------
    # 3. Remove índice, FK e category_id
    # ------------------------------------------------------------------

    existing_indexes = {
        row[1]
        for row in bind.execute(text("PRAGMA index_list(visitors)")).fetchall()
    }

    if "ix_visitors_category_id" in existing_indexes:
        op.drop_index("ix_visitors_category_id", table_name="visitors")

    with op.batch_alter_table("visitors", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_visitors_category_id_visitor_categories",
            type_="foreignkey",
        )

        batch_op.alter_column(
            "empresa",
            existing_type=sa.String(length=120),
            type_=sa.TEXT(length=120),
            existing_nullable=True,
        )

        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=254),
            type_=sa.TEXT(length=254),
            existing_nullable=True,
        )

        batch_op.alter_column(
            "phone",
            existing_type=sa.String(length=20),
            type_=sa.TEXT(length=20),
            existing_nullable=False,
        )

        batch_op.alter_column(
            "cpf",
            existing_type=sa.String(length=16),
            type_=sa.TEXT(length=16),
            existing_nullable=False,
        )

        batch_op.alter_column(
            "mom_name",
            existing_type=sa.String(length=220),
            type_=sa.TEXT(length=220),
            existing_nullable=False,
        )

        batch_op.alter_column(
            "father_name",
            existing_type=sa.String(length=220),
            type_=sa.TEXT(length=220),
            existing_nullable=True,
        )

        batch_op.alter_column(
            "name",
            existing_type=sa.String(length=220),
            type_=sa.TEXT(length=220),
            existing_nullable=False,
        )

        batch_op.alter_column(
            "category",
            existing_type=sa.String(length=60),
            type_=sa.TEXT(length=30),
            nullable=False,
            server_default=sa.text("'civil'"),
        )

        batch_op.drop_column("category_id")
