#!/usr/bin/env python3
"""
Script completo para verificar y recrear estructura PostgreSQL en Railway
con todos los datos necesarios para funcionar
"""
import asyncio
import asyncpg
import hashlib
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# URL de Railway PostgreSQL (directa)
DATABASE_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def check_and_fix_database():
    """Verifica y corrige la estructura completa de la base de datos"""

    print("🔍 INICIANDO VERIFICACIÓN Y CORRECCIÓN DE BASE DE DATOS RAILWAY")
    print("=" * 70)

    # Conectar a PostgreSQL
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Conexión a Railway PostgreSQL exitosa")
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        return False

    try:
        # 1. Habilitar extensión UUID
        print("\n📦 Habilitando extensión uuid-ossp...")
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
        print("✅ Extensión uuid-ossp habilitada")

        # 2. Verificar estructura de tabla users
        print("\n🔍 Verificando estructura tabla USERS...")
        users_columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'users'
            ORDER BY ordinal_position
        """)

        print("Columnas existentes en users:")
        for col in users_columns:
            print(f"  - {col['column_name']:15} | {col['data_type']:12} | NULL: {col['is_nullable']}")

        # 3. Verificar si falta full_name
        has_full_name = any(col['column_name'] == 'full_name' for col in users_columns)

        if not has_full_name:
            print("\n⚠️  PROBLEMA DETECTADO: Columna 'full_name' no existe")
            print("🔧 Agregando columna full_name...")
            await conn.execute("ALTER TABLE users ADD COLUMN full_name VARCHAR(255)")
            print("✅ Columna full_name agregada")
        else:
            print("✅ Columna full_name ya existe")

        # 4. Recrear todas las tablas si es necesario
        print("\n🏗️  RECREANDO ESTRUCTURA COMPLETA...")

        # Drop y recrear tablas en orden correcto
        await conn.execute("DROP TABLE IF EXISTS image_embeddings CASCADE")
        await conn.execute("DROP TABLE IF EXISTS images CASCADE")
        await conn.execute("DROP TABLE IF EXISTS products CASCADE")
        await conn.execute("DROP TABLE IF EXISTS categories CASCADE")
        await conn.execute("DROP TABLE IF EXISTS api_keys CASCADE")
        await conn.execute("DROP TABLE IF EXISTS users CASCADE")
        await conn.execute("DROP TABLE IF EXISTS clients CASCADE")

        print("🗑️  Tablas anteriores eliminadas")

        # Crear tabla clients
        await conn.execute("""
            CREATE TABLE clients (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                name VARCHAR(255) NOT NULL,
                domain VARCHAR(255),
                status VARCHAR(50) DEFAULT 'active',
                plan VARCHAR(50) DEFAULT 'starter',
                monthly_searches INTEGER DEFAULT 0,
                search_limit INTEGER DEFAULT 1000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Crear tabla users
        await conn.execute("""
            CREATE TABLE users (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                role VARCHAR(50) DEFAULT 'client_admin',
                client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
                is_active BOOLEAN DEFAULT true,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Crear tabla api_keys
        await conn.execute("""
            CREATE TABLE api_keys (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
                key_name VARCHAR(255) NOT NULL,
                api_key VARCHAR(255) UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT true,
                requests_made INTEGER DEFAULT 0,
                rate_limit INTEGER DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP
            )
        """)

        # Crear tabla categories
        await conn.execute("""
            CREATE TABLE categories (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                slug VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(client_id, slug)
            )
        """)

        # Crear tabla products
        await conn.execute("""
            CREATE TABLE products (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
                category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price DECIMAL(10,2),
                sku VARCHAR(255),
                brand VARCHAR(255),
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Crear tabla images
        await conn.execute("""
            CREATE TABLE images (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
                product_id UUID REFERENCES products(id) ON DELETE CASCADE,
                filename VARCHAR(255) NOT NULL,
                cloudinary_url TEXT,
                cloudinary_public_id VARCHAR(255),
                original_url TEXT,
                file_size INTEGER,
                width INTEGER,
                height INTEGER,
                format VARCHAR(50),
                is_primary BOOLEAN DEFAULT false,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Crear tabla image_embeddings
        await conn.execute("""
            CREATE TABLE image_embeddings (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                image_id UUID REFERENCES images(id) ON DELETE CASCADE,
                embedding_vector FLOAT8[],
                model_version VARCHAR(50) DEFAULT 'ViT-B/16',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(image_id)
            )
        """)

        print("✅ Todas las tablas creadas exitosamente")

        # 5. Insertar datos demo
        print("\n📊 INSERTANDO DATOS DEMO...")

        # Cliente demo
        client_id = await conn.fetchval("""
            INSERT INTO clients (name, domain, status, plan, search_limit)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, "Tienda Demo", "demo.com", "active", "professional", 5000)

        print(f"✅ Cliente demo creado: {client_id}")

        # Usuario admin demo
        password_hash = hashlib.sha256("demo123".encode()).hexdigest()
        user_id = await conn.fetchval("""
            INSERT INTO users (email, password_hash, full_name, role, client_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, "admin@demo.com", password_hash, "Admin Demo", "super_admin", client_id)

        print(f"✅ Usuario admin creado: admin@demo.com (password: demo123)")

        # API Key demo
        api_key = f"demo_api_key_{str(uuid.uuid4())[:8]}"
        await conn.execute("""
            INSERT INTO api_keys (client_id, key_name, api_key, rate_limit)
            VALUES ($1, $2, $3, $4)
        """, client_id, "Demo API Key", api_key, 1000)

        print(f"✅ API Key creada: {api_key}")

        # Categorías demo
        categories_data = [
            ("Moda", "Ropa y accesorios", "moda"),
            ("Electrónicos", "Dispositivos electrónicos", "electronicos"),
            ("Hogar", "Artículos para el hogar", "hogar"),
            ("Deportes", "Artículos deportivos", "deportes")
        ]

        category_ids = []
        for name, desc, slug in categories_data:
            cat_id = await conn.fetchval("""
                INSERT INTO categories (client_id, name, description, slug)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, client_id, name, desc, slug)
            category_ids.append(cat_id)
            print(f"✅ Categoría creada: {name}")

        # Productos demo
        products_data = [
            ("Camiseta Básica", "Camiseta de algodón básica", 19.99, "CAM001", "BasicWear"),
            ("Jeans Clásico", "Jeans de corte clásico", 49.99, "JEA001", "DenimCo"),
            ("Zapatillas Deportivas", "Zapatillas para correr", 89.99, "ZAP001", "SportMax")
        ]

        for i, (name, desc, price, sku, brand) in enumerate(products_data):
            product_id = await conn.fetchval("""
                INSERT INTO products (client_id, category_id, name, description, price, sku, brand)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """, client_id, category_ids[i % len(category_ids)], name, desc, price, sku, brand)
            print(f"✅ Producto creado: {name}")

        # 6. Verificación final
        print("\n🔍 VERIFICACIÓN FINAL...")

        # Contar registros
        clients_count = await conn.fetchval("SELECT COUNT(*) FROM clients")
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        categories_count = await conn.fetchval("SELECT COUNT(*) FROM categories")
        products_count = await conn.fetchval("SELECT COUNT(*) FROM products")

        print(f"📊 Registros creados:")
        print(f"  - Clientes: {clients_count}")
        print(f"  - Usuarios: {users_count}")
        print(f"  - Categorías: {categories_count}")
        print(f"  - Productos: {products_count}")

        # Verificar estructura users final
        print("\n🔍 Verificando estructura final tabla USERS:")
        final_users_columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'users'
            ORDER BY ordinal_position
        """)

        for col in final_users_columns:
            print(f"  ✅ {col['column_name']:15} | {col['data_type']}")

        print("\n🎉 BASE DE DATOS RAILWAY COMPLETAMENTE CONFIGURADA")
        print("📧 Usuario demo: admin@demo.com")
        print("🔑 Contraseña: demo123")
        print(f"🔗 API Key: {api_key}")

        return True

    except Exception as e:
        print(f"❌ Error durante la configuración: {e}")
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    success = asyncio.run(check_and_fix_database())
    if success:
        print("\n✅ Script ejecutado exitosamente")
    else:
        print("\n❌ Error en la ejecución del script")
