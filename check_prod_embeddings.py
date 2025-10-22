"""
Verificar estado de embeddings en producción
"""
import psycopg2

def get_conn():
    host = 'ballast.proxy.rlwy.net'
    port = 54363
    database = 'railway'
    user = 'postgres'
    password = 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
    return psycopg2.connect(host=host, port=port, database=database, user=user, password=password)

# Conectar a Railway
conn = get_conn()
cur = conn.cursor()

# Buscar productos de Eve's Store
print("=" * 80)
print("PRODUCTOS DE EVE'S STORE EN PRODUCCIÓN")
print("=" * 80)

cur.execute("""
    SELECT
        cl.name as cliente,
        c.name as categoria,
        c.slug,
        p.name as producto,
        p.sku,
        COUNT(i.id) as image_count,
        COUNT(CASE WHEN i.clip_embedding IS NOT NULL THEN 1 END) as images_with_embedding,
        STRING_AGG(i.upload_status::text, ', ' ORDER BY i.created_at) as upload_statuses,
        STRING_AGG((CASE WHEN i.is_processed THEN 'true' ELSE 'false' END), ', ' ORDER BY i.created_at) as processed_flags
    FROM products p
    JOIN categories c ON p.category_id = c.id
    JOIN clients cl ON c.client_id = cl.id
    LEFT JOIN images i ON i.product_id = p.id
    WHERE cl.name ILIKE '%eve%store%'
    GROUP BY cl.name, c.name, c.slug, p.name, p.sku, p.id
    ORDER BY c.name, p.name
""")

rows = cur.fetchall()

if not rows:
    print("❌ No se encontraron productos para Eve's Store")
else:
    print(f"\n✅ {len(rows)} producto(s) encontrado(s):\n")
    for row in rows:
        cliente, categoria, slug, producto, sku, image_count, images_with_emb, upload_statuses, processed_flags = row
        print(f"Cliente: {cliente}")
        print(f"Categoría: {categoria} (slug: {slug})")
        print(f"Producto: {producto} (SKU: {sku})")
        print(f"Imágenes: {image_count} total, {images_with_emb} con embedding {'✅' if images_with_emb > 0 else '❌'}")
        print(f"Estados de subida: {upload_statuses}")
        print(f"Flags is_processed: {processed_flags}")
        print("-" * 80)

# Verificar centroides
print("\n" + "=" * 80)
print("CENTROIDES DE CATEGORÍAS")
print("=" * 80 + "\n")

cur.execute("""
    SELECT
        c.name,
        c.slug,
        (c.centroid_embedding IS NOT NULL) as has_centroid,
        LENGTH(c.centroid_embedding::text) as centroid_length,
        COUNT(DISTINCT p.id) as product_count,
        COUNT(DISTINCT i.id) as image_count,
        COUNT(DISTINCT CASE WHEN i.clip_embedding IS NOT NULL THEN i.id END) as images_with_emb
    FROM categories c
    JOIN clients cl ON c.client_id = cl.id
    LEFT JOIN products p ON p.category_id = c.id
    LEFT JOIN images i ON i.product_id = p.id
    WHERE cl.name ILIKE '%eve%store%'
    GROUP BY c.id, c.name, c.slug, c.centroid_embedding
    ORDER BY c.name
""")

cat_rows = cur.fetchall()

for row in cat_rows:
    cat_name, slug, has_centroid, centroid_len, prod_count, img_count, imgs_with_emb = row
    print(f"Categoría: {cat_name} (slug: {slug})")
    print(f"Productos: {prod_count}")
    print(f"Imágenes: {img_count} total, {imgs_with_emb} con embedding")
    print(f"Centroide: {'✅ CALCULADO' if has_centroid else '❌ NO CALCULADO'} {f'(length: {centroid_len})' if centroid_len else ''}")
    print("-" * 80)

cur.close()
conn.close()
