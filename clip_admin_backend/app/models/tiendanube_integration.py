"""
Modelo de integración con Tiendanube
"""
from datetime import datetime
from .. import db
import uuid
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from cryptography.fernet import Fernet
import os

# Clave para encriptar tokens (debe estar en variable de entorno en producción)
ENCRYPTION_KEY = os.environ.get('TOKEN_ENCRYPTION_KEY', Fernet.generate_key())
cipher = Fernet(ENCRYPTION_KEY) if isinstance(ENCRYPTION_KEY, bytes) else Fernet(ENCRYPTION_KEY.encode())

class TiendanubeIntegration(db.Model):
    """
    Modelo para almacenar integración OAuth y datos de sincronización con Tiendanube
    """
    __tablename__ = 'tiendanube_integrations'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)

    # Datos de la tienda Tiendanube
    store_id = db.Column(db.String(50), nullable=False, unique=True, index=True)  # user_id de Tiendanube
    store_name = db.Column(db.String(255))
    store_email = db.Column(db.String(255))
    store_domain = db.Column(db.String(255))

    # Tokens OAuth (access_token encriptado)
    access_token = db.Column(db.Text, nullable=False)  # Almacenado encriptado
    scopes = db.Column(ARRAY(db.String), nullable=True)  # Array de permisos

    # Widget injection
    script_id = db.Column(db.Integer, nullable=True)  # ID del script inyectado (si aplica)

    # Estado
    is_active = db.Column(db.Boolean, default=True)
    installed_at = db.Column(db.DateTime, default=datetime.utcnow)
    uninstalled_at = db.Column(db.DateTime, nullable=True)

    # Sincronización
    last_sync_at = db.Column(db.DateTime, nullable=True)
    sync_status = db.Column(db.String(50), nullable=True)  # 'pending', 'in_progress', 'completed', 'error'
    sync_error = db.Column(db.Text, nullable=True)

    # Webhook IDs registrados
    webhook_ids = db.Column(JSONB, nullable=True)  # {"product_created": 123, ...}

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    client = db.relationship('Client', backref=db.backref('tiendanube_integrations', lazy='dynamic'))

    def __repr__(self):
        return f'<TiendanubeIntegration {self.store_id} - Client {self.client_id}>'

    def set_access_token(self, token: str):
        """Encripta y guarda el access_token"""
        self.access_token = cipher.encrypt(token.encode()).decode()

    def get_access_token(self) -> str:
        """Desencripta y devuelve el access_token"""
        try:
            return cipher.decrypt(self.access_token.encode()).decode()
        except Exception:
            return self.access_token  # Fallback si no está encriptado

    def to_dict(self, include_token=False):
        """Convierte el modelo a diccionario"""
        data = {
            'id': self.id,
            'client_id': self.client_id,
            'store_id': self.store_id,
            'store_name': self.store_name,
            'store_email': self.store_email,
            'store_domain': self.store_domain,
            'scopes': self.scopes,
            'script_id': self.script_id,
            'is_active': self.is_active,
            'installed_at': self.installed_at.isoformat() if self.installed_at else None,
            'uninstalled_at': self.uninstalled_at.isoformat() if self.uninstalled_at else None,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'sync_status': self.sync_status,
            'sync_error': self.sync_error,
            'webhook_ids': self.webhook_ids,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        if include_token:
            data['access_token'] = self.get_access_token()
        return data
