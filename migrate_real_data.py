#!/usr/bin/env python3
"""
Script para verificar TODA la data de SQLite y migrarla a PostgreSQL Railway
"""
import sqlite3
import asyncio
import asyncpg
import json
from datetime import datetime

# URLs de base de datos
SQLITE_PATH = "clip_admin_backend/instance/clip_comparador_v2.db"
POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def export_and_migrate_all_data():
    """Exporta TODA la data de SQLite y la migra a PostgreSQL"""

    print("🔍 ANÁLISIS COMPLETO DE DATOS SQLite -> PostgreSQL")
    print("=" * 70)

    # 1. Conectar a SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row  # Para acceso por nombre de columna
    cursor = sqlite_conn.cursor()

    # 2. Conectar a PostgreSQL
    pg_conn = await asyncpg.connect(POSTGRES_URL)

    try:
        print("\n📊 VERIFICANDO DATOS EN SQLite:")
        print("=" * 50)

        # Verificar todas las tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tablas en SQLite: {tables}")

        all_data = {}

        # Exportar datos de cada tabla
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"\n📋 Tabla '{table}': {count} registros")

            if count > 0:
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                all_data[table] = [dict(row) for row in rows]

                # Mostrar estructura de datos
                if rows:
                    first_row = dict(rows[0])
                    print(f"   Columnas: {list(first_row.keys())}")

                    # Mostrar algunos datos de ejemplo
                    for i, row_dict in enumerate(all_data[table][:3]):
                        print(f"   Fila {i+1}: {dict(row_dict)}")
                        if i >= 2:  # Solo mostrar primeras 3 filas
                            break

        print(f"\n💾 DATOS EXPORTADOS:")
        print("=" * 50)
        for table, data in all_data.items():
            print(f"  - {table}: {len(data)} registros")

        # 3. Migrar datos a PostgreSQL
        print(f"\n🚀 MIGRANDO A PostgreSQL:")
        print("=" * 50)

        # Limpiar PostgreSQL primero
        await pg_conn.execute("TRUNCATE TABLE image_embeddings CASCADE")
        await pg_conn.execute("TRUNCATE TABLE images CASCADE")
        await pg_conn.execute("TRUNCATE TABLE products CASCADE")
        await pg_conn.execute("TRUNCATE TABLE categories CASCADE")
        await pg_conn.execute("TRUNCATE TABLE api_keys CASCADE")
        await pg_conn.execute("TRUNCATE TABLE users CASCADE")
        await pg_conn.execute("TRUNCATE TABLE clients CASCADE")
        print("🗑️  Tablas PostgreSQL limpiadas")

        # Migrar en orden correcto por dependencias
        migration_order = ['clients', 'users', 'api_keys', 'categories', 'products', 'images', 'image_embeddings']

        for table in migration_order:
            if table in all_data and all_data[table]:
                print(f"\n📤 Migrando tabla '{table}'...")

                data = all_data[table]
                migrated_count = 0

                for row in data:
                    try:
                        if table == 'clients':
                            await pg_conn.execute("""
                                INSERT INTO clients (id, name, domain, status, plan, monthly_searches, search_limit, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            """, row['id'], row['name'], row.get('domain'), row.get('status', 'active'),
                                row.get('plan', 'starter'), row.get('monthly_searches', 0),
                                row.get('search_limit', 1000), row.get('created_at'), row.get('updated_at'))

                        elif table == 'users':
                            await pg_conn.execute("""
                                INSERT INTO users (id, email, password_hash, full_name, role, client_id, is_active, last_login, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                            """, row['id'], row['email'], row['password_hash'], row.get('full_name'),
                                row.get('role', 'client_admin'), row['client_id'], row.get('is_active', True),
                                row.get('last_login'), row.get('created_at'), row.get('updated_at'))

                        elif table == 'api_keys':
                            await pg_conn.execute("""
                                INSERT INTO api_keys (id, client_id, key_name, api_key, is_active, requests_made, rate_limit, created_at, last_used)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            """, row['id'], row['client_id'], row.get('key_name', 'API Key'), row['api_key'],
                                row.get('is_active', True), row.get('requests_made', 0), row.get('rate_limit', 100),
                                row.get('created_at'), row.get('last_used'))

                        elif table == 'categories':
                            await pg_conn.execute("""
                                INSERT INTO categories (id, client_id, name, description, slug, is_active, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            """, row['id'], row['client_id'], row['name'], row.get('description'),
                                row.get('slug', row['name'].lower().replace(' ', '-')), row.get('is_active', True),
                                row.get('created_at'), row.get('updated_at'))

                        elif table == 'products':
                            await pg_conn.execute("""
                                INSERT INTO products (id, client_id, category_id, name, description, price, sku, brand, is_active, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            """, row['id'], row['client_id'], row.get('category_id'), row['name'],
                                row.get('description'), row.get('price'), row.get('sku'), row.get('brand'),
                                row.get('is_active', True), row.get('created_at'), row.get('updated_at'))

                        elif table == 'images':
                            await pg_conn.execute("""
                                INSERT INTO images (id, client_id, product_id, filename, cloudinary_url, cloudinary_public_id,
                                                  original_url, file_size, width, height, format, is_primary, uploaded_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                            """, row['id'], row['client_id'], row.get('product_id'), row['filename'],
                                row.get('cloudinary_url'), row.get('cloudinary_public_id'), row.get('original_url'),
                                row.get('file_size'), row.get('width'), row.get('height'), row.get('format'),
                                row.get('is_primary', False), row.get('uploaded_at'))

                        elif table == 'image_embeddings':
                            # Convertir el embedding de string a array si es necesario
                            embedding = row.get('embedding_vector')
                            if isinstance(embedding, str):
                                try:
                                    embedding = json.loads(embedding)
                                except:
                                    embedding = None

                            if embedding:
                                await pg_conn.execute("""
                                    INSERT INTO image_embeddings (id, image_id, embedding_vector, model_version, created_at)
                                    VALUES ($1, $2, $3, $4, $5)
                                """, row['id'], row['image_id'], embedding,
                                    row.get('model_version', 'ViT-B/16'), row.get('created_at'))

                        migrated_count += 1

                    except Exception as e:
                        print(f"   ⚠️  Error migrando fila en {table}: {e}")
                        print(f"   Datos: {row}")

                print(f"   ✅ {migrated_count}/{len(data)} registros migrados")

        # 4. Verificación final
        print(f"\n🔍 VERIFICACIÓN FINAL PostgreSQL:")
        print("=" * 50)

        verification_tables = ['clients', 'users', 'categories', 'products', 'images', 'image_embeddings']
        for table in verification_tables:
            count = await pg_conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            print(f"  ✅ {table}: {count} registros")

        # Mostrar algunos datos migrados para verificar
        print(f"\n📋 MUESTRA DE DATOS MIGRADOS:")
        print("=" * 50)

        # Categorías
        categories = await pg_conn.fetch("SELECT name, description FROM categories LIMIT 5")
        print("Categorías:")
        for cat in categories:
            print(f"  - {cat['name']}: {cat['description'] or 'Sin descripción'}")

        # Productos
        products = await pg_conn.fetch("SELECT name, price, brand FROM products LIMIT 5")
        print("\nProductos:")
        for prod in products:
            print(f"  - {prod['name']} | ${prod['price'] or 'N/A'} | {prod['brand'] or 'Sin marca'}")

        # Imágenes
        images = await pg_conn.fetch("SELECT filename, cloudinary_url FROM images LIMIT 5")
        print("\nImágenes:")
        for img in images:
            print(f"  - {img['filename']} | {img['cloudinary_url'] or 'Sin URL'}")

        print(f"\n🎉 MIGRACIÓN COMPLETA EXITOSA!")

    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sqlite_conn.close()
        await pg_conn.close()

if __name__ == "__main__":
    asyncio.run(export_and_migrate_all_data())
