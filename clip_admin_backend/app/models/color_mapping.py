"""
Modelo ColorMapping: Sistema de aprendizaje automático de colores por cliente
"""
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid
from .. import db


class ColorMapping(db.Model):
    """
    Almacena mapeos de colores aprendidos automáticamente para cada cliente.

    Permite que el sistema se adapte a los colores usados por cada cliente
    sin necesidad de hardcodear nuevos colores globalmente.

    Ejemplo:
        Cliente 1 usa "coral vibrante" → normalizado a "CORAL" → grupo "NARANJA"
        Cliente 2 usa "coral" → normalizado a "CORAL" → grupo "ROSA" (según su paleta)
    """
    __tablename__ = 'color_mappings'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)

    # Color raw tal como está en el producto (ej: "coral vibrante", "azul marino oscuro")
    raw_color = db.Column(db.String(100), nullable=False)

    # Color normalizado por el LLM (ej: "CORAL", "AZUL")
    normalized_color = db.Column(db.String(50))

    # Grupo de similitud al que pertenece (ej: "NARANJA", "AZUL")
    # Múltiples raw_colors pueden pertenecer al mismo grupo
    similarity_group = db.Column(db.String(50))

    # Contador de uso (para optimización y estadísticas)
    usage_count = db.Column(db.Integer, default=1, nullable=False)

    # Confianza del LLM al normalizar (0.0 a 1.0)
    confidence = db.Column(db.Float)

    # Metadatos adicionales (evitar nombre reservado 'metadata' en SQLAlchemy)
    extra_metadata = db.Column(JSONB, default={})

    # Timestamps
    last_used_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    client = db.relationship('Client', backref=db.backref('color_mappings', lazy='dynamic', cascade='all, delete-orphan'))

    # Constraint: un cliente no puede tener dos mapeos para el mismo raw_color
    __table_args__ = (
        db.UniqueConstraint('client_id', 'raw_color', name='uq_client_raw_color'),
        db.Index('idx_color_mappings_client', 'client_id'),
        db.Index('idx_color_mappings_usage', 'client_id', 'usage_count'),
        db.Index('idx_color_mappings_group', 'client_id', 'similarity_group'),
    )

    def __repr__(self):
        return f'<ColorMapping {self.raw_color} → {self.normalized_color} (grupo: {self.similarity_group}, usos: {self.usage_count})>'

    def to_dict(self):
        """Serializa el objeto a diccionario"""
        return {
            'id': str(self.id),
            'client_id': str(self.client_id),
            'raw_color': self.raw_color,
            'normalized_color': self.normalized_color,
            'similarity_group': self.similarity_group,
            'usage_count': self.usage_count,
            'confidence': self.confidence,
            'metadata': self.extra_metadata,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def get_or_create(cls, client_id, raw_color, normalized_color=None, similarity_group=None, confidence=None):
        """
        Obtiene un mapeo existente o crea uno nuevo.
        Incrementa usage_count si ya existe.

        Args:
            client_id: UUID del cliente
            raw_color: Color tal como está en el producto
            normalized_color: Color normalizado (opcional, se puede calcular después)
            similarity_group: Grupo al que pertenece (opcional)
            confidence: Confianza del LLM (opcional)

        Returns:
            ColorMapping instance
        """
        mapping = cls.query.filter_by(client_id=client_id, raw_color=raw_color).first()

        if mapping:
            # Actualizar uso
            mapping.usage_count += 1
            mapping.last_used_at = datetime.utcnow()
            mapping.updated_at = datetime.utcnow()

            # Actualizar campos si se proporcionan y no existían
            if normalized_color and not mapping.normalized_color:
                mapping.normalized_color = normalized_color
            if similarity_group and not mapping.similarity_group:
                mapping.similarity_group = similarity_group
            if confidence and not mapping.confidence:
                mapping.confidence = confidence

            db.session.commit()
            return mapping
        else:
            # Crear nuevo
            mapping = cls(
                client_id=client_id,
                raw_color=raw_color,
                normalized_color=normalized_color,
                similarity_group=similarity_group,
                confidence=confidence
            )
            db.session.add(mapping)
            db.session.commit()
            return mapping

    @classmethod
    def find_similar_colors(cls, client_id, normalized_color, threshold=0.85):
        """
        Encuentra colores similares ya mapeados para este cliente.

        Args:
            client_id: UUID del cliente
            normalized_color: Color normalizado a buscar
            threshold: Umbral de similitud (0.0 a 1.0)

        Returns:
            Lista de ColorMapping con colores similares
        """
        # TODO: Implementar búsqueda por embedding similarity
        # Por ahora, busca por mismo similarity_group
        return cls.query.filter_by(
            client_id=client_id,
            normalized_color=normalized_color
        ).all()

    @classmethod
    def get_client_color_groups(cls, client_id):
        """
        Obtiene todos los grupos de colores de un cliente, organizados.

        Returns:
            {
                'groups': {
                    'NARANJA': [ColorMapping, ...],
                    'AZUL': [ColorMapping, ...]
                },
                'ungrouped': [ColorMapping, ...]
            }
        """
        mappings = cls.query.filter_by(client_id=client_id).order_by(cls.usage_count.desc()).all()

        groups = {}
        ungrouped = []

        for mapping in mappings:
            if mapping.similarity_group:
                if mapping.similarity_group not in groups:
                    groups[mapping.similarity_group] = []
                groups[mapping.similarity_group].append(mapping)
            else:
                ungrouped.append(mapping)

        return {
            'groups': groups,
            'ungrouped': ungrouped
        }

    @classmethod
    def get_colors_in_group(cls, client_id, similarity_group):
        """
        Obtiene todos los colores raw de un grupo específico para un cliente.
        Útil para aplicar boost en búsquedas.

        Returns:
            Lista de strings con raw_colors
        """
        mappings = cls.query.filter_by(
            client_id=client_id,
            similarity_group=similarity_group
        ).all()

        return [m.raw_color for m in mappings]
