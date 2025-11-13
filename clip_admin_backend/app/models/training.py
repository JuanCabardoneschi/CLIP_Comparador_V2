"""
DEPRECATED: Módulos de entrenamiento eliminados del sistema.
Este archivo permanece solo para evitar import errors en entornos antiguos.
"""
raise ImportError("training models removed: 'training_events' y 'client_category_variants' fueron eliminados.")
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from .. import db
import uuid


class TrainingEvent(db.Model):
    """Evento de entrenamiento visual (admin marca resultados)."""
    __tablename__ = 'training_events'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey('clients.id'), nullable=False)
    category_id = db.Column(UUID(as_uuid=True), db.ForeignKey('categories.id'), nullable=True)

    # Referencia a la imagen consultada (URL, id de imagen subida, hash, etc.)
    query_image_ref = db.Column(db.String(500), nullable=True)

    # Top-K mostrado al admin (lista de dict {product_id, score})
    topk_results = db.Column(db.JSON, nullable=False, default=list)

    # Positivos y negativos marcados por el admin (listas de product_id)
    positives = db.Column(db.JSON, nullable=False, default=list)
    negatives = db.Column(db.JSON, nullable=False, default=list)

    # Variante asignada (ej. "bib" / "waist" / "medio") – opcional
    variant_key = db.Column(db.String(64), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    client = db.relationship('Client', backref='training_events')
    category = db.relationship('Category', backref='training_events')

    def to_dict(self):
        return {
            'id': str(self.id),
            'client_id': str(self.client_id),
            'category_id': str(self.category_id) if self.category_id else None,
            'query_image_ref': self.query_image_ref,
            'topk_results': self.topk_results,
            'positives': self.positives,
            'negatives': self.negatives,
            'variant_key': self.variant_key,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ClientCategoryVariant(db.Model):
    """Variante visual dentro de una categoría para un cliente (sub-centroide)."""
    __tablename__ = 'client_category_variants'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey('clients.id'), nullable=False)
    category_id = db.Column(UUID(as_uuid=True), db.ForeignKey('categories.id'), nullable=False)

    variant_key = db.Column(db.String(64), nullable=False)  # identificador interno (ej. "bib", "waist")
    name = db.Column(db.String(120), nullable=False)  # nombre visible para admin

    # Centroid embedding serializado como lista JSON (normalizado)
    centroid_embedding = db.Column(db.Text, nullable=True)
    support_count = db.Column(db.Integer, default=0)  # cantidad de ejemplos (positives) usados

    # Prompts auxiliares para re-ranking (iteración 2)
    prompts = db.Column(db.JSON, nullable=False, default=list)

    active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship('Client', backref='category_variants')
    category = db.relationship('Category', backref='category_variants')

    def to_dict(self):
        return {
            'id': str(self.id),
            'client_id': str(self.client_id),
            'category_id': str(self.category_id),
            'variant_key': self.variant_key,
            'name': self.name,
            'support_count': self.support_count,
            'active': self.active,
            'prompts': self.prompts,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def get_active_variants(client_id, category_id):
        return ClientCategoryVariant.query.filter_by(
            client_id=client_id,
            category_id=category_id,
            active=True
        ).all()
