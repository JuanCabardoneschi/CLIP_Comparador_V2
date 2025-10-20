"""
Script para migrar los datos legacy de productos al campo attributes (JSONB)
"""
import os
import sys
from clip_admin_backend.app import db
from clip_admin_backend.app.models.product import Product
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json

# Cargar configuración de entorno
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
env_local_path = os.path.join(script_dir, '.env.local')
load_dotenv(env_local_path)

db_url = os.getenv('DATABASE_URL')
if not db_url:
    raise RuntimeError(f"DATABASE_URL no encontrado en {env_local_path}")
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

# Campos legacy que se migran (excepto sku, description, category_id)
LEGACY_FIELDS = [
    'price', 'stock', 'brand', 'color', 'tags', 'is_active', 'created_at', 'updated_at'
]

for product in session.query(Product).all():
    attributes = {}
    for field in LEGACY_FIELDS:
        value = getattr(product, field, None)
        if value is not None:
            # Convert datetime to isoformat
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            # Convert Decimal to float
            elif type(value).__name__ == 'Decimal':
                value = float(value)
            attributes[field] = value
    product.attributes = attributes
    print(f"Migrando producto {product.sku}: {json.dumps(attributes, ensure_ascii=False)}")

session.commit()
print("Migración de atributos a JSONB completada.")
