"""
Script simple para crear super admin
"""
from werkzeug.security import generate_password_hash
import sqlite3
import uuid

# Conectar a la base de datos SQLite directamente
db_path = "C:/Personal/CLIP_Comparador_V2/clip_admin_backend/instance/clip_comparador_v2.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Verificar si ya existe
cursor.execute("SELECT email, role FROM users WHERE email = ?", ('clipadmin@sistema.com',))
existing = cursor.fetchone()

if existing:
    print(f"⚠️ Super Admin ya existe: {existing[0]} - Rol: {existing[1]}")
else:
    # Crear super admin
    user_id = str(uuid.uuid4())
    password_hash = generate_password_hash('Laurana@01')

    cursor.execute("""
        INSERT INTO users (id, email, password_hash, full_name, role, client_id, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (user_id, 'clipadmin@sistema.com', password_hash, 'Clip Admin', 'SUPER_ADMIN', None, 1))

    conn.commit()
    print("✅ Super Admin creado exitosamente")
    print("Email: clipadmin@sistema.com")
    print("Password: Laurana@01")
    print("Rol: SUPER_ADMIN")

conn.close()
