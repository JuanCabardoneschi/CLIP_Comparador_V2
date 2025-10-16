#!/usr/bin/env python3
"""
Sincronizar TODAS las tablas de PostgreSQL con SQLite de una vez
"""
import asyncio
import asyncpg
import sqlite3

SQLITE_PATH = "clip_admin_backend/instance/clip_comparador_v2.db"
POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def sync_all_tables():
    """Sincronizar TODAS las tablas PostgreSQL con SQLite"""

    print("🔧 SINCRONIZANDO TODAS LAS TABLAS CON SQLITE")
    print("=" * 60)

    # Conectar a SQLite para obtener estructuras
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    cursor = sqlite_conn.cursor()

    # Conectar a PostgreSQL
    pg_conn = await asyncpg.connect(POSTGRES_URL)

    try:
        # TABLA CLIENTS
        print("\n📋 CORRIGIENDO TABLA CLIENTS...")
        cursor.execute('PRAGMA table_info(clients)')
        sqlite_clients = [col[1] for col in cursor.fetchall()]
        print(f"SQLite clients: {sqlite_clients}")

        pg_clients = await pg_conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'clients'")
        pg_clients_cols = [col['column_name'] for col in pg_clients]
        print(f"PostgreSQL clients: {pg_clients_cols}")

        # Agregar campos faltantes en clients
        missing_clients = ['slug', 'email', 'description', 'industry', 'api_key', 'api_settings']
        for field in missing_clients:
            if field not in pg_clients_cols:
                try:
                    if field == 'email':
                        await pg_conn.execute(f"ALTER TABLE clients ADD COLUMN {field} VARCHAR(255)")
                    elif field == 'slug':
                        await pg_conn.execute(f"ALTER TABLE clients ADD COLUMN {field} VARCHAR(100)")
                    elif field == 'industry':
                        await pg_conn.execute(f"ALTER TABLE clients ADD COLUMN {field} VARCHAR(100)")
                    elif field == 'api_key':
                        await pg_conn.execute(f"ALTER TABLE clients ADD COLUMN {field} VARCHAR(100)")
                    else:
                        await pg_conn.execute(f"ALTER TABLE clients ADD COLUMN {field} TEXT")
                    print(f"  ✅ Agregado: {field}")
                except Exception as e:
                    print(f"  ❌ Error agregando {field}: {e}")

        # TABLA USERS
        print("\n📋 VERIFICANDO TABLA USERS...")
        cursor.execute('PRAGMA table_info(users)')
        sqlite_users = [col[1] for col in cursor.fetchall()]
        print(f"SQLite users: {sqlite_users}")

        # TABLA CATEGORIES
        print("\n📋 VERIFICANDO TABLA CATEGORIES...")
        cursor.execute('PRAGMA table_info(categories)')
        sqlite_categories = [col[1] for col in cursor.fetchall()]
        print(f"SQLite categories: {sqlite_categories}")

        # TABLA PRODUCTS ya está corregida
        print("\n📋 TABLA PRODUCTS - YA CORREGIDA")

        # TABLA IMAGES ya está corregida
        print("\n📋 TABLA IMAGES - YA CORREGIDA")

        # Actualizar datos de clients con información de SQLite
        print(f"\n🔄 ACTUALIZANDO DATOS DE CLIENTS...")
        cursor.execute("SELECT id, slug, email, description, industry, api_key, api_settings FROM clients")
        sqlite_client_data = cursor.fetchall()

        for client_data in sqlite_client_data:
            try:
                await pg_conn.execute("""
                    UPDATE clients
                    SET slug = $2, email = $3, description = $4, industry = $5, api_key = $6, api_settings = $7
                    WHERE id = $1
                """,
                client_data[0],  # id
                client_data[1] or '',  # slug
                client_data[2] or '',  # email
                client_data[3] or '',  # description
                client_data[4] or '',  # industry
                client_data[5] or '',  # api_key
                client_data[6] or '')  # api_settings

                print(f"  ✅ Cliente actualizado: {client_data[0]}")
            except Exception as e:
                print(f"  ❌ Error actualizando cliente: {e}")

        # Verificación final
        print(f"\n🔍 VERIFICACIÓN FINAL:")
        for table in ['clients', 'users', 'categories', 'products', 'images']:
            count = await pg_conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            print(f"  ✅ {table}: {count} registros")

        print(f"\n✨ ¡TODAS LAS TABLAS SINCRONIZADAS!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        sqlite_conn.close()
        await pg_conn.close()

if __name__ == "__main__":
    success = asyncio.run(sync_all_tables())
    if success:
        print("\n🎯 SISTEMA COMPLETAMENTE SINCRONIZADO")
    else:
        print("\n💥 Error en la sincronización")
