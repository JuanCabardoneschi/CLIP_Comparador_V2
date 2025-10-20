"""
Sincroniza product_attribute_config desde la base local a Railway.
- Lee DATABASE_URL de .env.local para la base local
- Conecta a Railway con credenciales conocidas (mismas usadas en otros scripts)
- Mapea clientes por slug (local -> Railway)
- UPSERT por (client_id, key) en Railway
"""
import os
import uuid
import json
from pathlib import Path
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
ENV_LOCAL = ROOT / ".env.local"

# Cargar .env.local para la base local
if not ENV_LOCAL.exists():
    raise SystemExit("❌ .env.local no encontrado. Crea uno desde .env.local.example y completa credenciales.")
load_dotenv(ENV_LOCAL)
LOCAL_DB_URL = os.getenv("DATABASE_URL")
if not LOCAL_DB_URL:
    raise SystemExit("❌ DATABASE_URL no definido en .env.local")

# Config Railway (consistente con otros scripts)
RAILWAY_DB = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}


def fetch_local_attribute_configs():
    """Obtiene configs locales junto con el slug del cliente"""
    conn = psycopg2.connect(LOCAL_DB_URL)
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT pac.key, pac.label, pac.type, pac.required, pac.options,
                       COALESCE(pac.field_order, 0) AS field_order,
                       COALESCE(pac.expose_in_search, false) AS expose_in_search,
                       c.slug AS client_slug,
                       c.id   AS local_client_id
                FROM product_attribute_config pac
                JOIN clients c ON c.id = pac.client_id
                ORDER BY c.slug, pac.field_order, pac.label
                """
            )
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


def get_railway_client_id_by_slug(cur, slug: str):
    cur.execute("SELECT id FROM clients WHERE slug = %s LIMIT 1", (slug,))
    row = cur.fetchone()
    return row[0] if row else None


def upsert_attribute_config(cur, client_uuid: uuid.UUID, row: dict):
    # Usar adaptador Json para JSONB
    options = row.get('options', None)
    cur.execute(
        """
        INSERT INTO product_attribute_config
            (client_id, key, label, type, required, options, field_order, expose_in_search)
        VALUES
            (%s,        %s,  %s,    %s,   %s,       %s,      %s,          %s)
        ON CONFLICT (client_id, key)
        DO UPDATE SET
            label = EXCLUDED.label,
            type = EXCLUDED.type,
            required = EXCLUDED.required,
            options = EXCLUDED.options,
            field_order = EXCLUDED.field_order,
            expose_in_search = EXCLUDED.expose_in_search
        """,
        (
            str(client_uuid), row['key'], row['label'], row['type'],
            bool(row['required']), psycopg2.extras.Json(options) if options is not None else None,
            int(row['field_order']), bool(row['expose_in_search'])
        )
    )


def sync_to_railway(rows):
    if not rows:
        print("ℹ️ No hay configuraciones locales para sincronizar")
        return

    conn = psycopg2.connect(**RAILWAY_DB)
    try:
        with conn:
            with conn.cursor() as cur:
                total = 0
                by_client = {}
                for r in rows:
                    slug = r['client_slug']
                    if slug not in by_client:
                        rid = get_railway_client_id_by_slug(cur, slug)
                        by_client[slug] = rid
                    rid = by_client[slug]
                    if rid is None:
                        print(f"⚠️ Cliente con slug '{slug}' no existe en Railway. Saltando {r['key']}")
                        continue
                    try:
                        client_uuid = uuid.UUID(str(rid))
                    except Exception:
                        print(f"⚠️ ID de cliente inválido para slug '{slug}': {rid}. Saltando {r['key']}")
                        continue
                    upsert_attribute_config(cur, client_uuid, r)
                    total += 1
                print(f"✅ Sincronización completada. Registros procesados: {total}")
    finally:
        conn.close()
        print("🔌 Conexión Railway cerrada")


if __name__ == "__main__":
    print("🚀 Leyendo configuraciones locales de atributos...")
    local_rows = fetch_local_attribute_configs()
    print(f"📦 Encontradas {len(local_rows)} configuraciones locales")
    print("🚀 Sincronizando a Railway...")
    sync_to_railway(local_rows)
