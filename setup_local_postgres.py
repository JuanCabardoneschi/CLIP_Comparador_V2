"""
Script para inicializar la base de datos PostgreSQL local
Crea todas las tablas y datos de ejemplo
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

# Configurar para usar PostgreSQL local
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/clip_comparador_v2')
os.environ.setdefault('SECRET_KEY', 'dev-secret-key-change-in-production')

from clip_admin_backend.app import create_app, db
from clip_admin_backend.app.models.client import Client
from clip_admin_backend.app.models.user import User

def init_database():
    """Inicializar base de datos con estructura y datos de ejemplo"""

    app = create_app()

    with app.app_context():
        print("🔄 Eliminando tablas existentes...")
        db.drop_all()

        print("🔨 Creando estructura de tablas...")
        db.create_all()

        print("👤 Creando usuario administrador...")
        admin = User(
            username='admin',
            email='admin@sistema.com',
            is_super_admin=True
        )
        admin.set_password('admin123')  # Cambiar en producción
        db.session.add(admin)

        print("🏢 Creando cliente de ejemplo...")
        demo_client = Client(
            name='Demo Fashion Store',
            email='demo@fashion.com',
            description='Tienda de demostración para pruebas',
            industry='fashion',
            category_confidence_threshold=70,
            product_similarity_threshold=30
        )
        db.session.add(demo_client)

        # Crear usuario vinculado al cliente demo
        demo_user = User(
            username='demo',
            email='demo@fashion.com',
            is_super_admin=False,
            client=demo_client
        )
        demo_user.set_password('demo123')
        db.session.add(demo_user)

        print("💾 Guardando cambios...")
        db.session.commit()

        print("\n✅ Base de datos inicializada correctamente!")
        print("\n📋 Credenciales de acceso:")
        print("   Super Admin:")
        print("   - Usuario: admin")
        print("   - Password: admin123")
        print("\n   Cliente Demo:")
        print("   - Usuario: demo")
        print("   - Password: demo123")
        print(f"\n🔑 API Key del cliente demo: {demo_client.api_key}")
        print(f"\n🆔 ID del cliente demo: {demo_client.id}")

        return True

if __name__ == '__main__':
    print("🚀 Inicializando base de datos PostgreSQL local...\n")

    # Verificar que DATABASE_URL esté configurada
    db_url = os.environ.get('DATABASE_URL')
    print(f"📍 Database URL: {db_url}\n")

    if not db_url or 'postgresql' not in db_url:
        print("⚠️  ADVERTENCIA: DATABASE_URL no apunta a PostgreSQL")
        print("    Configura la variable de entorno:")
        print('    $env:DATABASE_URL="postgresql://postgres:tu_password@localhost:5432/clip_comparador_v2"')
        response = input("\n¿Continuar de todas formas? (s/n): ")
        if response.lower() != 's':
            print("❌ Operación cancelada")
            sys.exit(1)

    try:
        init_database()
    except Exception as e:
        print(f"\n❌ Error al inicializar la base de datos:")
        print(f"   {str(e)}")
        print("\n💡 Posibles soluciones:")
        print("   1. Verifica que PostgreSQL esté corriendo")
        print("   2. Verifica que la base de datos 'clip_comparador_v2' exista")
        print("   3. Verifica las credenciales en DATABASE_URL")
        print("   4. Ejecuta: psql -U postgres -c 'CREATE DATABASE clip_comparador_v2;'")
        sys.exit(1)
