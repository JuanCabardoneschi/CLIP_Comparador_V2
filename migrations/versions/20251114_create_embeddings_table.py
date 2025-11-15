"""
Revision ID: 20251114_create_embeddings_table
Revises:
Create Date: 2025-11-14
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'embeddings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('key', sa.String(128), unique=True, nullable=False),
        sa.Column('embedding', sa.Text, nullable=False),
        sa.Column('type', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table('embeddings')
