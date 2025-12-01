import psycopg2
import json

# Conexión a Railway
conn = psycopg2.connect(
    host="ballast.proxy.rlwy.net",
    port=54363,
    database="railway",
    user="postgres",
    password="xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum"
)

cur = conn.cursor()

# Obtener imágenes de Goody
skus = ['GOD-CHQ-002', 'GOD-CAM-001', 'GOD-GOR-001', 'GOD-CAR-002', 'GOD-BUZ-001', 'GOD-AMB-002']
images = {}

for sku in skus:
    cur.execute("""
        SELECT p.name, i.base64_data
        FROM products p
        JOIN images i ON i.product_id = p.id AND i.is_primary = true
        JOIN clients c ON c.id = p.client_id
        WHERE c.name = 'Goody Store' AND p.sku = %s
    """, (sku,))

    row = cur.fetchone()
    if row:
        images[sku] = row[1]  # base64_data
        print(f"✓ {sku}: {row[0][:50]}... ({len(row[1])} chars)")

# Obtener imágenes de Noa
cur.execute("""
    SELECT p.sku, i.base64_data
    FROM products p
    JOIN images i ON i.product_id = p.id AND i.is_primary = true
    JOIN clients c ON c.id = p.client_id
    WHERE c.name = 'Noa Store'
""")

for row in cur.fetchall():
    images[row[0]] = row[1]
    print(f"✓ {row[0]}: ({len(row[1])} chars)")

cur.close()
conn.close()

# Guardar en JSON para uso fácil
with open('base64_images.json', 'w', encoding='utf-8') as f:
    json.dump(images, f)

print(f"\n✅ {len(images)} imágenes extraídas a base64_images.json")
