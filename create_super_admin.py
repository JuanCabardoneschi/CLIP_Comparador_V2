#!/usr/bin/env python3
"""
Script para crear el super administrador del sistema
"""

import sys
import os

# Añadir el directorio del proyecto al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from app import create_app, db
from app.models.user import User

def create_super_admin():
    """Crear el usuario super administrador"""

    app = create_app()

    with app.app_context():
        # Verificar si ya existe
        existing_admin = User.query.filter_by(email='clipadmin@system.com').first()
        if existing_admin:
            print("❌ Super admin ya existe")
            # Actualizar role y password por si acaso
            existing_admin.role = 'SUPER_ADMIN'
            existing_admin.client_id = None
            existing_admin.full_name = 'CLIP System Administrator'
            existing_admin.set_password('Laurana@01')
            db.session.commit()
            print("✅ Super admin actualizado")
            return

        # Crear nuevo super admin
        super_admin = User(
            email='clipadmin@system.com',
            full_name='CLIP System Administrator',
            role='SUPER_ADMIN',
            client_id=None,  # Super admin no pertenece a ningún cliente
            active=True
        )
        super_admin.set_password('Laurana@01')

        db.session.add(super_admin)
        db.session.commit()

        print("✅ Super admin creado exitosamente")
        print(f"📧 Email: clipadmin@system.com")
        print(f"🔑 Password: Laurana@01")
        print(f"👑 Role: SUPER_ADMIN")

if __name__ == "__main__":
    create_super_admin()
