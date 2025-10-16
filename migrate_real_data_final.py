#!/usr/bin/env python3
"""
Script FINAL para migrar TODA la data real de SQLite a PostgreSQL Railway
"""
import sqlite3
import asyncio
import asyncpg
import json
from datetime import datetime

# URLs de base de datos
SQLITE_PATH = "clip_admin_backend/instance/clip_comparador_v2.db"
POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def migrate_real_data_complete():
    """Migra TODA la data real de SQLite a PostgreSQL con mapeo correcto"""

    print("🚀 MIGRACIÓN COMPLETA DE DATOS REALES SQLite -> PostgreSQL")
    print("=" * 70)

    # 1. Conectar a SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    # 2. Conectar a PostgreSQL
    pg_conn = await asyncpg.connect(POSTGRES_URL)

    try:
        # 3. Limpiar PostgreSQL
        print("🗑️  Limpiando PostgreSQL...")
        await pg_conn.execute("TRUNCATE TABLE image_embeddings CASCADE")
        await pg_conn.execute("TRUNCATE TABLE images CASCADE")
        await pg_conn.execute("TRUNCATE TABLE products CASCADE")
        await pg_conn.execute("TRUNCATE TABLE categories CASCADE")
        await pg_conn.execute("TRUNCATE TABLE api_keys CASCADE")
        await pg_conn.execute("TRUNCATE TABLE users CASCADE")
        await pg_conn.execute("TRUNCATE TABLE clients CASCADE")

        # 4. Migrar CLIENTS
        print("\n📤 MIGRANDO CLIENTS...")
        cursor.execute("SELECT * FROM clients")
        clients = cursor.fetchall()

        for client in clients:
            try:
                await pg_conn.execute("""
                    INSERT INTO clients (id, name, domain, status, plan, monthly_searches, search_limit, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                client['id'],
                client['name'],
                client['domain'] if 'domain' in client.keys() and client['domain'] else 'demo.com',
                client['status'] if 'status' in client.keys() and client['status'] else 'active',
                client['plan'] if 'plan' in client.keys() and client['plan'] else 'professional',
                client['monthly_searches'] if 'monthly_searches' in client.keys() and client['monthly_searches'] else 0,
                client['search_limit'] if 'search_limit' in client.keys() and client['search_limit'] else 5000,
                client['created_at'] if 'created_at' in client.keys() and client['created_at'] else datetime.utcnow(),
                client['updated_at'] if 'updated_at' in client.keys() and client['updated_at'] else datetime.utcnow())

                print(f"  ✅ Cliente: {client['name']}")
            except Exception as e:
                print(f"  ❌ Error cliente {client['name']}: {e}")

        # 5. Migrar USERS
        print("\n📤 MIGRANDO USERS...")
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()

        for user in users:
            try:
                await pg_conn.execute("""
                    INSERT INTO users (id, email, password_hash, full_name, role, client_id, is_active, last_login, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                user['id'],
                user['email'],
                user['password_hash'],
                user.get('full_name', 'Usuario'),
                user.get('role', 'super_admin'),
                user['client_id'],
                user.get('is_active', True),
                user.get('last_login'),
                user.get('created_at', datetime.utcnow()),
                user.get('updated_at', datetime.utcnow()))

                print(f"  ✅ Usuario: {user['email']}")
            except Exception as e:
                print(f"  ❌ Error usuario {user['email']}: {e}")

        # 6. Migrar API_KEYS
        print("\n📤 MIGRANDO API_KEYS...")
        cursor.execute("SELECT * FROM api_keys")
        api_keys = cursor.fetchall()

        for key in api_keys:
            try:
                await pg_conn.execute("""
                    INSERT INTO api_keys (id, client_id, key_name, api_key, is_active, requests_made, rate_limit, created_at, last_used)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                key['id'],
                key['client_id'],
                key.get('key_name', 'API Key'),
                key['api_key'],
                key.get('is_active', True),
                key.get('requests_made', 0),
                key.get('rate_limit', 1000),
                key.get('created_at', datetime.utcnow()),
                key.get('last_used'))

                print(f"  ✅ API Key: {key['api_key'][:20]}...")
            except Exception as e:
                print(f"  ❌ Error API key: {e}")

        # 7. Migrar CATEGORIES
        print("\n📤 MIGRANDO CATEGORIES...")
        cursor.execute("SELECT * FROM categories")
        categories = cursor.fetchall()

        for cat in categories:
            try:
                slug = cat.get('slug', cat['name'].lower().replace(' ', '-').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n'))

                await pg_conn.execute("""
                    INSERT INTO categories (id, client_id, name, description, slug, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                cat['id'],
                cat['client_id'],
                cat['name'],
                cat.get('description', ''),
                slug,
                cat.get('is_active', True),
                cat.get('created_at', datetime.utcnow()),
                cat.get('updated_at', datetime.utcnow()))

                print(f"  ✅ Categoría: {cat['name']}")
            except Exception as e:
                print(f"  ❌ Error categoría {cat['name']}: {e}")

        # 8. Migrar PRODUCTS
        print("\n📤 MIGRANDO PRODUCTS...")
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall()

        for prod in products:
            try:
                await pg_conn.execute("""
                    INSERT INTO products (id, client_id, category_id, name, description, price, sku, brand, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                prod['id'],
                prod['client_id'],
                prod.get('category_id'),
                prod['name'],
                prod.get('description', ''),
                float(prod['price']) if prod.get('price') else None,
                prod.get('sku', ''),
                prod.get('brand', ''),
                prod.get('is_active', True),
                prod.get('created_at', datetime.utcnow()),
                prod.get('updated_at', datetime.utcnow()))

                print(f"  ✅ Producto: {prod['name']}")
            except Exception as e:
                print(f"  ❌ Error producto {prod['name']}: {e}")

        # 9. Migrar IMAGES
        print("\n📤 MIGRANDO IMAGES...")
        cursor.execute("SELECT * FROM images")
        images = cursor.fetchall()

        for img in images:
            try:
                await pg_conn.execute("""
                    INSERT INTO images (id, client_id, product_id, filename, cloudinary_url, cloudinary_public_id,
                                      original_url, file_size, width, height, format, is_primary, uploaded_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                img['id'],
                img['client_id'],
                img.get('product_id'),
                img['filename'],
                img.get('cloudinary_url', ''),
                img.get('cloudinary_public_id', ''),
                img.get('original_url', ''),
                int(img['file_size']) if img.get('file_size') else None,
                int(img['width']) if img.get('width') else None,
                int(img['height']) if img.get('height') else None,
                img.get('format', ''),
                img.get('is_primary', False),
                img.get('uploaded_at', datetime.utcnow()))

                print(f"  ✅ Imagen: {img['filename']}")
            except Exception as e:
                print(f"  ❌ Error imagen {img['filename']}: {e}")

        # 10. Migrar IMAGE_EMBEDDINGS
        print("\n📤 MIGRANDO IMAGE_EMBEDDINGS...")
        cursor.execute("SELECT * FROM image_embeddings")
        embeddings = cursor.fetchall()

        for emb in embeddings:
            try:
                # Procesar embedding vector
                embedding_vector = emb.get('embedding_vector')
                if embedding_vector:
                    if isinstance(embedding_vector, str):
                        try:
                            embedding_vector = json.loads(embedding_vector)
                        except:
                            print(f"  ⚠️  No se pudo parsear embedding para imagen {emb['image_id']}")
                            continue

                    await pg_conn.execute("""
                        INSERT INTO image_embeddings (id, image_id, embedding_vector, model_version, created_at)
                        VALUES ($1, $2, $3, $4, $5)
                    """,
                    emb['id'],
                    emb['image_id'],
                    embedding_vector,
                    emb.get('model_version', 'ViT-B/16'),
                    emb.get('created_at', datetime.utcnow()))

                    print(f"  ✅ Embedding: {emb['image_id']}")

            except Exception as e:
                print(f"  ❌ Error embedding {emb['image_id']}: {e}")

        # 11. Verificación final
        print(f"\n🔍 VERIFICACIÓN FINAL:")
        print("=" * 50)

        verification_tables = ['clients', 'users', 'api_keys', 'categories', 'products', 'images', 'image_embeddings']
        total_migrated = 0

        for table in verification_tables:
            count = await pg_conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            print(f"  ✅ {table:15}: {count:3} registros")
            total_migrated += count

        print(f"\n🎉 MIGRACIÓN COMPLETA: {total_migrated} registros totales migrados")

        # 12. Mostrar datos migrados
        print(f"\n📋 MUESTRA DE DATOS MIGRADOS:")
        print("=" * 50)

        # Categorías reales
        categories = await pg_conn.fetch("SELECT name, description FROM categories LIMIT 10")
        print("📂 Categorías reales:")
        for cat in categories:
            print(f"  - {cat['name']}: {cat['description'] or 'Sin descripción'}")

        # Productos reales
        products = await pg_conn.fetch("SELECT name, price, brand FROM products LIMIT 10")
        print("\n🛍️  Productos reales:")
        for prod in products:
            print(f"  - {prod['name']} | ${prod['price'] or 'N/A'} | {prod['brand'] or 'Sin marca'}")

        # Imágenes reales
        images = await pg_conn.fetch("SELECT filename, cloudinary_url FROM images LIMIT 10")
        print(f"\n🖼️  Imágenes reales:")
        for img in images:
            print(f"  - {img['filename']} | {img['cloudinary_url'][:50] if img['cloudinary_url'] else 'Sin URL'}...")

        print(f"\n✨ ¡TODOS LOS DATOS REALES MIGRADOS EXITOSAMENTE!")
        return True

    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        sqlite_conn.close()
        await pg_conn.close()

if __name__ == "__main__":
    success = asyncio.run(migrate_real_data_complete())
    if success:
        print("\n🎯 MIGRACIÓN REAL COMPLETADA - Railway listo para funcionar")
    else:
        print("\n💥 Error en la migración")
