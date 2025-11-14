"""
Script para crear/actualizar usuario admin en Railway
Usa Werkzeug para hashear contraseñas correctamente
"""
import os
import sys
from werkzeug.security import generate_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

# URL de Railway (desde variables de entorno o hardcoded)
RAILWAY_DATABASE_URL = os.getenv(
    "RAILWAY_DATABASE_URL",
    "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"
)

def create_or_update_admin(email="admin@demo.com", password="demo123", full_name="Admin Demo", client_email=None):
    """Crear o actualizar usuario admin con hash correcto"""

    print(f"🔐 Conectando a Railway PostgreSQL...")
    print(f"📧 Email: {email}")
    print(f"🔑 Password: {password}")

    try:
        # Conectar a Railway
        conn = psycopg2.connect(RAILWAY_DATABASE_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Generar hash con Werkzeug (igual que Flask)
        password_hash = generate_password_hash(password)
        print(f"🔒 Hash generado: {password_hash[:50]}...")

        # Buscar cliente (por email si se proporciona, sino el primero)
        if client_email:
            cursor.execute("SELECT id, name, slug FROM clients WHERE email = %s LIMIT 1", (client_email,))
            client = cursor.fetchone()
            if not client:
                print(f"❌ Error: No existe cliente con email '{client_email}'")
                return False
        else:
            # Verificar si existe algún cliente (usar el primero disponible)
            cursor.execute("SELECT id, name, slug FROM clients ORDER BY created_at LIMIT 1")
            client = cursor.fetchone()
            if not client:
                print("❌ Error: No existe ningún cliente en Railway")
                print("   Debes crear al menos un cliente primero")
                return False

        client_id = client['id']
        print(f"✅ Cliente encontrado: {client['name']} ({client['slug']}) - {client_id}")

        # Verificar si usuario existe
        cursor.execute("SELECT id, email FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            # Actualizar usuario existente
            print(f"🔄 Actualizando usuario existente: {user['id']}")
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    full_name = %s,
                    role = 'SUPER_ADMIN',
                    is_active = true
                WHERE email = %s
                """,
                (password_hash, full_name, email)
            )
            print(f"✅ Usuario actualizado exitosamente")
        else:
            # Crear nuevo usuario
            print(f"➕ Creando nuevo usuario...")
            cursor.execute(
                """
                INSERT INTO users (email, password_hash, full_name, role, client_id, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (email, password_hash, full_name, "SUPER_ADMIN", client_id, True)
            )
            user_id = cursor.fetchone()['id']
            print(f"✅ Usuario creado exitosamente: {user_id}")

        # Commit cambios
        conn.commit()

        print("\n" + "="*60)
        print("🎉 ¡USUARIO ADMIN CONFIGURADO CORRECTAMENTE!")
        print("="*60)
        print(f"📧 Email:    {email}")
        print(f"🔑 Password: {password}")
        print(f"🌐 Railway:  https://clipcomparadorv2-production.up.railway.app/auth/login")
        print("="*60)

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Permitir pasar email y password como argumentos
    # Uso: python create_railway_admin.py <user_email> <password> <full_name> [client_email]
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@demo.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "demo123"
    full_name = sys.argv[3] if len(sys.argv) > 3 else "Admin Demo"
    client_email = sys.argv[4] if len(sys.argv) > 4 else None

    success = create_or_update_admin(email, password, full_name, client_email)
    sys.exit(0 if success else 1)
