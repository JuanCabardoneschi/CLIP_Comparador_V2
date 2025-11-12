"""add_hierarchical_categories

Revision ID: 238d9dadb10d
Revises: 3f2c1d8e3a4b
Create Date: 2025-11-10 15:41:14.710696

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '238d9dadb10d'
down_revision = '3f2c1d8e3a4b'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar campos para jerarquía de categorías
    op.add_column('categories', sa.Column('parent_id', sa.String(length=36), nullable=True))
    op.add_column('categories', sa.Column('level', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('categories', sa.Column('is_leaf', sa.Boolean(), nullable=False, server_default='true'))

    # Crear foreign key constraint para parent_id
    op.create_foreign_key(
        'fk_categories_parent_id',
        'categories',
        'categories',
        ['parent_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Crear índices para mejorar performance de búsquedas jerárquicas
    op.create_index('ix_categories_parent_id', 'categories', ['parent_id'])
    op.create_index('ix_categories_level', 'categories', ['level'])
    op.create_index('ix_categories_is_leaf', 'categories', ['is_leaf'])

    # Crear índice compuesto para búsquedas comunes
    op.create_index('ix_categories_client_parent_leaf', 'categories', ['client_id', 'parent_id', 'is_leaf'])


def downgrade():
    # Eliminar índices
    op.drop_index('ix_categories_client_parent_leaf', table_name='categories')
    op.drop_index('ix_categories_is_leaf', table_name='categories')
    op.drop_index('ix_categories_level', table_name='categories')
    op.drop_index('ix_categories_parent_id', table_name='categories')

    # Eliminar foreign key
    op.drop_constraint('fk_categories_parent_id', 'categories', type_='foreignkey')

    # Eliminar columnas
    op.drop_column('categories', 'is_leaf')
    op.drop_column('categories', 'level')
    op.drop_column('categories', 'parent_id')
