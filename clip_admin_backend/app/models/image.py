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

    # 🔗 PIPELINE BASE64 TIENDANUBE
    base64_data = db.Column(db.Text)  # Imagen completa en base64 (opcional)
    base64_thumb = db.Column(db.Text)  # Thumbnail base64 para UI/embeddings
    source_url = db.Column(db.Text)  # URL original de Tiendanube
    source_updated_at = db.Column(db.DateTime)  # Última actualización de fuente
    hash_sha256 = db.Column(db.String(128))  # Hash para detectar cambios
    size_bytes = db.Column(db.Integer)  # Tamaño en bytes (corregir nombre de file_size)

    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    file_size = db.Column(db.Integer)  # DEPRECATED: usar size_bytes
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

    # --- Campos de recorte manual / refinamiento ---
    crop_x = db.Column(db.Integer)
    crop_y = db.Column(db.Integer)
    crop_w = db.Column(db.Integer)
    crop_h = db.Column(db.Integer)
    is_crop_manual = db.Column(db.Boolean, default=None)  # True si usuario lo definió, False si auto, None si no aplica
    refined = db.Column(db.Boolean, default=None)  # Marcador de que el embedding ya fue regenerado tras recorte

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

    def _is_tiendanube_client(self):
        """Verifica si el cliente es de Tiendanube"""
        try:
            if hasattr(self, '_is_tiendanube_cache'):
                return self._is_tiendanube_cache

            from app.models.client import Client
            client = Client.query.get(self.client_id)
            self._is_tiendanube_cache = (client and client.integration_type == 'tiendanube')
            return self._is_tiendanube_cache
        except Exception:
            return False

    @property
    def thumbnail_url(self):
        """Genera URL de thumbnail - Tiendanube source_url o Cloudinary"""
        # Priorizar URL de origen si existe (Tiendanube / WooCommerce)
        if self.source_url:
            return self.source_url
        # Clientes standalone usan Cloudinary
        if self.cloudinary_url:
            return self.cloudinary_url
        return '/static/images/placeholder.svg'

    @property
    def medium_url(self):
        """Genera URL de imagen mediana - Tiendanube source_url o Cloudinary"""
        # Priorizar URL de origen si existe (Tiendanube / WooCommerce)
        if self.source_url:
            return self.source_url
        # Clientes standalone usan Cloudinary
        if self.cloudinary_url:
            return self.cloudinary_url
        return '/static/images/placeholder.svg'

    @property
    def display_url(self):
        """URL principal para mostrar la imagen - Tiendanube source_url o Cloudinary"""
        # Priorizar URL de origen si existe (Tiendanube / WooCommerce)
        if self.source_url:
            return self.source_url
        # Clientes standalone usan Cloudinary
        if self.cloudinary_url:
            return self.cloudinary_url
        return '/static/images/placeholder.svg'

    @property
    def optimized_url(self):
        """
        URL optimizada que prioriza base64 cacheado sobre Cloudinary/Tiendanube.
        Usar este método para:
        - Generación de embeddings CLIP (evita descargas repetidas)
        - Respuestas de API de búsqueda (reduce llamadas externas)
        - Cualquier operación que necesite la imagen frecuentemente
        """
        # 1. Priorizar base64 si existe (ya está en Railway, sin latencia)
        if self.base64_data:
            return self.base64_data

        # 2. Si hay URL de origen (Tiendanube / WooCommerce), usarla
        if self.source_url:
            return self.source_url

        # 3. Fallback a Cloudinary para clientes standalone
        if self.cloudinary_url:
            return self.cloudinary_url

        # 4. Placeholder si no hay nada
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
            'image_url': self.optimized_url,  # Base64 cacheado (evita Cloudinary)
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
            'crop': {
                'x': self.crop_x,
                'y': self.crop_y,
                'w': self.crop_w,
                'h': self.crop_h,
                'is_manual': self.is_crop_manual,
                'refined': self.refined
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    # ---- Utilidades de recorte ----
    def has_crop(self) -> bool:
        return all([
            isinstance(self.crop_x, int), isinstance(self.crop_y, int),
            isinstance(self.crop_w, int), isinstance(self.crop_h, int),
            (self.crop_w or 0) > 0, (self.crop_h or 0) > 0
        ])

    def get_crop_box(self):
        """Devuelve la caja de recorte (x1,y1,x2,y2) o None"""
        if not self.has_crop():
            return None
        return (
            int(self.crop_x),
            int(self.crop_y),
            int(self.crop_x + self.crop_w),
            int(self.crop_y + self.crop_h)
        )

    def apply_crop_to_pil(self, pil_img):
        """Aplica recorte a una PIL Image si existe bounding box válido"""
        box = self.get_crop_box()
        if not box:
            return pil_img
        try:
            # Sanitizar límites
            x1, y1, x2, y2 = box
            x1 = max(0, min(x1, pil_img.width - 1))
            y1 = max(0, min(y1, pil_img.height - 1))
            x2 = max(x1 + 1, min(x2, pil_img.width))
            y2 = max(y1 + 1, min(y2, pil_img.height))
            return pil_img.crop((x1, y1, x2, y2))
        except Exception:
            return pil_img

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
