"""
Modelo Product para CLIP Comparador V2
"""
from datetime import datetime
from .. import db

class Product(db.Model):
    """Modelo para productos"""
    __tablename__ = 'products'

    id = db.Column(db.String(36), primary_key=True)
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)
    category_id = db.Column(db.String(36), db.ForeignKey('categories.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    brand = db.Column(db.String(100))  # Marca del producto
    sku = db.Column(db.String(100))  # Código único del producto
    price = db.Column(db.Numeric(10, 2))
    stock = db.Column(db.Integer, default=0)
    color = db.Column(db.String(50))  # Color del producto
    tags = db.Column(db.Text)  # Tags separados por comas para búsqueda
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    client = db.relationship('Client', backref='products')
    images = db.relationship('Image', backref='product', lazy='dynamic', cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        if 'id' not in kwargs:
            import uuid
            kwargs['id'] = str(uuid.uuid4())
        super(Product, self).__init__(**kwargs)

    def __repr__(self):
        return f'<Product {self.name}>'

    @property
    def primary_image(self):
        """Obtiene la imagen principal del producto"""
        return self.images.filter_by(is_primary=True).first() or self.images.first()

    @property
    def image_count(self):
        """Obtiene el número total de imágenes del producto"""
        return self.images.count()

    @property
    def tag_list(self):
        """Convierte tags string a lista"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []

    @tag_list.setter
    def tag_list(self, value):
        """Convierte lista de tags a string"""
        if isinstance(value, list):
            self.tags = ', '.join(value)
        else:
            self.tags = value

    def to_dict(self):
        """Convierte el objeto a diccionario para JSON"""
        return {
            'id': self.id,
            'client_id': self.client_id,
            'category_id': self.category_id,
            'name': self.name,
            'description': self.description,
            'sku': self.sku,
            'price': float(self.price) if self.price else None,
            'stock': self.stock,
            'tags': self.tag_list,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'primary_image': self.primary_image.to_dict() if self.primary_image else None,
            'image_count': self.images.count()
        }

    @staticmethod
    def get_by_client(client_id, active_only=True):
        """Obtiene productos por cliente"""
        query = Product.query.filter_by(client_id=client_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(Product.name).all()

    @staticmethod
    def get_by_category(category_id, active_only=True):
        """Obtiene productos por categoría"""
        query = Product.query.filter_by(category_id=category_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(Product.name).all()

    @staticmethod
    def search_by_text(client_id, search_term):
        """Búsqueda de productos por texto"""
        return Product.query.filter(
            Product.client_id == client_id,
            Product.is_active == True,
            db.or_(
                Product.name.ilike(f'%{search_term}%'),
                Product.description.ilike(f'%{search_term}%'),
                Product.tags.ilike(f'%{search_term}%'),
                Product.sku.ilike(f'%{search_term}%')
            )
        ).all()
