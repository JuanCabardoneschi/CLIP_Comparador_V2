from app import db
import uuid

class Embedding(db.Model):
    __tablename__ = 'embeddings'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = db.Column(db.String(128), unique=True, nullable=False)  # Ej: "color:blanco", "category:camisas"
    embedding = db.Column(db.Text, nullable=False)  # JSON string: [float, float, ...]
    type = db.Column(db.String(32), nullable=False)  # "color" | "category"
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f"<Embedding {self.key} ({self.type})>"
