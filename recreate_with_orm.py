#!/usr/bin/env python3
"""
Script para recrear la base de datos usando SQLAlchemy ORM
Esto asegura que TODOS los modelos se creen correctamente
"""

import os
import sys
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash

# Configurar Flask y la app
sys.path.append(os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from clip_admin_backend.app import create_app, db
from clip_admin_backend.app.models import Client, User, Category, Product, Image, SearchLog

def recreate_database():
    """Recrear base de datos con SQLAlchemy ORM"""

    print("🔄 INICIANDO RECREACIÓN DE BASE DE DATOS CON ORM...")
    print("=" * 60)

    # Crear app
    app = create_app()

    with app.app_context():
        # Ruta de la base de datos
        db_path = os.path.join(app.instance_path, 'clip_comparador_v2.db')

        # Eliminar base de datos existente
        if os.path.exists(db_path):
            print("🗑️ Eliminando base de datos existente...")
            os.remove(db_path)

        # Crear todas las tablas usando SQLAlchemy
        print("🏗️ Creando estructura de tablas con SQLAlchemy...")
        db.create_all()
        print("✅ Estructura de tablas creada exitosamente!")

        # Crear cliente demo
        print("\n🏪 Creando cliente Demo Fashion Store...")
        demo_client = Client(
            name="Demo Fashion Store",
            slug="demo-fashion",
            email="demo@fashionstore.com",
            description="Tienda de moda demo para pruebas del sistema",
            industry="textil",
            api_key=f"demo_{uuid.uuid4().hex[:16]}"
        )
        db.session.add(demo_client)
        db.session.flush()  # Para obtener el ID
        print(f"   ✅ Cliente creado con ID: {demo_client.id}")

        # Crear SUPER ADMIN
        print("\n👑 Creando SUPER ADMIN...")
        super_admin = User(
            email="clipadmin@sistema.com",
            password_hash=generate_password_hash("Laurana@01"),
            first_name="CLIP",
            last_name="Admin",
            role="SUPER_ADMIN",
            client_id=None,  # Sin restricción de cliente
            is_active=True
        )
        db.session.add(super_admin)
        print("   ✅ SUPER ADMIN creado:")
        print("   📧 Email: clipadmin@sistema.com")
        print("   🔑 Password: Laurana@01")
        print("   🎭 Role: SUPER_ADMIN")
        print("   🏢 Cliente: TODOS (sin restricción)")

        # Crear STORE ADMIN
        print("\n🏪 Creando STORE ADMIN...")
        store_admin = User(
            email="admin@demo.com",
            password_hash=generate_password_hash("admin123"),
            first_name="Store",
            last_name="Admin",
            role="STORE_ADMIN",
            client_id=demo_client.id,
            is_active=True
        )
        db.session.add(store_admin)
        print("   ✅ STORE ADMIN creado:")
        print("   📧 Email: admin@demo.com")
        print("   🔑 Password: admin123")
        print("   🎭 Role: STORE_ADMIN")
        print("   🏢 Cliente: Demo Fashion Store")

        # Guardar cambios
        print("\n💾 Guardando cambios en base de datos...")
        db.session.commit()

        # Verificar creación
        print("\n🔍 VERIFICACIÓN FINAL:")
        clients_count = Client.query.count()
        users_count = User.query.count()
        print(f"📊 Clientes: {clients_count}")
        print(f"👥 Usuarios: {users_count}")

        print("\n✅ BASE DE DATOS RECREADA EXITOSAMENTE!")
        print("=" * 60)

        print("\n🌐 ACCESO AL SISTEMA:")
        print("URL: http://localhost:5000")
        print("\n👑 SUPER ADMIN:")
        print("   Email: clipadmin@sistema.com")
        print("   Password: Laurana@01")
        print("   Permisos: Ve TODOS los clientes y datos")
        print("\n🏪 STORE ADMIN:")
        print("   Email: admin@demo.com")
        print("   Password: admin123")
        print("   Cliente: Demo Fashion Store (textil)")
        print("   Permisos: Solo ve SU catálogo y datos")
        print("\n🎉 ¡Sistema listo para usar!")

if __name__ == "__main__":
    recreate_database()
