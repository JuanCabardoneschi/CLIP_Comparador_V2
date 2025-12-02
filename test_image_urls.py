"""
Script de prueba para verificar las URLs de imágenes antes de migrar
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import json

RAILWAY_DB = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

# Query para obtener un producto con sus imágenes
query = """
    SELECT
        p.name,
        COALESCE(
            json_agg(
                json_build_object(
                    'url', i.cloudinary_url,
                    'is_primary', i.is_primary
                ) ORDER BY i.is_primary DESC, i.display_order
            ) FILTER (WHERE i.id IS NOT NULL AND i.cloudinary_url IS NOT NULL AND LENGTH(i.cloudinary_url) > 60),
            '[]'
        ) as images
    FROM products p
    LEFT JOIN images i ON i.product_id = p.id
    WHERE p.client_id = (SELECT id FROM clients WHERE name = 'Eve''s Store')
    AND p.name = 'top silvia'
    GROUP BY p.id, p.name
"""

conn = psycopg2.connect(**RAILWAY_DB)
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute(query)
result = cur.fetchone()
cur.close()
conn.close()

print("Producto:", result['name'])
print("\nImágenes JSON:")
print(json.dumps(result['images'], indent=2))

if result['images']:
    images = result['images'] if isinstance(result['images'], list) else json.loads(result['images'])
    print(f"\n✅ {len(images)} imagen(es) encontrada(s)")
    for idx, img in enumerate(images, 1):
        print(f"\nImagen {idx}:")
        print(f"  URL: {img['url']}")
        print(f"  Es primaria: {img['is_primary']}")
else:
    print("\n❌ No se encontraron imágenes")
