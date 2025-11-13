import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="clip_comparador_v2",
    user="postgres",
    password="Laurana@01"
)

cur = conn.cursor()

# Contar productos con color
cur.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN attributes->>'color' IS NOT NULL AND attributes->>'color' != '' THEN 1 END) as with_color,
        COUNT(CASE WHEN attributes->>'color' IS NULL OR attributes->>'color' = '' THEN 1 END) as without_color
    FROM products p
    JOIN clients c ON p.client_id = c.id
    WHERE c.name = 'Goody Store'
""")

result = cur.fetchone()
print(f"Total: {result[0]}, Con color: {result[1]}, Sin color: {result[2]}")

# Mostrar colores en categoría CAMISAS
cur.execute("""
    SELECT p.name, p.attributes->>'color' as color
    FROM products p
    JOIN clients c ON p.client_id = c.id
    JOIN categories cat ON p.category_id = cat.id
    WHERE c.name = 'Goody Store'
    AND cat.name LIKE '%CAMISA%'
    AND p.attributes->>'color' IS NOT NULL
""")

print("\nColores en categoria CAMISAS:")
for row in cur.fetchall():
    print(f"  - {row[0]}: {row[1]}")

cur.close()
conn.close()
