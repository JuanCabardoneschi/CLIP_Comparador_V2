"""Add CategoryPairExclusion model for per-client exclusion rules

Revision ID: add_category_pair_exclusion
Revises: [previous_revision]
Create Date: 2025-11-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_category_pair_exclusion'
down_revision = None  # Update this with the actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'category_pair_exclusions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('primary_category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('secondary_category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('exclusion_rule', sa.String(50), nullable=False, server_default='torso_evidence'),
        sa.Column('params', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_index('idx_pair_exclusions_client', 'category_pair_exclusions', ['client_id'])
    op.create_index('idx_pair_exclusions_active', 'category_pair_exclusions', ['client_id', 'is_active'])
    op.create_unique_constraint(
        'uq_pair_exclusion',
        'category_pair_exclusions',
        ['client_id', 'primary_category_id', 'secondary_category_id']
    )


def downgrade():
    op.drop_table('category_pair_exclusions')
