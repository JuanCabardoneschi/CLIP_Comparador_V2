"""
Corrige estados de imágenes en Railway: si clip_embedding IS NOT NULL pero
is_processed es False o upload_status != 'completed', los marca como completados.

Se conecta directamente a Railway (ballast.proxy.rlwy.net:54363).
"""
import psycopg2
import psycopg2.extras

RAILWAY_DB = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

SQL_COUNTS = {
    'total': "SELECT COUNT(*) FROM images",
    'processed': "SELECT COUNT(*) FROM images WHERE is_processed = TRUE",
    'pending': "SELECT COUNT(*) FROM images WHERE is_processed = FALSE AND upload_status = 'pending'",
    'failed': "SELECT COUNT(*) FROM images WHERE upload_status = 'failed'",
}

SQL_FIX = (
    """
    UPDATE images
       SET is_processed = TRUE,
           upload_status = 'completed',
           updated_at = NOW()
     WHERE clip_embedding IS NOT NULL
       AND (is_processed = FALSE OR upload_status <> 'completed');
    """
)


def get_counts(cur):
    res = {}
    for k, q in SQL_COUNTS.items():
        cur.execute(q)
        res[k] = cur.fetchone()[0]
    return res


def main():
    print("🔌 Conectando a Railway…")
    conn = psycopg2.connect(**RAILWAY_DB)
    try:
        with conn:
            with conn.cursor() as cur:
                before = get_counts(cur)
                print(f"Antes: total={before['total']} procesadas={before['processed']} pendientes={before['pending']} fallidas={before['failed']}")
                print("🔧 Corrigiendo estados incoherentes…")
                cur.execute(SQL_FIX)
                print(f"Filas afectadas: {cur.rowcount}")
                after = get_counts(cur)
                print(f"Después: total={after['total']} procesadas={after['processed']} pendientes={after['pending']} fallidas={after['failed']}")
    finally:
        conn.close()
        print("✅ Hecho. Conexión cerrada.")


if __name__ == '__main__':
    main()
