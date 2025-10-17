"""
Modelo Image para CLIP Comparador V2
"""
from datetime import datetime
from .. import db

class Image(db.Model):
    """Modelo para imágenes de productos"""
    __tablename__ = 'images'

    id = db.Column(db.String(36), primary_key=True)
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(500))  # Nombre del archivo original al subir
    cloudinary_url = db.Column(db.String(500))  # URL completa de Cloudinary
    cloudinary_public_id = db.Column(db.String(255))  # ID público de Cloudinary
    base64_data = db.Column(db.Text)  # Imagen en base64 para API (generado una sola vez)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    file_size = db.Column(db.Integer)  # Tamaño en bytes
    mime_type = db.Column(db.String(100))
    alt_text = db.Column(db.String(255))  # Texto alternativo para accesibilidad
    display_order = db.Column(db.Integer, default=0)  # Orden de visualización de la imagen
    is_primary = db.Column(db.Boolean, default=False)  # Imagen principal del producto
    is_processed = db.Column(db.Boolean, default=False)  # Si ya se generó el embedding
    clip_embedding = db.Column(db.Text)  # Embedding CLIP serializado como JSON
    upload_status = db.Column(db.String(50), default='pending')  # pending, processing, completed, failed
    error_message = db.Column(db.Text)  # Mensaje de error si falló el procesamiento
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    client = db.relationship('Client', backref='images')

    def __init__(self, **kwargs):
        if 'id' not in kwargs:
            import uuid
            kwargs['id'] = str(uuid.uuid4())
        super(Image, self).__init__(**kwargs)

    def __repr__(self):
        return f'<Image {self.filename}>'

    @property
    def client_slug(self):
        """Obtiene el slug del cliente dinámicamente"""
        try:
            if hasattr(self, '_client_slug_cache'):
                return self._client_slug_cache

            from app.models.client import Client
            client = Client.query.get(self.client_id)
            self._client_slug_cache = client.slug if client else "demo_fashion_store"
            return self._client_slug_cache
        except Exception:
            return "demo_fashion_store"  # Fallback seguro

    @property
    def thumbnail_url(self):
        """Genera URL de thumbnail - SOLO Cloudinary"""
        # SOLO usar Cloudinary - no hay fallback local
        if self.cloudinary_url:
            return self.cloudinary_url
        return '/static/images/placeholder.svg'

    @property
    def medium_url(self):
        """Genera URL de imagen mediana - SOLO Cloudinary"""
        # SOLO usar Cloudinary - no hay fallback local
        if self.cloudinary_url:
            return self.cloudinary_url
        return '/static/images/placeholder.svg'

    @property
    def display_url(self):
        """URL principal para mostrar la imagen - SOLO Cloudinary"""
        # SOLO usar Cloudinary - no hay fallback local
        if self.cloudinary_url:
            return self.cloudinary_url
        return '/static/images/placeholder.svg'

    @property
    def embedding_vector(self):
        """Convierte el embedding JSON a lista de números"""
        if self.clip_embedding:
            import json
            try:
                return json.loads(self.clip_embedding)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    @embedding_vector.setter
    def embedding_vector(self, value):
        """Convierte lista de números a JSON"""
        if value is not None:
            import json
            self.clip_embedding = json.dumps(value)
        else:
            self.clip_embedding = None

    def to_dict(self):
        """Convierte el objeto a diccionario para JSON"""
        return {
            'id': self.id,
            'client_id': self.client_id,
            'product_id': self.product_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'image_url': self.display_url,  # Usar la URL generada por ImageManager
            'thumbnail_url': self.thumbnail_url,
            'medium_url': self.medium_url,
            'width': self.width,
            'height': self.height,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'is_primary': self.is_primary,
            'is_processed': self.is_processed,
            'upload_status': self.upload_status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def get_by_client(client_id, processed_only=False):
        """Obtiene imágenes por cliente"""
        query = Image.query.filter_by(client_id=client_id)
        if processed_only:
            query = query.filter_by(is_processed=True)
        return query.order_by(Image.created_at.desc()).all()

    @staticmethod
    def get_by_product(product_id):
        """Obtiene imágenes por producto"""
        return Image.query.filter_by(product_id=product_id)\
            .order_by(Image.is_primary.desc(), Image.created_at).all()

    @staticmethod
    def get_unprocessed():
        """Obtiene imágenes que necesitan procesamiento CLIP"""
        return Image.query.filter_by(
            is_processed=False,
            upload_status='pending'
        ).all()

    def set_as_primary(self):
        """Establece esta imagen como primaria del producto"""
        # Quitar primaria de otras imágenes del mismo producto
        Image.query.filter_by(product_id=self.product_id, is_primary=True)\
            .update({'is_primary': False})

        # Establecer esta como primaria
        self.is_primary = True
        db.session.commit()
