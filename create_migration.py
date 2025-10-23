"""
Script para crear la tabla store_search_config directamente en PostgreSQL
Ejecuta este script con: python create_migration.py
"""
import psycopg2
import os
from dotenv import load_dotenv

# Cargar variables de entorno
env_local_path = '.env.local'
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)
    print(f"📄 Cargando configuración desde {env_local_path}")
else:
    load_dotenv()
    print("📄 Cargando configuración desde .env")

# Obtener DATABASE_URL
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL no encontrado en variables de entorno")
    exit(1)

print(f"� Conectando a: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'local'}")

def create_store_search_config_table():
    """Crea la tabla store_search_config si no existe"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Conexión establecida")

        with conn, conn.cursor() as cur:
            # Verificar si la tabla ya existe
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'store_search_config'
                );
            """)
            exists = cur.fetchone()[0]

            if exists:
                print("⚠️  La tabla store_search_config ya existe")
                print("   Verificando estructura...")

                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'store_search_config'
                    ORDER BY ordinal_position;
                """)
                columns = cur.fetchall()
                print("\n   Columnas existentes:")
                for col_name, col_type in columns:
                    print(f"     - {col_name}: {col_type}")

                return

            print("\n🚀 Creando tabla store_search_config...")

            # Crear tabla
            cur.execute("""
                CREATE TABLE store_search_config (
                    store_id UUID PRIMARY KEY,
                    visual_weight FLOAT NOT NULL DEFAULT 0.6,
                    metadata_weight FLOAT NOT NULL DEFAULT 0.3,
                    business_weight FLOAT NOT NULL DEFAULT 0.1,
                    metadata_config JSONB NOT NULL DEFAULT '{"color": {"enabled": true, "weight": 0.3}, "brand": {"enabled": true, "weight": 0.3}, "pattern": {"enabled": false, "weight": 0.2}}'::jsonb,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_store_id FOREIGN KEY (store_id)
                        REFERENCES clients(id) ON DELETE CASCADE
                );
            """)            # Crear índices
            cur.execute("""
                CREATE INDEX idx_store_search_config_store_id
                ON store_search_config(store_id);
            """)

            conn.commit()
            print("✅ Tabla store_search_config creada exitosamente")

            # Mostrar estructura
            cur.execute("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'store_search_config'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            print("\n📊 Estructura de la tabla:")
            for col_name, col_type, col_default in columns:
                default_str = f" (default: {col_default})" if col_default else ""
                print(f"   - {col_name}: {col_type}{default_str}")

    except psycopg2.Error as e:
        print(f"❌ Error de PostgreSQL: {e}")
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()
            print("\n🔌 Conexión cerrada")

if __name__ == "__main__":
    print("=" * 60)
    print("MIGRACIÓN: Crear tabla store_search_config")
    print("=" * 60)
    create_store_search_config_table()
    print("\n✨ Migración completada")
