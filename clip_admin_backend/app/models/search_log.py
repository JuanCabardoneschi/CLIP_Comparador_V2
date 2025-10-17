from datetime import datetime
from .. import db
import uuid

class SearchLog(db.Model):
    """Modelo para registrar búsquedas realizadas por los clientes"""
    __tablename__ = 'search_logs'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)
    query_type = db.Column(db.String(50), nullable=False)  # 'text', 'image'
    query_data = db.Column(db.Text)  # JSON con datos de la consulta
    results_count = db.Column(db.Integer, default=0)
    response_time = db.Column(db.Float)  # tiempo en segundos
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con client
    client = db.relationship('Client', backref='search_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'query_type': self.query_type,
            'query_data': self.query_data,
            'results_count': self.results_count,
            'response_time': self.response_time,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
