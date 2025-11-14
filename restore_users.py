"""
Script para restaurar los 3 usuarios originales del sistema
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Usuarios originales del backup
USERS = [
    {
        'id': '5e2b5086-38fd-455d-92ea-914aa16d9136',
        'email': 'clipadmin@sistema.com',
        'password_hash': 'scrypt:32768:8:1$jllt0b1r4dwQjLQZ$3f5a257e0a3b80f88375a6bcdb4adeabe543ac74d1bf1389148220d5dda731376b8bb4c52c408b34d66df1034315a22ba30f5e72defc8e40529629ca7004a896',
        'full_name': 'CLIP System Administrator',
        'role': 'SUPER_ADMIN',
        'client_id': None,
        'is_active': True
    },
    {
        'id': 'ef26feea-3df3-4b45-8e6e-f4bb3b9bccbd',
        'email': 'admin@demo.com',
        'password_hash': 'scrypt:32768:8:1$p79b5LtJhXOySpOf$5245049fae453db666353e312e09b73308546933e87c3f44944eaaaa370f53ffcecbcc35c2825bb1452ba115c3f90938beab4d3f693dc61e7bd6b8459a20672c',
        'full_name': 'Demo Store Administrator',
        'role': 'STORE_ADMIN',
        'client_id': '60231500-ca6f-4c46-a960-2e17298fcdb0',  # Goody Store
        'is_active': True
    },
    {
        'id': 'db4bbc41-b66b-4578-a852-37633875ef57',
        'email': 'esilvestre@redsis.com.ar',
        'password_hash': 'scrypt:32768:8:1$DO9SaVL4udqD6RHE$27685fd9973b004ad14c6f5534a7c3cf2d0e671339bbcd21bfd38c76665ec563753351027a6c1412c9833d8a242216a824506b5936658cc254e2a1e4235b5f4d',
        'full_name': 'Evelin Silvestre',
        'role': 'STORE_ADMIN',
        'client_id': '57fc482f-2776-4816-b231-57d3c57348de',  # Eve's Store
        'is_active': True
    }
]

def restore_users(db_url, db_name):
    """Restaurar usuarios en la base de datos especificada"""
    print(f"\n{'='*60}")
    print(f"🔄 RESTAURANDO USUARIOS EN: {db_name}")
    print(f"{'='*60}\n")

    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Eliminar usuarios actuales
        print("🗑️  Limpiando usuarios existentes...")
        cursor.execute("DELETE FROM users")
        deleted = cursor.rowcount
        print(f"   ✅ {deleted} usuarios eliminados\n")

        # Insertar usuarios originales
        for user in USERS:
            print(f"➕ Insertando usuario: {user['email']}")
            print(f"   Rol: {user['role']}")
            print(f"   Cliente: {user['client_id'] or 'N/A (System Admin)'}")

            cursor.execute(
                """
                INSERT INTO users (id, email, password_hash, full_name, role, client_id, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (
                    user['id'],
                    user['email'],
                    user['password_hash'],
                    user['full_name'],
                    user['role'],
                    user['client_id'],
                    user['is_active']
                )
            )
            print(f"   ✅ Usuario creado\n")

        # Commit
        conn.commit()

        # Verificar
        cursor.execute("SELECT email, role, full_name FROM users ORDER BY role DESC, email")
        users = cursor.fetchall()

        print(f"\n{'='*60}")
        print(f"✅ RESTAURACIÓN COMPLETADA - {db_name}")
        print(f"{'='*60}")
        print(f"\n📋 USUARIOS RESTAURADOS ({len(users)}):\n")

        for u in users:
            print(f"  📧 {u['email']}")
            print(f"     Nombre: {u['full_name']}")
            print(f"     Rol: {u['role']}")
            print()

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys

    # Determinar qué BD restaurar
    target = sys.argv[1] if len(sys.argv) > 1 else "both"

    if target in ["local", "both"]:
        LOCAL_URL = "postgresql://postgres:Laurana%4001@localhost:5432/clip_comparador_v2"
        restore_users(LOCAL_URL, "LOCAL")

    if target in ["railway", "both"]:
        RAILWAY_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"
        restore_users(RAILWAY_URL, "RAILWAY")

    print("\n" + "="*60)
    print("🎉 PROCESO COMPLETADO")
    print("="*60)
    print("\n📝 CREDENCIALES DE ACCESO:\n")
    print("1️⃣  SUPER ADMIN (Sistema completo):")
    print("    📧 clipadmin@sistema.com")
    print("    🔑 (password del backup - necesitas recuperarla)\n")
    print("2️⃣  ADMIN Goody Store:")
    print("    📧 admin@demo.com")
    print("    🔑 (password del backup - necesitas recuperarla)\n")
    print("3️⃣  ADMIN Eve's Store:")
    print("    📧 esilvestre@redsis.com.ar")
    print("    🔑 (password del backup - necesitas recuperarla)\n")
    print("="*60)
