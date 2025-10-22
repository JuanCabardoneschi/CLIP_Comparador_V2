"""
Resetear flags de embeddings para Eve's Store en producción
"""
import psycopg2

conn = psycopg2.connect('postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway')
cur = conn.cursor()

# Poner imágenes en pendiente y limpiar embeddings
cur.execute("""
    UPDATE images i
    SET is_processed = FALSE,
        upload_status = 'pending',
        error_message = NULL,
        clip_embedding = NULL
    FROM products p
    JOIN categories c ON p.category_id = c.id
    JOIN clients cl ON c.client_id = cl.id
    WHERE i.product_id = p.id
      AND cl.name ILIKE '%eve%store%';
""")

conn.commit()
print("✅ Imágenes reseteadas a pending para Eve's Store")

cur.close()
conn.close()
