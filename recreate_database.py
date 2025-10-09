#!/usr/bin/env python3
"""
Script para recrear la estructura de base de datos y usuarios básicos
CLIP Comparador V2 - Recuperación de Base de Datos
"""

import os
import sys
import sqlite3
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash

def recreate_database():
    """Recrear estructura de base de datos y usuarios básicos"""

    print("🔄 INICIANDO RECREACIÓN DE BASE DE DATOS...")
    print("=" * 50)

    # Ruta de la base de datos
    db_path = os.path.join(os.path.dirname(__file__), 'clip_admin_backend', 'instance', 'clip_comparador_v2.db')

    # Eliminar base de datos existente
    if os.path.exists(db_path):
        print("🗑️ Eliminando base de datos existente...")
        os.remove(db_path)

    # Crear directorio instance si no existe
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Conectar a la nueva base de datos
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print("🏗️ Creando estructura de tablas...")

    # Crear tabla clients
    cur.execute('''
        CREATE TABLE clients (
            id TEXT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            industry VARCHAR(100),
            api_key VARCHAR(100) UNIQUE,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Crear tabla users
    cur.execute('''
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            role VARCHAR(50) DEFAULT 'STORE_ADMIN',
            is_active BOOLEAN DEFAULT 1,
            last_login DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')

    # Crear tabla categories
    cur.execute('''
        CREATE TABLE categories (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            name VARCHAR(100) NOT NULL,
            name_en VARCHAR(100) NOT NULL,
            alternative_terms TEXT,
            description TEXT,
            clip_prompt TEXT,
            visual_features TEXT,
            confidence_threshold REAL DEFAULT 0.75,
            color VARCHAR(7) DEFAULT '#007bff',
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')

    # Crear tabla products
    cur.execute('''
        CREATE TABLE products (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            category_id TEXT,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            brand VARCHAR(100),
            sku VARCHAR(100),
            price DECIMAL(10,2),
            stock INTEGER DEFAULT 0,
            color VARCHAR(50),
            tags TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id),
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')

    # Crear tabla images
    cur.execute('''
        CREATE TABLE images (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            product_id TEXT,
            filename VARCHAR(255) NOT NULL,
            original_filename VARCHAR(255),
            cloudinary_url TEXT,
            cloudinary_public_id TEXT,
            width INTEGER,
            height INTEGER,
            file_size INTEGER,
            mime_type VARCHAR(100),
            alt_text VARCHAR(255),
            is_primary BOOLEAN DEFAULT 0,
            is_processed BOOLEAN DEFAULT 0,
            clip_embedding TEXT,
            upload_status VARCHAR(50) DEFAULT 'pending',
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')

    # Crear tabla api_keys
    cur.execute('''
        CREATE TABLE api_keys (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            name VARCHAR(255) NOT NULL,
            key_hash VARCHAR(255) UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            rate_limit_per_hour INTEGER DEFAULT 1000,
            last_used_at DATETIME,
            usage_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')

    print("✅ Estructura de tablas creada exitosamente!")
    print()

    # Generar IDs únicos
    demo_client_id = str(uuid.uuid4())
    super_admin_id = str(uuid.uuid4())
    store_admin_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Crear cliente demo
    print("🏪 Creando cliente Demo Fashion Store...")
    cur.execute('''
        INSERT INTO clients (id, name, slug, email, description, industry, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (demo_client_id, "Demo Fashion Store", "demo_fashion_store", "admin@demo.com",
          "Tienda de moda y textiles para demostración", "textil", True, now, now))

    print(f"   ✅ Cliente creado con ID: {demo_client_id}")
    print()

    # Crear SUPER ADMIN
    print("👑 Creando SUPER ADMIN...")
    super_admin_password = generate_password_hash("Laurana@01")
    cur.execute('''
        INSERT INTO users (id, client_id, email, password_hash, full_name, role, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (super_admin_id, None, "clipadmin@sistema.com", super_admin_password,
          "CLIP System Administrator", "SUPER_ADMIN", True, now, now))

    print("   ✅ SUPER ADMIN creado:")
    print("   📧 Email: clipadmin@sistema.com")
    print("   🔑 Password: Laurana@01")
    print("   🎭 Role: SUPER_ADMIN")
    print("   🏢 Cliente: TODOS (sin restricción)")
    print()

    # Crear STORE ADMIN
    print("🏪 Creando STORE ADMIN...")
    store_admin_password = generate_password_hash("admin123")
    cur.execute('''
        INSERT INTO users (id, client_id, email, password_hash, full_name, role, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (store_admin_id, demo_client_id, "admin@demo.com", store_admin_password,
          "Demo Store Administrator", "STORE_ADMIN", True, now, now))

    print("   ✅ STORE ADMIN creado:")
    print("   📧 Email: admin@demo.com")
    print("   🔑 Password: admin123")
    print("   🎭 Role: STORE_ADMIN")
    print("   🏢 Cliente: Demo Fashion Store")
    print()

    # Confirmar cambios
    print("💾 Guardando cambios en base de datos...")
    conn.commit()

    # Verificar resultado
    print("🔍 VERIFICACIÓN FINAL:")
    clients_count = cur.execute('SELECT COUNT(*) FROM clients').fetchone()[0]
    users_count = cur.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    print(f"📊 Clientes: {clients_count}")
    print(f"👥 Usuarios: {users_count}")

    conn.close()

    print("✅ BASE DE DATOS RECREADA EXITOSAMENTE!")
    print("=" * 50)
    print()
    print("🌐 ACCESO AL SISTEMA:")
    print("URL: http://localhost:5000")
    print()
    print("👑 SUPER ADMIN:")
    print("   Email: clipadmin@sistema.com")
    print("   Password: Laurana@01")
    print("   Permisos: Ve TODOS los clientes y datos")
    print()
    print("🏪 STORE ADMIN:")
    print("   Email: admin@demo.com")
    print("   Password: admin123")
    print("   Cliente: Demo Fashion Store (textil)")
    print("   Permisos: Solo ve SU catálogo y datos")
    print()
    print("🎉 ¡Sistema listo para usar!")


if __name__ == "__main__":
    try:
        recreate_database()
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
