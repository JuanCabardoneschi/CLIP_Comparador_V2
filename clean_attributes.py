"""
Script para limpiar el campo attributes de la tabla products.
Elimina los campos que ya existen como columnas individuales.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Cargar variables de entorno
env_file = os.path.join(os.path.dirname(__file__), '.env.local')
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"✅ Variables cargadas desde {env_file}")
else:
    print(f"❌ No se encontró {env_file}")
    sys.exit(1)

# Obtener DATABASE_URL
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ DATABASE_URL no está configurada")
    sys.exit(1)

print(f"🔗 Conectando a base de datos...")

# Crear engine
engine = create_engine(DATABASE_URL)

# Campos que NO deben estar en attributes (porque son columnas)
FIELDS_TO_REMOVE = [
    'tags',
    'brand',
    'color',
    'price',
    'stock',
    'is_active',
    'created_at',
    'updated_at'
]

print(f"\n🧹 Limpiando campos: {', '.join(FIELDS_TO_REMOVE)}")
print("=" * 60)

try:
    with engine.connect() as conn:
        # Obtener productos con attributes
        result = conn.execute(text("""
            SELECT id, name, attributes
            FROM products
            WHERE attributes IS NOT NULL
        """))

        products = result.fetchall()
        print(f"📦 Total de productos con attributes: {len(products)}")

        updated = 0
        unchanged = 0

        for product in products:
            product_id, name, attributes = product

            if not attributes:
                unchanged += 1
                continue

            # Crear nuevo dict sin los campos prohibidos
            clean_attributes = {
                k: v for k, v in attributes.items()
                if k not in FIELDS_TO_REMOVE
            }

            # Si hubo cambios, actualizar
            if clean_attributes != attributes:
                import json
                attrs_json = json.dumps(clean_attributes) if clean_attributes else None

                conn.execute(
                    text("""
                        UPDATE products
                        SET attributes = CAST(:attrs AS jsonb)
                        WHERE id = :id
                    """),
                    {
                        'attrs': attrs_json,
                        'id': str(product_id)
                    }
                )

                removed = set(attributes.keys()) - set(clean_attributes.keys())
                print(f"   ✓ {name}: Eliminados {removed}")
                updated += 1
            else:
                unchanged += 1

        # Commit
        conn.commit()

        print("=" * 60)
        print(f"✅ Limpieza completada:")
        print(f"   - Productos actualizados: {updated}")
        print(f"   - Productos sin cambios: {unchanged}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✨ Script finalizado exitosamente")
