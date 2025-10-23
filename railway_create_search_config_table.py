"""
Railway Migration - Create store_search_config table

Ejecuta la migración de FASE 1 en Railway PostgreSQL
Uso: python railway_create_search_config_table.py --yes
"""
import os
import sys
import psycopg2


def get_conn():
    """Conectar a Railway PostgreSQL usando credenciales del proyecto"""
    host = os.getenv('RAILWAY_DB_HOST', 'ballast.proxy.rlwy.net')
    port = int(os.getenv('RAILWAY_DB_PORT', '54363'))
    database = os.getenv('RAILWAY_DB', 'railway')
    user = os.getenv('RAILWAY_DB_USER', 'postgres')
    password = os.getenv('RAILWAY_DB_PASSWORD', 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum')

    print(f"🔌 Conectando a Railway PostgreSQL...")
    print(f"   Host: {host}:{port}")
    print(f"   Database: {database}")
    print(f"   User: {user}")

    return psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        connect_timeout=10
    )


def check_table_exists(cur):
    """Verificar si la tabla ya existe"""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'store_search_config'
        );
    """)
    return cur.fetchone()[0]


def check_clients_exist(cur):
    """Verificar cuántos clientes existen"""
    cur.execute("SELECT COUNT(*) FROM clients;")
    return cur.fetchone()[0]


def create_table(cur):
    """Crear tabla store_search_config"""
    sql = """
    CREATE TABLE IF NOT EXISTS store_search_config (
        store_id UUID PRIMARY KEY,
        visual_weight FLOAT NOT NULL DEFAULT 0.6,
        metadata_weight FLOAT NOT NULL DEFAULT 0.3,
        business_weight FLOAT NOT NULL DEFAULT 0.1,
        metadata_config JSONB NOT NULL DEFAULT '{"color_weight": 1.0, "brand_weight": 1.0, "pattern_weight": 0.8, "material_weight": 0.7, "style_weight": 0.6}'::jsonb,
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
        CONSTRAINT fk_store_search_config_client
            FOREIGN KEY (store_id)
            REFERENCES clients(id)
            ON DELETE CASCADE
    );
    """
    print("📝 Creando tabla store_search_config...")
    cur.execute(sql)


def create_index(cur):
    """Crear índice para performance"""
    sql = """
    CREATE INDEX IF NOT EXISTS idx_store_search_config_store_id
    ON store_search_config(store_id);
    """
    print("📝 Creando índice idx_store_search_config_store_id...")
    cur.execute(sql)


def seed_existing_clients(cur):
    """Insertar configuración default para clientes existentes"""
    sql = """
    INSERT INTO store_search_config (store_id, visual_weight, metadata_weight, business_weight)
    SELECT
        id,
        0.6,
        0.3,
        0.1
    FROM clients
    WHERE id NOT IN (SELECT store_id FROM store_search_config)
    ON CONFLICT (store_id) DO NOTHING;
    """
    print("📝 Insertando configuraciones default para clientes existentes...")
    cur.execute(sql)
    return cur.rowcount


def verify_data(cur):
    """Verificar datos insertados"""
    sql = """
    SELECT
        c.name as client_name,
        ssc.visual_weight,
        ssc.metadata_weight,
        ssc.business_weight,
        ssc.created_at
    FROM store_search_config ssc
    JOIN clients c ON c.id = ssc.store_id
    ORDER BY c.name;
    """
    cur.execute(sql)
    rows = cur.fetchall()

    print("\n📊 Configuraciones creadas:")
    print(f"{'Cliente':<30} | Visual | Metadata | Business | Creado")
    print("-" * 80)
    for row in rows:
        name, visual, metadata, business, created = row
        print(f"{name:<30} | {visual:.1f}    | {metadata:.1f}      | {business:.1f}      | {created}")

    return len(rows)


def main():
    # Parse argumentos
    dry_run = '--yes' not in sys.argv

    if dry_run:
        print("🛟 MODO SEGURO: Se hará ROLLBACK al final (usa --yes para confirmar cambios)")
    else:
        print("✅ MODO COMMIT: Los cambios serán permanentes")

    print()

    try:
        with get_conn() as conn:
            conn.autocommit = False  # Transacciones manuales

            with conn.cursor() as cur:
                # 1. Verificar estado actual
                print("🔍 Verificando estado actual...")
                table_exists = check_table_exists(cur)
                num_clients = check_clients_exist(cur)

                print(f"   Tabla 'store_search_config' existe: {'✅ SÍ' if table_exists else '❌ NO'}")
                print(f"   Clientes en BD: {num_clients}")
                print()

                if table_exists:
                    print("⚠️ La tabla ya existe. Verificando datos...")
                    num_configs = verify_data(cur)

                    if num_configs == num_clients:
                        print(f"\n✅ TODO OK: {num_configs} configuraciones existen para {num_clients} clientes")
                        print("   No se requieren cambios.")
                        return
                    else:
                        print(f"\n⚠️ Faltan configuraciones: {num_configs}/{num_clients}")
                        print("   Procediendo a crear configuraciones faltantes...")
                        inserted = seed_existing_clients(cur)
                        print(f"   ✅ {inserted} configuraciones insertadas")
                else:
                    # 2. Crear tabla
                    create_table(cur)
                    print("   ✅ Tabla creada")

                    # 3. Crear índice
                    create_index(cur)
                    print("   ✅ Índice creado")

                    # 4. Seed data
                    inserted = seed_existing_clients(cur)
                    print(f"   ✅ {inserted} configuraciones insertadas")

                print()

                # 5. Verificar resultado
                num_configs = verify_data(cur)
                print(f"\n✅ Total configuraciones: {num_configs}")

                # 6. Commit o Rollback
                print()
                if dry_run:
                    conn.rollback()
                    print("🛟 ROLLBACK ejecutado (modo seguro)")
                    print("   Para aplicar cambios, ejecuta: python railway_create_search_config_table.py --yes")
                else:
                    conn.commit()
                    print("✅ COMMIT ejecutado - Cambios aplicados en Railway")
                    print(f"   {num_configs} configuraciones ahora disponibles")

    except psycopg2.Error as e:
        print(f"\n❌ ERROR de PostgreSQL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
