"""
Script de inicialización de base de datos
Crear tablas y datos iniciales para el sistema V2
"""

import asyncio
import hashlib
import json
import os
import secrets
import sys
from datetime import datetime

import asyncpg

# Agregar path para importar modelos
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))


async def create_extensions(conn):
    """Crear extensiones necesarias"""
    print("🔧 Creando extensiones PostgreSQL...")

    extensions = [
        'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";',
        "CREATE EXTENSION IF NOT EXISTS vector;",  # pgvector para embeddings
    ]

    for ext_sql in extensions:
        try:
            await conn.execute(ext_sql)
        except Exception as e:
            print(f"⚠️ Error creando extensión: {e}")


async def create_tables(conn):
    """Crear todas las tablas del sistema"""

    print("📝 Creando tablas...")

    # Tabla de clientes
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT true,
            api_settings JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    )
    print("✅ Tabla clients creada")

    # Tabla de usuarios
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
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
        );
    """
    )
    print("✅ Tabla users creada")

    # Tabla de API keys
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            key_hash VARCHAR(255) UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT true,
            rate_limit_per_hour INTEGER DEFAULT 1000,
            allowed_ips JSONB,
            last_used_at TIMESTAMP,
            usage_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        );
    """
    )
    print("✅ Tabla api_keys creada")

    # Tabla de categorías
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) NOT NULL,
            description TEXT,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(client_id, slug)
        );
    """
    )
    print("✅ Tabla categories creada")

    # Tabla de productos
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) NOT NULL,
            description TEXT,
            price DECIMAL(10,2),
            sku VARCHAR(100),
            is_active BOOLEAN DEFAULT true,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(client_id, slug)
        );
    """
    )
    print("✅ Tabla products creada")

    # Tabla de imágenes de productos
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS product_images (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            cloudinary_url VARCHAR(500) NOT NULL,
            cloudinary_public_id VARCHAR(255) NOT NULL,
            alt_text VARCHAR(255),
            is_primary BOOLEAN DEFAULT false,
            file_size INTEGER,
            dimensions JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    )
    print("✅ Tabla product_images creada")

    # Tabla de embeddings de imágenes
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS image_embeddings (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            image_id UUID NOT NULL REFERENCES product_images(id) ON DELETE CASCADE,
            embedding vector(512),
            model_version VARCHAR(50) DEFAULT 'ViT-B/16',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    )
    print("✅ Tabla image_embeddings creada")

    # Tabla de logs de búsqueda
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS search_logs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            user_ip VARCHAR(45),
            results_count INTEGER DEFAULT 0,
            query_time_ms FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    )
    print("✅ Tabla search_logs creada")


async def create_indexes(conn):
    """Crear índices para optimización"""

    print("📊 Creando índices...")

    indexes = [
        # Índices básicos
        "CREATE INDEX IF NOT EXISTS idx_clients_slug ON clients(slug);",
        "CREATE INDEX IF NOT EXISTS idx_clients_active ON clients(is_active);",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
        "CREATE INDEX IF NOT EXISTS idx_users_client ON users(client_id);",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_client ON api_keys(client_id);",
        "CREATE INDEX IF NOT EXISTS idx_categories_client ON categories(client_id);",
        "CREATE INDEX IF NOT EXISTS idx_categories_slug ON categories(client_id, slug);",
        "CREATE INDEX IF NOT EXISTS idx_products_client ON products(client_id);",
        "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);",
        "CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);",
        "CREATE INDEX IF NOT EXISTS idx_products_slug ON products(client_id, slug);",
        "CREATE INDEX IF NOT EXISTS idx_product_images_product ON product_images(product_id);",
        "CREATE INDEX IF NOT EXISTS idx_product_images_primary ON product_images(is_primary);",
        "CREATE INDEX IF NOT EXISTS idx_image_embeddings_image ON image_embeddings(image_id);",
        "CREATE INDEX IF NOT EXISTS idx_search_logs_client ON search_logs(client_id);",
        "CREATE INDEX IF NOT EXISTS idx_search_logs_date ON search_logs(created_at);",
    ]

    for index_sql in indexes:
        try:
            await conn.execute(index_sql)
        except Exception as e:
            print(f"⚠️ Error creando índice: {e}")

    # Índice vectorial especializado (requiere más configuración)
    try:
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_embeddings_vector
            ON image_embeddings
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """
        )
        print("✅ Índice vectorial creado")
    except Exception as e:
        print(f"⚠️ Error creando índice vectorial: {e}")
        print("   Esto es normal si no hay datos aún en la tabla")


async def create_demo_data(conn):
    """Crear datos de demostración"""

    print("🎭 Creando datos de demostración...")

    # Cliente demo
    client_id = await conn.fetchval(
        """
        INSERT INTO clients (name, slug, email, api_settings)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
    """,
        "DEMO Fashion Store",
        "demo-fashion",
        "demo@fashionstore.com",
        json.dumps({"max_products": 1000, "max_categories": 50}),
    )

    print(f"✅ Cliente demo creado: {client_id}")

    # Usuario admin demo
    password_hash = hashlib.sha256("demo123".encode()).hexdigest()
    user_id = await conn.fetchval(
        """
        INSERT INTO users (email, password_hash, full_name, role, client_id)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name
        RETURNING id
    """,
        "admin@demo.com",
        password_hash,
        "Admin Demo",
        "super_admin",
        client_id,
    )

    print(f"✅ Usuario demo creado: admin@demo.com")

    # API Key demo
    api_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    await conn.execute(
        """
        INSERT INTO api_keys (client_id, name, key_hash, rate_limit_per_hour)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (key_hash) DO NOTHING
    """,
        client_id,
        "API Key Demo",
        key_hash,
        1000,
    )

    print(f"🔑 API Key demo: {api_key}")

    # Categorías demo
    categories = [
        ("Camisas", "camisas", "Camisas y blusas de vestir"),
        ("Pantalones", "pantalones", "Pantalones y jeans"),
        ("Casacas", "casacas", "Casacas y chaquetas"),
        ("Delantales", "delantales", "Delantales profesionales"),
    ]

    for name, slug, desc in categories:
        cat_id = await conn.fetchval(
            """
            INSERT INTO categories (client_id, name, slug, description)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (client_id, slug) DO UPDATE SET description = EXCLUDED.description
            RETURNING id
        """,
            client_id,
            name,
            slug,
            desc,
        )
        print(f"✅ Categoría creada: {name}")

    print("\n🎉 Datos de demostración creados exitosamente!")
    print(f"👤 Usuario: admin@demo.com / demo123")
    print(f"🔑 API Key: {api_key}")
    print(f"🏢 Cliente: demo-fashion ({client_id})")


async def initialize_database():
    """Función principal de inicialización"""

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL no está configurada")
        print("   Configura la variable de entorno DATABASE_URL")
        return False

    try:
        print("🚀 Inicializando base de datos CLIP Comparador V2...")
        print(
            f"🔗 Conectando a: {database_url.split('@')[1] if '@' in database_url else 'database'}"
        )

        # Conectar a PostgreSQL
        conn = await asyncpg.connect(database_url)
        print("✅ Conexión establecida")

        # Crear extensiones
        await create_extensions(conn)

        # Crear tablas
        await create_tables(conn)

        # Crear índices
        await create_indexes(conn)

        # Crear datos demo
        await create_demo_data(conn)

        await conn.close()
        print("\n🎉 Base de datos inicializada exitosamente!")
        print("\n📋 Próximos pasos:")
        print("1. Configurar variables de entorno (.env)")
        print("2. Instalar dependencias: pip install -r requirements.txt")
        print(
            "3. Ejecutar Backend Admin: cd clip_admin_backend && python app.py"
        )
        print("4. Ejecutar Search API: cd clip_search_api && python main.py")

        return True

    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        print(f"   Tipo de error: {type(e).__name__}")
        return False


if __name__ == "__main__":
    # Cargar variables de entorno
    from dotenv import load_dotenv

    load_dotenv()

    # Ejecutar inicialización
    success = asyncio.run(initialize_database())
    sys.exit(0 if success else 1)
