"""
Sincroniza client_vocabulary_cache de la BD local hacia Railway.

Uso:
  python sync_vocab_cache_to_railway.py
  python sync_vocab_cache_to_railway.py --client <uuid>
"""
import argparse
import json
import psycopg2

# Conexiones (ajustadas a patrón existente en sync_embeddings_to_railway.py)
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--client', dest='client_id', help='UUID del cliente a sincronizar (opcional)')
    args = parser.parse_args()

    try:
        local_cur = local_conn.cursor()
        railway_cur = railway_conn.cursor()

        if args.client_id:
            print(f"📦 Leyendo caché local de vocabulario para cliente {args.client_id}...")
            local_cur.execute(
                'SELECT client_id, vocabulary, updated_at FROM client_vocabulary_cache WHERE client_id = %s',
                (args.client_id,)
            )
        else:
            print("📦 Leyendo caché local de vocabulario para TODOS los clientes...")
            local_cur.execute('SELECT client_id, vocabulary, updated_at FROM client_vocabulary_cache')

        rows = local_cur.fetchall()
        print(f"🔎 {len(rows)} fila(s) a sincronizar")

        inserted = 0
        updated = 0

        for row in rows:
            client_id, vocabulary, updated_at = row
            try:
                railway_cur.execute(
                    """
                    INSERT INTO client_vocabulary_cache (client_id, vocabulary, created_at, updated_at)
                    VALUES (%s, %s::jsonb, NOW(), %s)
                    ON CONFLICT (client_id)
                    DO UPDATE SET vocabulary = EXCLUDED.vocabulary, updated_at = EXCLUDED.updated_at
                    """,
                    (str(client_id), json.dumps(vocabulary) if isinstance(vocabulary, dict) else vocabulary, updated_at)
                )
                # statusmessage detection is not reliable across drivers; count as updated/inserted generically
                if railway_cur.rowcount:
                    updated += 1
            except Exception as e:
                print(f"❌ Error sincronizando cliente {client_id}: {e}")

        railway_conn.commit()
        print("✅ Sincronización completada")
        print(f"   - Upserts: {updated}")

    finally:
        local_conn.close()
        railway_conn.close()


if __name__ == '__main__':
    main()
