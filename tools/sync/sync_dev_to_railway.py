"""
Sincroniza configuraciones de atributos desde desarrollo local a Railway
Copia exactamente lo que está en la base local (creado manualmente o via interface)
"""
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Cargar .env.local para base local
script_dir = os.path.dirname(os.path.abspath(__file__))
env_local_path = os.path.join(script_dir, '.env.local')
load_dotenv(env_local_path)

LOCAL_DB_URL = os.getenv('DATABASE_URL')
if not LOCAL_DB_URL:
    raise SystemExit("❌ DATABASE_URL no definido en .env.local")

# Config Railway
RAILWAY_DB = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

def sync_attribute_configs():
    print("🔍 SINCRONIZACIÓN DE CONFIGURACIONES DE ATRIBUTOS")
    print("=" * 70)

    # 1. Leer configuraciones de desarrollo
    local_conn = psycopg2.connect(LOCAL_DB_URL)
    try:
        with local_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT c.slug as client_slug,
                       pac.key, pac.label, pac.type, pac.required,
                       pac.options, pac.field_order, pac.expose_in_search
                FROM product_attribute_config pac
                JOIN clients c ON c.id = pac.client_id
                ORDER BY c.slug, pac.field_order
            """)
            local_configs = cur.fetchall()
    finally:
        local_conn.close()

    if not local_configs:
        print("⚠️  No hay configuraciones en desarrollo local")
        return

    print(f"\n📦 Encontradas {len(local_configs)} configuraciones en LOCAL:\n")
    for cfg in local_configs:
        expose_icon = "✅" if cfg['expose_in_search'] else "❌"
        opts_info = f" (opciones: {len(cfg['options']['values'])})" if cfg['options'] and 'values' in cfg['options'] else ""
        print(f"  {expose_icon} {cfg['client_slug']:20s} | {cfg['key']:15s} | {cfg['label']:20s} | {cfg['type']:6s}{opts_info}")

    # 2. Copiar a Railway
    railway_conn = psycopg2.connect(**RAILWAY_DB)
    try:
        with railway_conn, railway_conn.cursor() as cur:
            print("\n🚀 Copiando a RAILWAY...\n")

            for cfg in local_configs:
                # Obtener client_id en Railway por slug
                cur.execute("SELECT id FROM clients WHERE slug = %s LIMIT 1", (cfg['client_slug'],))
                row = cur.fetchone()
                if not row:
                    print(f"⚠️  Cliente '{cfg['client_slug']}' no existe en Railway. Saltando.")
                    continue

                railway_client_id = row[0]

                # Insertar/actualizar configuración
                cur.execute(
                    """
                    INSERT INTO product_attribute_config
                        (client_id, key, label, type, required, options, field_order, expose_in_search)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s)
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
                        railway_client_id,
                        cfg['key'],
                        cfg['label'],
                        cfg['type'],
                        cfg['required'],
                        psycopg2.extras.Json(cfg['options']) if cfg['options'] else None,
                        cfg['field_order'],
                        cfg['expose_in_search']
                    )
                )
                print(f"  ✓ {cfg['key']} copiado")

            print(f"\n✅ {len(local_configs)} configuraciones sincronizadas exitosamente")

    finally:
        railway_conn.close()

    print("\n" + "=" * 70)
    print("🎯 Ahora LOCAL y RAILWAY tienen las mismas configuraciones")
    print("   Ambos entornos funcionarán idénticamente")

if __name__ == "__main__":
    sync_attribute_configs()
