"""
Modelo CategoryPairExclusion - Reglas de exclusión de pares de categorías por cliente.

Permite definir que cuando aparezcan ambas categorías de un par (e.g., Delantal Completo vs Medio Delantal),
se aplique una regla de decisión para seleccionar una y suprimir la otra.

Campos:
- client_id: Cliente al que pertenece la regla
- primary_category_id: Categoría "dominante" del par
- secondary_category_id: Categoría a excluir si la primaria gana
- exclusion_rule: Tipo de regla ('torso_evidence', 'score_threshold', 'custom')
- params: JSON con parámetros específicos de la regla
- is_active: Si está activa o no
"""
from app import db
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime

class CategoryPairExclusion(db.Model):
    __tablename__ = 'category_pair_exclusions'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    primary_category_id = db.Column(UUID(as_uuid=True), db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False)
    secondary_category_id = db.Column(UUID(as_uuid=True), db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False)

    # Tipo de regla: 'torso_evidence', 'score_threshold', 'custom'
    exclusion_rule = db.Column(db.String(50), nullable=False, default='torso_evidence')

    # Parámetros JSON específicos de la regla
    # Ejemplo para 'torso_evidence':
    # {
    #   "override_gap_max": 0.10,
    #   "torso_evidence_min": 0.24,
    #   "torso_advantage_min": 0.06,
    #   "suppression_evidence_threshold": 0.22,
    #   "tie_margin": 0.02
    # }
    params = db.Column(JSONB, nullable=False, default={})

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = db.relationship('Client', backref=db.backref('pair_exclusions', lazy='dynamic'))
    primary_category = db.relationship('Category', foreign_keys=[primary_category_id], backref=db.backref('primary_exclusions', lazy='dynamic'))
    secondary_category = db.relationship('Category', foreign_keys=[secondary_category_id], backref=db.backref('secondary_exclusions', lazy='dynamic'))

    # Índices
    __table_args__ = (
        db.Index('idx_pair_exclusions_client', 'client_id'),
        db.Index('idx_pair_exclusions_active', 'client_id', 'is_active'),
        db.UniqueConstraint('client_id', 'primary_category_id', 'secondary_category_id', name='uq_pair_exclusion'),
    )

    def __repr__(self):
        return f"<CategoryPairExclusion {self.primary_category.name} vs {self.secondary_category.name} ({self.exclusion_rule})>"

    def to_dict(self):
        return {
            'id': str(self.id),
            'client_id': str(self.client_id),
            'primary_category_id': str(self.primary_category_id),
            'primary_category_name': self.primary_category.name if self.primary_category else None,
            'secondary_category_id': str(self.secondary_category_id),
            'secondary_category_name': self.secondary_category.name if self.secondary_category else None,
            'exclusion_rule': self.exclusion_rule,
            'params': self.params,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
