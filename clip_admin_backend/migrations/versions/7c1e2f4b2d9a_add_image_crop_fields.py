"""add_image_crop_fields

Revision ID: 7c1e2f4b2d9a
Revises: 238d9dadb10d
Create Date: 2025-11-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7c1e2f4b2d9a'
down_revision = '238d9dadb10d'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columnas de cropping a images (todas opcionales)
    op.add_column('images', sa.Column('crop_x', sa.Integer(), nullable=True))
    op.add_column('images', sa.Column('crop_y', sa.Integer(), nullable=True))
    op.add_column('images', sa.Column('crop_w', sa.Integer(), nullable=True))
    op.add_column('images', sa.Column('crop_h', sa.Integer(), nullable=True))
    op.add_column('images', sa.Column('is_crop_manual', sa.Boolean(), nullable=True))
    op.add_column('images', sa.Column('refined', sa.Boolean(), nullable=True))

    # Opcional: índice para consultas futuras sobre refinados/manuales
    op.create_index('ix_images_is_crop_manual', 'images', ['is_crop_manual'])
    op.create_index('ix_images_refined', 'images', ['refined'])


def downgrade():
    op.drop_index('ix_images_refined', table_name='images')
    op.drop_index('ix_images_is_crop_manual', table_name='images')
    op.drop_column('images', 'refined')
    op.drop_column('images', 'is_crop_manual')
    op.drop_column('images', 'crop_h')
    op.drop_column('images', 'crop_w')
    op.drop_column('images', 'crop_y')
    op.drop_column('images', 'crop_x')
