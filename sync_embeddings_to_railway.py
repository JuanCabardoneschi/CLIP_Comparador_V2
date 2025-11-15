"""
Sincronizar embeddings de local a Railway
"""
import psycopg2

# Conexiones
local_conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='clip_comparador_v2',
    user='postgres',
    password='Laurana@01'
)
railway_conn = psycopg2.connect(
    host='ballast.proxy.rlwy.net',
    port=54363,
    database='railway',
    user='postgres',
    password='xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
)

try:
    local_cur = local_conn.cursor()
    railway_cur = railway_conn.cursor()

    # Leer embeddings de local
    local_cur.execute('SELECT id, key, embedding, type, created_at FROM embeddings')
    rows = local_cur.fetchall()

    print(f"📊 Encontrados {len(rows)} embeddings en BD local")

    inserted = 0
    updated = 0

    for row in rows:
        try:
            # Insertar o actualizar
            railway_cur.execute(
                """
                INSERT INTO embeddings (id, key, embedding, type, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    type = EXCLUDED.type
                """,
                row
            )
            if railway_cur.rowcount > 0:
                if 'INSERT' in railway_cur.statusmessage:
                    inserted += 1
                else:
                    updated += 1
        except Exception as e:
            print(f"❌ Error insertando {row[1]}: {e}")

    railway_conn.commit()
    print(f"✅ Sincronización completada:")
    print(f"   - Nuevos: {inserted}")
    print(f"   - Actualizados: {updated}")
    print(f"   - Total: {inserted + updated}")

finally:
    local_conn.close()
    railway_conn.close()
