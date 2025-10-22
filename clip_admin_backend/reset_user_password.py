"""
Script para resetear contraseña de usuario específico
"""
import sys
import os

# Añadir el directorio al path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

# Importar app desde app.py
from app import db, app
from app.models.user import User

with app.app_context():
    email = "esilvestre@redsis.com.ar"
    nueva_password = "demo123"

    user = User.query.filter_by(email=email).first()

    if user:
        print(f"✅ Usuario encontrado: {user.email}")
        print(f"   Nombre: {user.full_name or 'Sin nombre'}")
        print(f"   Cliente: {user.client.name if user.client else 'Sin cliente'}")
        print(f"   ID: {user.id}")

        user.set_password(nueva_password)
        db.session.commit()

        print(f"\n🔑 Nueva contraseña establecida: {nueva_password}")
        print(f"✅ Contraseña actualizada correctamente")
        print(f"\n📧 Credenciales de acceso:")
        print(f"   Email: {email}")
        print(f"   Contraseña: {nueva_password}")
    else:
        print(f"❌ Usuario {email} NO encontrado en la base de datos")

