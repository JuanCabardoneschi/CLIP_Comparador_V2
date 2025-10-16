#!/usr/bin/env python3
"""
Script FINAL - Migración COMPLETA sin embeddings
Los embeddings se generarán desde el sistema funcionando
"""
import sqlite3
import asyncio
import asyncpg
from datetime import datetime

# URLs de base de datos
SQLITE_PATH = "clip_admin_backend/instance/clip_comparador_v2.db"
POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

def safe_get(row, key, default=None):
    """Obtiene valor de sqlite3.Row de forma segura"""
    try:
        return row[key] if key in row.keys() and row[key] is not None else default
    except:
        return default

def to_bool(value):
    """Convierte valores de SQLite (0/1) a boolean"""
    if value is None:
        return None
    return bool(int(value))

def to_datetime(value):
    """Convierte string de fecha a datetime"""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return datetime.utcnow()
    return value

async def migrate_all_data_no_embeddings():
    """Migra TODA la data real excepto embeddings"""

    print("🚀 MIGRACIÓN COMPLETA - SIN EMBEDDINGS")
    print("=" * 50)
    print("📝 Los embeddings se generarán desde el sistema funcionando")
    print("=" * 50)

    # 1. Conectar a SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    # 2. Conectar a PostgreSQL
    pg_conn = await asyncpg.connect(POSTGRES_URL)

    try:
        # 3. Limpiar PostgreSQL (sin embeddings)
        print("🗑️  Limpiando PostgreSQL...")
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
        clients_count = 0

        for client in clients:
            try:
                await pg_conn.execute("""
                    INSERT INTO clients (id, name, domain, status, plan, monthly_searches, search_limit, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                client['id'],
                client['name'],
                safe_get(client, 'domain', 'demo.com'),
                safe_get(client, 'status', 'active'),
                safe_get(client, 'plan', 'professional'),
                safe_get(client, 'monthly_searches', 0),
                safe_get(client, 'search_limit', 5000),
                to_datetime(safe_get(client, 'created_at')) or datetime.utcnow(),
                to_datetime(safe_get(client, 'updated_at')) or datetime.utcnow())

                clients_count += 1
                print(f"  ✅ Cliente: {client['name']}")
            except Exception as e:
                print(f"  ❌ Error cliente {client['name']}: {e}")

        # 5. Migrar USERS
        print(f"\n📤 MIGRANDO USERS...")
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        users_count = 0

        for user in users:
            try:
                await pg_conn.execute("""
                    INSERT INTO users (id, email, password_hash, full_name, role, client_id, is_active, last_login, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                user['id'],
                user['email'],
                user['password_hash'],
                safe_get(user, 'full_name', 'Usuario'),
                safe_get(user, 'role', 'super_admin'),
                user['client_id'],
                to_bool(safe_get(user, 'is_active', 1)),
                to_datetime(safe_get(user, 'last_login')),
                to_datetime(safe_get(user, 'created_at')) or datetime.utcnow(),
                to_datetime(safe_get(user, 'updated_at')) or datetime.utcnow())

                users_count += 1
                print(f"  ✅ Usuario: {user['email']}")
            except Exception as e:
                print(f"  ❌ Error usuario {user['email']}: {e}")

        # 6. Migrar API_KEYS
        print(f"\n📤 MIGRANDO API_KEYS...")
        try:
            cursor.execute("SELECT * FROM api_keys")
            api_keys = cursor.fetchall()
            api_keys_count = 0

            for key in api_keys:
                try:
                    await pg_conn.execute("""
                        INSERT INTO api_keys (id, client_id, key_name, api_key, is_active, requests_made, rate_limit, created_at, last_used)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    key['id'],
                    key['client_id'],
                    safe_get(key, 'key_name', 'API Key'),
                    key['api_key'],
                    to_bool(safe_get(key, 'is_active', 1)),
                    safe_get(key, 'requests_made', 0),
                    safe_get(key, 'rate_limit', 1000),
                    to_datetime(safe_get(key, 'created_at')) or datetime.utcnow(),
                    to_datetime(safe_get(key, 'last_used')))

                    api_keys_count += 1
                    print(f"  ✅ API Key: {key['api_key'][:20]}...")
                except Exception as e:
                    print(f"  ❌ Error API key: {e}")
        except Exception as e:
            print(f"  ⚠️  Tabla api_keys no existe: {e}")
            api_keys_count = 0

        # 7. Migrar CATEGORIES
        print(f"\n📤 MIGRANDO CATEGORIES...")
        cursor.execute("SELECT * FROM categories")
        categories = cursor.fetchall()
        categories_count = 0

        for cat in categories:
            try:
                slug = safe_get(cat, 'slug', cat['name'].lower().replace(' ', '-').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n').replace('–', '-'))

                await pg_conn.execute("""
                    INSERT INTO categories (id, client_id, name, description, slug, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                cat['id'],
                cat['client_id'],
                cat['name'],
                safe_get(cat, 'description', ''),
                slug,
                to_bool(safe_get(cat, 'is_active', 1)),
                to_datetime(safe_get(cat, 'created_at')) or datetime.utcnow(),
                to_datetime(safe_get(cat, 'updated_at')) or datetime.utcnow())

                categories_count += 1
                print(f"  ✅ Categoría: {cat['name']}")
            except Exception as e:
                print(f"  ❌ Error categoría {cat['name']}: {e}")

        # 8. Migrar PRODUCTS
        print(f"\n📤 MIGRANDO PRODUCTS...")
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall()
        products_count = 0

        for prod in products:
            try:
                price_val = safe_get(prod, 'price')
                price = float(price_val) if price_val is not None else None

                await pg_conn.execute("""
                    INSERT INTO products (id, client_id, category_id, name, description, price, sku, brand, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                prod['id'],
                prod['client_id'],
                safe_get(prod, 'category_id'),
                prod['name'],
                safe_get(prod, 'description', ''),
                price,
                safe_get(prod, 'sku', ''),
                safe_get(prod, 'brand', ''),
                to_bool(safe_get(prod, 'is_active', 1)),
                to_datetime(safe_get(prod, 'created_at')) or datetime.utcnow(),
                to_datetime(safe_get(prod, 'updated_at')) or datetime.utcnow())

                products_count += 1
                print(f"  ✅ Producto: {prod['name']}")
            except Exception as e:
                print(f"  ❌ Error producto {prod['name']}: {e}")

        # 9. Migrar IMAGES
        print(f"\n📤 MIGRANDO IMAGES...")
        cursor.execute("SELECT * FROM images")
        images = cursor.fetchall()
        images_count = 0

        for img in images:
            try:
                file_size = safe_get(img, 'file_size')
                file_size = int(file_size) if file_size is not None else None

                width = safe_get(img, 'width')
                width = int(width) if width is not None else None

                height = safe_get(img, 'height')
                height = int(height) if height is not None else None

                await pg_conn.execute("""
                    INSERT INTO images (id, client_id, product_id, filename, cloudinary_url, cloudinary_public_id,
                                      original_url, file_size, width, height, format, is_primary, uploaded_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                img['id'],
                img['client_id'],
                safe_get(img, 'product_id'),
                img['filename'],
                safe_get(img, 'cloudinary_url', ''),
                safe_get(img, 'cloudinary_public_id', ''),
                safe_get(img, 'original_url', ''),
                file_size,
                width,
                height,
                safe_get(img, 'format', ''),
                to_bool(safe_get(img, 'is_primary', 0)),
                to_datetime(safe_get(img, 'uploaded_at')) or datetime.utcnow())

                images_count += 1
                print(f"  ✅ Imagen: {img['filename']}")
            except Exception as e:
                print(f"  ❌ Error imagen {img['filename']}: {e}")

        # 10. Verificación final
        print(f"\n🔍 VERIFICACIÓN FINAL:")
        print("=" * 50)

        # Contar registros finales
        final_clients = await pg_conn.fetchval("SELECT COUNT(*) FROM clients")
        final_users = await pg_conn.fetchval("SELECT COUNT(*) FROM users")
        final_api_keys = await pg_conn.fetchval("SELECT COUNT(*) FROM api_keys")
        final_categories = await pg_conn.fetchval("SELECT COUNT(*) FROM categories")
        final_products = await pg_conn.fetchval("SELECT COUNT(*) FROM products")
        final_images = await pg_conn.fetchval("SELECT COUNT(*) FROM images")
        final_embeddings = await pg_conn.fetchval("SELECT COUNT(*) FROM image_embeddings")

        total_migrated = final_clients + final_users + final_api_keys + final_categories + final_products + final_images

        print(f"  ✅ clients:           {final_clients:3} registros")
        print(f"  ✅ users:             {final_users:3} registros")
        print(f"  ✅ api_keys:          {final_api_keys:3} registros")
        print(f"  ✅ categories:        {final_categories:3} registros")
        print(f"  ✅ products:          {final_products:3} registros")
        print(f"  ✅ images:            {final_images:3} registros")
        print(f"  ⏳ image_embeddings:  {final_embeddings:3} registros (se generarán)")

        print(f"\n🎉 MIGRACIÓN COMPLETA: {total_migrated} registros migrados")

        # 11. Mostrar datos migrados
        print(f"\n📋 MUESTRA DE DATOS MIGRADOS:")
        print("=" * 50)

        # Usuario principal
        admin_user = await pg_conn.fetchrow("SELECT email, role FROM users WHERE email LIKE '%admin%' LIMIT 1")
        if admin_user:
            print(f"🔑 Usuario admin: {admin_user['email']} ({admin_user['role']})")

        # Categorías reales
        categories = await pg_conn.fetch("SELECT name, description FROM categories LIMIT 5")
        print(f"\n📂 Categorías ({len(categories)} de {final_categories}):")
        for cat in categories:
            print(f"  - {cat['name']}: {cat['description'] or 'Sin descripción'}")

        # Productos reales
        products = await pg_conn.fetch("SELECT name, price, brand FROM products LIMIT 5")
        print(f"\n🛍️  Productos ({len(products)} de {final_products}):")
        for prod in products:
            print(f"  - {prod['name']} | ${prod['price'] or 'N/A'} | {prod['brand'] or 'Sin marca'}")

        # Imágenes reales
        images = await pg_conn.fetch("SELECT filename, cloudinary_url FROM images LIMIT 5")
        print(f"\n🖼️  Imágenes ({len(images)} de {final_images}):")
        for img in images:
            url = img['cloudinary_url'][:50] + "..." if img['cloudinary_url'] and len(img['cloudinary_url']) > 50 else img['cloudinary_url'] or 'Sin URL'
            print(f"  - {img['filename']} | {url}")

        print(f"\n✨ ¡MIGRACIÓN EXITOSA!")
        print(f"📝 Los embeddings se generarán automáticamente cuando uses el sistema")
        print(f"🔗 Usuario: admin@demo.com | Password: demo123")

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
    success = asyncio.run(migrate_all_data_no_embeddings())
    if success:
        print("\n🎯 SISTEMA LISTO PARA FUNCIONAR EN RAILWAY")
        print("🚀 Los embeddings se crearán automáticamente al usar la búsqueda")
    else:
        print("\n💥 Error en la migración")
