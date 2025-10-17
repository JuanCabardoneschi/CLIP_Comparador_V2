# Modelo Usuario
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db

class User(UserMixin, db.Model):
    __tablename__ = "users"

    # UUID almacenado como String para compatibilidad con diferentes drivers
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = db.Column(db.String(36), db.ForeignKey("clients.id"))
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=True)  # ✅ Restaurado - ahora existe en BD
    role = db.Column(db.String(50), default="STORE_ADMIN")  # SUPER_ADMIN | STORE_ADMIN
    active = db.Column(db.Boolean, default=True, name='is_active')  # Mapeo a columna is_active de BD
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación con Client
    client = db.relationship('Client', backref='users', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        print(f"🔍 DEBUG: Verificando contraseña para usuario {self.email}")
        print(f"🔍 DEBUG: Password recibida: '{password}' (len: {len(password)})")
        print(f"🔍 DEBUG: Hash almacenado: {self.password_hash[:50]}... (len: {len(self.password_hash)})")
        result = check_password_hash(self.password_hash, password)
        print(f"🔍 DEBUG: Resultado verificación: {result}")
        return result

    # Métodos requeridos por Flask-Login (UserMixin ya provee algunos, pero los sobreescribimos)
    @property
    def is_active(self):
        return bool(self.active)

    def get_id(self):
        return str(self.id)

    @property
    def is_super_admin(self):
        """Verifica si el usuario es super administrador"""
        return self.role == "SUPER_ADMIN"

    @property
    def is_store_admin(self):
        """Verifica si el usuario es administrador de tienda"""
        return self.role == "STORE_ADMIN"

    def can_access_client(self, client_id):
        """Verifica si el usuario puede acceder a un cliente específico"""
        if self.is_super_admin:
            return True
        return str(self.client_id) == str(client_id)

    def __repr__(self):
        return f"<User {self.email}>"
