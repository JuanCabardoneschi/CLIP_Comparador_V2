from datetime import datetime
from .. import db
import uuid
from sqlalchemy.dialects.postgresql import ARRAY
from ..logging_config import log_error, log_info

class SearchLog(db.Model):
    """Modelo para registrar búsquedas realizadas por los clientes

    Propósito: Analytics de uso del sistema y gap detection
    - Tracking de búsquedas visuales y por texto
    - Detección de categorías que usuarios buscan pero no existen
    - Detección de términos/atributos no disponibles en catálogo
    """
    __tablename__ = 'search_logs'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)

    # Tipo y datos de búsqueda
    search_type = db.Column(db.String(20), nullable=False)  # 'visual', 'text', 'gpt4v-unified'
    query_text = db.Column(db.Text)  # Query original (si es texto)
    image_url = db.Column(db.Text)  # URL de imagen (si es visual)

    # Categorías detectadas (ARRAY de PostgreSQL)
    categories_detected = db.Column(ARRAY(db.Text))  # Todas las categorías detectadas
    categories_matched = db.Column(ARRAY(db.Text))   # Categorías que SÍ existen
    categories_missing = db.Column(ARRAY(db.Text))   # Categorías NO disponibles (GAP)

    # Términos en búsqueda por texto
    terms_extracted = db.Column(ARRAY(db.Text))      # Términos extraídos
    terms_matched = db.Column(ARRAY(db.Text))        # Términos que matchearon
    terms_unmatched = db.Column(ARRAY(db.Text))      # Términos sin match (GAP)

    # Resultados
    results_count = db.Column(db.Integer, default=0)
    had_results = db.Column(db.Boolean, default=False)

    # Performance
    response_time_ms = db.Column(db.Integer)

    # Metadata
    threshold_used = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relación con client
    client = db.relationship('Client', backref='search_logs')

    @staticmethod
    def log_search(client_id, search_type, **kwargs):
        """Crear log de búsqueda de forma simple

        Args:
            client_id: UUID del cliente
            search_type: 'visual', 'text', 'gpt4v-unified'
            **kwargs: Campos opcionales del modelo
        """
        try:
            log = SearchLog(
                client_id=client_id,
                search_type=search_type,
                **kwargs
            )
            db.session.add(log)
            db.session.flush()  # Flush antes del commit para detectar errores de validación
            db.session.commit()
            log_info(f"✅ SearchLog guardado: client={client_id}, type={search_type}, results={kwargs.get('results_count', 0)}")
        except Exception as e:
            db.session.rollback()
            log_error(f"⚠️ ERROR guardando search log: {e}")
            log_error(f"   client_id={client_id}, search_type={search_type}")
            log_error(f"   kwargs={kwargs}")
            raise  # Re-lanzar la excepción para que se vea en los logs superiores

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'search_type': self.search_type,
            'query_text': self.query_text,
            'image_url': self.image_url,
            'categories_detected': self.categories_detected,
            'categories_matched': self.categories_matched,
            'categories_missing': self.categories_missing,
            'terms_extracted': self.terms_extracted,
            'terms_matched': self.terms_matched,
            'terms_unmatched': self.terms_unmatched,
            'results_count': self.results_count,
            'had_results': self.had_results,
            'response_time_ms': self.response_time_ms,
            'threshold_used': self.threshold_used,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
