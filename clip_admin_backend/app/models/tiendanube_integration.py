"""
Modelo de integración con Tiendanube
"""
from datetime import datetime
from .. import db
import uuid

class TiendanubeIntegration(db.Model):
    """
    Modelo para almacenar tokens de acceso de Tiendanube por cliente
    """
    __tablename__ = 'tiendanube_integrations'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)

    # Datos de la tienda Tiendanube
    store_id = db.Column(db.String(50), nullable=False, unique=True)  # user_id de Tiendanube
    store_name = db.Column(db.String(255))
    store_url = db.Column(db.String(500))

    # Tokens OAuth
    access_token = db.Column(db.String(500), nullable=False)
    token_type = db.Column(db.String(50), default='bearer')
    scope = db.Column(db.String(255))  # Ej: write_products write_content

    # Estado
    is_active = db.Column(db.Boolean, default=True)
    last_sync_at = db.Column(db.DateTime)

    # Configuración de sincronización
    auto_sync_enabled = db.Column(db.Boolean, default=False)
    sync_products = db.Column(db.Boolean, default=True)
    sync_images = db.Column(db.Boolean, default=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    client = db.relationship('Client', backref=db.backref('tiendanube_integrations', lazy='dynamic'))

    def __repr__(self):
        return f'<TiendanubeIntegration {self.store_id} - Client {self.client_id}>'

    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'client_id': self.client_id,
            'store_id': self.store_id,
            'store_name': self.store_name,
            'store_url': self.store_url,
            'token_type': self.token_type,
            'scope': self.scope,
            'is_active': self.is_active,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'auto_sync_enabled': self.auto_sync_enabled,
            'sync_products': self.sync_products,
            'sync_images': self.sync_images,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
