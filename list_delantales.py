"""Lista todos los delantales y sus colores"""
import os
import psycopg2
import json
from dotenv import load_dotenv

load_dotenv('.env.local')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cursor = conn.cursor()

cursor.execute("""
    SELECT p.name, p.sku, p.attributes
    FROM products p
    JOIN categories c ON p.category_id = c.id
    WHERE c.name = 'DELANTAL'
    AND p.attributes IS NOT NULL
    ORDER BY p.name
""")

rows = cursor.fetchall()
print(f"\nEncontrados {len(rows)} delantales:\n")

for i, (name, sku, attrs) in enumerate(rows, 1):
    if isinstance(attrs, str):
        attrs_dict = json.loads(attrs)
    else:
        attrs_dict = attrs

    color = attrs_dict.get('color', 'N/A')
    print(f"{i}. {name}")
    print(f"   SKU: {sku}, Color: {color}")

cursor.close()
conn.close()
