"""
Modelo de integración con WooCommerce
Basado en el modelo de TiendanubeIntegration pero adaptado a WooCommerce
"""
from datetime import datetime
from .. import db
import uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID
from cryptography.fernet import Fernet
import os

# Clave para encriptar tokens (debe estar en variable de entorno en producción)
ENCRYPTION_KEY = os.environ.get('TOKEN_ENCRYPTION_KEY', Fernet.generate_key())
cipher = Fernet(ENCRYPTION_KEY) if isinstance(ENCRYPTION_KEY, bytes) else Fernet(ENCRYPTION_KEY.encode())

class WooCommerceIntegration(db.Model):
    """
    Modelo para almacenar integración con WooCommerce (REST API)

    Diferencias vs Tiendanube:
    - No usa OAuth, usa Consumer Key + Secret
    - store_url en vez de store_id
    - Sin script_id (widget se instala manualmente o vía plugin)
    """
    __tablename__ = 'woocommerce_integrations'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)

    # Datos de la tienda WooCommerce
    store_url = db.Column(db.String(500), nullable=False, unique=True, index=True)  # https://mitienda.com
    store_name = db.Column(db.String(255))
    store_email = db.Column(db.String(255))

    # Credenciales REST API (encriptadas)
    consumer_key = db.Column(db.Text, nullable=False)      # ck_xxxxxxxxxxxxx
    consumer_secret = db.Column(db.Text, nullable=False)   # cs_xxxxxxxxxxxxx

    # Versión de API y configuración
    api_version = db.Column(db.String(10), default='v3', nullable=False)  # v3 es la más común
    use_ssl = db.Column(db.Boolean, default=True)  # HTTPS requerido para REST API

    # Webhooks configurados
    webhook_ids = db.Column(JSONB, nullable=True)  # {"product.created": 123, ...}
    webhook_secret = db.Column(db.String(100), nullable=True)  # Para validar webhooks

    # Widget installation method
    widget_method = db.Column(db.String(50), nullable=True)  # 'plugin', 'shortcode', 'manual'

    # Estado
    is_active = db.Column(db.Boolean, default=True)
    installed_at = db.Column(db.DateTime, default=datetime.utcnow)
    uninstalled_at = db.Column(db.DateTime, nullable=True)

    # Sincronización
    last_sync_at = db.Column(db.DateTime, nullable=True)
    sync_status = db.Column(db.String(50), nullable=True)  # 'pending', 'in_progress', 'completed', 'error'
    sync_error = db.Column(db.Text, nullable=True)

    # Metadata adicional
    wc_version = db.Column(db.String(20), nullable=True)  # Versión de WooCommerce instalada
    wp_version = db.Column(db.String(20), nullable=True)  # Versión de WordPress
    timezone = db.Column(db.String(50), nullable=True)
    currency = db.Column(db.String(10), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    client = db.relationship('Client', backref=db.backref('woocommerce_integrations', lazy='dynamic'))

    def __repr__(self):
        return f'<WooCommerceIntegration {self.store_url} - Client {self.client_id}>'

    def set_consumer_key(self, key: str):
        """Encripta y guarda el consumer_key"""
        self.consumer_key = cipher.encrypt(key.encode()).decode()

    def get_consumer_key(self) -> str:
        """Desencripta y devuelve el consumer_key"""
        try:
            return cipher.decrypt(self.consumer_key.encode()).decode()
        except Exception:
            return self.consumer_key  # Fallback si no está encriptado

    def set_consumer_secret(self, secret: str):
        """Encripta y guarda el consumer_secret"""
        self.consumer_secret = cipher.encrypt(secret.encode()).decode()

    def get_consumer_secret(self) -> str:
        """Desencripta y devuelve el consumer_secret"""
        try:
            return cipher.decrypt(self.consumer_secret.encode()).decode()
        except Exception:
            return self.consumer_secret  # Fallback si no está encriptado

    @property
    def api_base_url(self) -> str:
        """Construye URL base de la API REST"""
        protocol = 'https' if self.use_ssl else 'http'
        # Limpiar URL (remover trailing slash)
        clean_url = self.store_url.rstrip('/')
        return f"{protocol}://{clean_url.replace('http://', '').replace('https://', '')}/wp-json/wc/{self.api_version}"

    @property
    def webhook_delivery_url(self) -> str:
        """URL donde WooCommerce enviará los webhooks"""
        # TODO: Configurar el dominio base desde settings
        base_url = os.environ.get('APP_BASE_URL', 'https://clipcomparadorv2-production.up.railway.app')
        return f"{base_url}/api/webhooks/woocommerce"

    def to_dict(self, include_credentials=False):
        """Convierte el modelo a diccionario"""
        data = {
            'id': self.id,
            'client_id': self.client_id,
            'store_url': self.store_url,
            'store_name': self.store_name,
            'store_email': self.store_email,
            'api_version': self.api_version,
            'use_ssl': self.use_ssl,
            'webhook_ids': self.webhook_ids,
            'widget_method': self.widget_method,
            'is_active': self.is_active,
            'installed_at': self.installed_at.isoformat() if self.installed_at else None,
            'uninstalled_at': self.uninstalled_at.isoformat() if self.uninstalled_at else None,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'sync_status': self.sync_status,
            'sync_error': self.sync_error,
            'wc_version': self.wc_version,
            'wp_version': self.wp_version,
            'timezone': self.timezone,
            'currency': self.currency,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'api_base_url': self.api_base_url,
            'webhook_delivery_url': self.webhook_delivery_url
        }

        if include_credentials:
            data['consumer_key'] = self.get_consumer_key()
            data['consumer_secret'] = self.get_consumer_secret()
            data['webhook_secret'] = self.webhook_secret

        return data
