"""
Modelo para Dataset de Training/Calibración por Cliente
Permite a cada cliente construir su propio ground-truth dataset
"""

from app import db
from datetime import datetime
import uuid


class TrainingImage(db.Model):
    """
    Imágenes etiquetadas manualmente para calibración de thresholds
    Cada cliente construye su propio dataset de validación
    """
    __tablename__ = 'training_images'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Relación con cliente
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False, index=True)
    client = db.relationship('Client', backref='training_images')

    # Archivo de imagen
    filename = db.Column(db.String(255), nullable=False)
    cloudinary_public_id = db.Column(db.String(255))  # ID en Cloudinary
    cloudinary_url = db.Column(db.Text)  # URL completa

    # Ground-truth: categorías esperadas (JSON array de nombres)
    expected_categories = db.Column(db.JSON, nullable=False, default=list)
    # Ejemplo: ["Delantal Completo", "CAMISAS HOMBRE- DAMA"]

    # Notas descriptivas
    notes = db.Column(db.Text)

    # Tipo de caso (para filtrar en calibración)
    case_type = db.Column(db.String(50), default='general')
    # Valores: 'single', 'multi', 'edge_case', 'problematic'

    # Estado de uso
    is_active = db.Column(db.Boolean, default=True, index=True)

    # Metadatos de calibración (últimos resultados)
    last_calibration_result = db.Column(db.JSON)  # Scores obtenidos, categorías detectadas
    last_calibration_date = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_user_id = db.Column(db.String(36), db.ForeignKey('users.id'))

    def __repr__(self):
        return f'<TrainingImage {self.filename} - {len(self.expected_categories)} categories>'

    def to_dict(self):
        """Serializa para JSON"""
        return {
            'id': self.id,
            'filename': self.filename,
            'image_url': self.cloudinary_url,
            'expected_categories': self.expected_categories,
            'notes': self.notes,
            'case_type': self.case_type,
            'is_active': self.is_active,
            'last_calibration_result': self.last_calibration_result,
            'last_calibration_date': self.last_calibration_date.isoformat() if self.last_calibration_date else None,
            'created_at': self.created_at.isoformat()
        }

    @staticmethod
    def get_dataset_for_client(client_id, active_only=True):
        """Obtiene el dataset completo de un cliente"""
        query = TrainingImage.query.filter_by(client_id=client_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(TrainingImage.created_at.desc()).all()

    @staticmethod
    def get_statistics(client_id):
        """Estadísticas del dataset de un cliente"""
        images = TrainingImage.query.filter_by(client_id=client_id, is_active=True).all()

        if not images:
            return {
                'total_images': 0,
                'categories_distribution': {},
                'case_types': {}
            }

        # Contar categorías
        category_counts = {}
        case_type_counts = {}

        for img in images:
            # Categorías
            for cat_name in img.expected_categories:
                category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

            # Tipos de caso
            case_type_counts[img.case_type] = case_type_counts.get(img.case_type, 0) + 1

        return {
            'total_images': len(images),
            'categories_distribution': category_counts,
            'case_types': case_type_counts,
            'avg_categories_per_image': sum(len(img.expected_categories) for img in images) / len(images)
        }


class CalibrationRun(db.Model):
    """
    Historial de ejecuciones de calibración
    Guarda métricas y thresholds sugeridos por cada run
    """
    __tablename__ = 'calibration_runs'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False, index=True)
    client = db.relationship('Client', backref='calibration_runs')

    # Resultados de calibración (JSON con métricas por categoría)
    results = db.Column(db.JSON, nullable=False)
    # {
    #   "category_metrics": { "CAMISAS": {"precision": 0.8, "recall": 0.9, ...}, ... },
    #   "threshold_suggestions": { "CAMISAS": 0.65, ... },
    #   "dataset_size": 30
    # }

    # Thresholds aplicados (si el usuario los aplicó)
    applied = db.Column(db.Boolean, default=False)
    applied_at = db.Column(db.DateTime)
    applied_by_user_id = db.Column(db.String(36), db.ForeignKey('users.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = db.Column(db.String(36), db.ForeignKey('users.id'))

    def __repr__(self):
        return f'<CalibrationRun {self.created_at} - {self.client_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'results': self.results,
            'applied': self.applied,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None,
            'created_at': self.created_at.isoformat()
        }
