# Modelo Cliente
import uuid
import secrets
from datetime import datetime
from slugify import slugify
from . import db
from sqlalchemy import event
from datetime import datetime as _dt
from app.models.store_search_config import StoreSearchConfig

class Client(db.Model):
    __tablename__ = "clients"

    # UUID almacenado como String(36) para consistencia
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), nullable=False)
    industry = db.Column(db.String(100), default='general')  # Rubro/Industria del cliente
    # description = db.Column(db.Text)  # COMENTADO: Esta columna no existe en la BD real
    is_active = db.Column(db.Boolean, default=True)
    api_key = db.Column(db.String(100), unique=True, nullable=False)  # API Key del cliente - OBLIGATORIO
    api_settings = db.Column(db.Text, default='{}')  # Columna que existe en la BD real

    # 🎯 SENSIBILIDAD DE DETECCIÓN (valores 1-100)
    category_confidence_threshold = db.Column(db.Integer, default=70)  # Confianza mínima para detectar categoría (70%)
    product_similarity_threshold = db.Column(db.Integer, default=30)   # Similitud mínima para matching de productos (30%)

    # 🔗 INTEGRACIÓN TIENDANUBE
    integration_type = db.Column(db.String(50), default='standalone', nullable=False)  # 'standalone' | 'tiendanube'
    integration_config = db.Column(db.JSON, default=dict, nullable=False)  # Metadatos de integración
    is_read_only = db.Column(db.Boolean, default=False, nullable=False)  # TRUE para Tiendanube

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, **kwargs):
        """Constructor que genera automáticamente la API Key"""
        if 'api_key' not in kwargs or not kwargs['api_key']:
            kwargs['api_key'] = self.generate_api_key()

        if 'slug' not in kwargs or not kwargs['slug']:
            kwargs['slug'] = self.generate_slug(kwargs.get('name', ''))

        super(Client, self).__init__(**kwargs)

    @staticmethod
    def generate_api_key():
        """Genera una API Key única y segura"""
        prefix = "clip_"
        # Generar 24 caracteres hexadecimales (12 bytes)
        api_key = prefix + secrets.token_hex(12)
        return api_key

    @staticmethod
    def generate_slug(name):
        """Genera un slug único basado en el nombre"""
        base_slug = slugify(name)
        counter = 1
        slug = base_slug

        # Verificar si el slug ya existe y generar uno único
        while Client.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    def regenerate_api_key(self):
        """Regenera la API Key del cliente"""
        old_key = self.api_key
        new_key = self.generate_api_key()

        # Verificar que la nueva key sea única
        while Client.query.filter_by(api_key=new_key).first():
            new_key = self.generate_api_key()

        self.api_key = new_key
        return old_key, new_key

    def __repr__(self):
        return f"<Client {self.name}>"


# Auto-crear configuración de búsqueda por defecto al crear un cliente
@event.listens_for(Client, 'after_insert')
def _create_default_search_config(mapper, connection, target):
    try:
        table = StoreSearchConfig.__table__
        connection.execute(
            table.insert().values(
                store_id=target.id,
                visual_weight=0.6,
                metadata_weight=0.3,
                business_weight=0.1,
                metadata_config={
                    'color': {'enabled': True, 'weight': 0.3},
                    'brand': {'enabled': True, 'weight': 0.3},
                    'pattern': {'enabled': False, 'weight': 0.2}
                },
                created_at=_dt.utcnow(),
                updated_at=_dt.utcnow()
            )
        )
    except Exception:
        # Evitar que falle la creación del cliente si la config ya existe
        # o si hay un problema no crítico al insertar la configuración.
        pass

# COMENTADO: No existe la tabla api_keys en la base de datos real
# class APIKey(db.Model):
#     __tablename__ = "api_keys"
#
#     # Usar String en lugar de UUID para compatibilidad con SQLite
#     id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
#     client_id = db.Column(db.String(36), db.ForeignKey("clients.id"))
#     name = db.Column(db.String(255), nullable=False)
#     key_hash = db.Column(db.String(255), unique=True, nullable=False)
#     is_active = db.Column(db.Boolean, default=True)
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
#
#     def __repr__(self):
#         return f"<APIKey {self.name}>"
