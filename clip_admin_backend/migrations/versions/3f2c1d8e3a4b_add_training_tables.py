"""Add training module tables

Revision ID: 3f2c1d8e3a4b
Revises: None
Create Date: 2025-11-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3f2c1d8e3a4b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Tabla: training_events
    op.create_table(
        'training_events',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('client_id', sa.String(length=36), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('category_id', sa.String(length=36), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('query_image_ref', sa.String(length=500), nullable=True),
        sa.Column('topk_results', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('positives', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('negatives', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('variant_key', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Tabla: client_category_variants
    op.create_table(
        'client_category_variants',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('client_id', sa.String(length=36), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('category_id', sa.String(length=36), sa.ForeignKey('categories.id'), nullable=False),
        sa.Column('variant_key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('centroid_embedding', sa.Text(), nullable=True),
        sa.Column('support_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('prompts', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Índice opcional para búsquedas rápidas por cliente/categoría
    op.create_index('ix_client_category_variants_client_category', 'client_category_variants', ['client_id', 'category_id'])
    op.create_unique_constraint('uq_client_category_variant_key', 'client_category_variants', ['client_id', 'category_id', 'variant_key'])


def downgrade():
    op.drop_constraint('uq_client_category_variant_key', 'client_category_variants', type_='unique')
    op.drop_index('ix_client_category_variants_client_category', table_name='client_category_variants')
    op.drop_table('client_category_variants')
    op.drop_table('training_events')
