import psycopg2
from dotenv import load_dotenv
import os
import json

load_dotenv('.env.local')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute("""
SELECT p.name, p.attributes, c.name as categoria, c.clip_prompt
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
WHERE p.name LIKE '%GORRA%' OR p.name LIKE '%CUP%'
""")

rows = cur.fetchall()

for r in rows:
    print(f"Producto: {r[0]}")
    print(f"Categoría: {r[2]} | CLIP Prompt: {r[3]}")
    attrs = r[1] if isinstance(r[1], dict) else (json.loads(r[1]) if r[1] else {})
    print(f"Atributos: {json.dumps(attrs, indent=2, ensure_ascii=False)}")
    print("---\n")

cur.close()
conn.close()
