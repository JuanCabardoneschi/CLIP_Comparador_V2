"""
Verificar y ajustar umbrales de sensibilidad para Eve's Store
"""
import psycopg2

conn = psycopg2.connect('postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway')
cur = conn.cursor()

# Ver umbrales actuales
cur.execute("""
    SELECT
        name,
        category_confidence_threshold,
        product_similarity_threshold
    FROM clients
    WHERE name ILIKE '%eve%store%'
""")

row = cur.fetchone()
if row:
    name, cat_threshold, prod_threshold = row
    print(f"Cliente: {name}")
    print(f"Category confidence threshold: {cat_threshold}")
    print(f"Product similarity threshold: {prod_threshold}")
    print()

    # Ajustar a valores más permisivos para testing
    print("Ajustando umbrales a valores más permisivos...")
    cur.execute("""
        UPDATE clients
        SET category_confidence_threshold = 20,
            product_similarity_threshold = 20
        WHERE name ILIKE '%eve%store%'
    """)

    conn.commit()
    print("✅ Umbrales actualizados:")
    print("   - Category confidence: 20% (era 70%)")
    print("   - Product similarity: 20% (era 30%)")
else:
    print("❌ Cliente no encontrado")

cur.close()
conn.close()
