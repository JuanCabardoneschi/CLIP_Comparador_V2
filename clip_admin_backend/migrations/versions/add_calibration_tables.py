"""Agregar tablas para módulo de Calibración Multi-Label

Revision ID: add_calibration_tables
Revises:
Create Date: 2025-11-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_calibration_tables'
down_revision = None  # Actualizar según última migración
branch_labels = None
depends_on = None


def upgrade():
    # Tabla training_images
    op.create_table(
        'training_images',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('client_id', sa.String(36), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('cloudinary_public_id', sa.String(255)),
        sa.Column('cloudinary_url', sa.Text()),
        sa.Column('expected_categories', postgresql.JSON(), nullable=False, server_default='[]'),
        sa.Column('notes', sa.Text()),
        sa.Column('case_type', sa.String(50), server_default='general'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('last_calibration_result', postgresql.JSON()),
        sa.Column('last_calibration_date', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by_user_id', sa.String(36), sa.ForeignKey('users.id'))
    )

    # Índices
    op.create_index('ix_training_images_client_id', 'training_images', ['client_id'])
    op.create_index('ix_training_images_is_active', 'training_images', ['is_active'])

    # Tabla calibration_runs
    op.create_table(
        'calibration_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('client_id', sa.String(36), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('results', postgresql.JSON(), nullable=False),
        sa.Column('applied', sa.Boolean(), server_default='false'),
        sa.Column('applied_at', sa.DateTime()),
        sa.Column('applied_by_user_id', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by_user_id', sa.String(36), sa.ForeignKey('users.id'))
    )

    # Índices
    op.create_index('ix_calibration_runs_client_id', 'calibration_runs', ['client_id'])


def downgrade():
    op.drop_index('ix_calibration_runs_client_id')
    op.drop_table('calibration_runs')

    op.drop_index('ix_training_images_is_active')
    op.drop_index('ix_training_images_client_id')
    op.drop_table('training_images')
