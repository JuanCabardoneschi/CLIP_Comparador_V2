# Modelo Cliente
import uuid
from datetime import datetime
from slugify import slugify
from . import db

class Client(db.Model):
    __tablename__ = "clients"

    # Usar String en lugar de UUID para compatibilidad con SQLite
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    industry = db.Column(db.String(100), default='general')  # Rubro/Industria del cliente
    # description = db.Column(db.Text)  # COMENTADO: Esta columna no existe en la BD real
    is_active = db.Column(db.Boolean, default=True)
    api_key = db.Column(db.String(100), unique=True, nullable=True)  # API Key del cliente
    api_settings = db.Column(db.Text, default='{}')  # Columna que existe en la BD real
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # COMENTADO: No existe la tabla api_keys en la base de datos real
    # api_keys = db.relationship('APIKey', backref='client', lazy=True)

    def __repr__(self):
        return f"<Client {self.name}>"

# COMENTADO: No existe la tabla api_keys en la base de datos real
# class APIKey(db.Model):
#     __tablename__ = "api_keys"
#
#     # Usar String en lugar de UUID para compatibilidad con SQLite
#     id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
#     client_id = db.Column(db.String(36), db.ForeignKey("clients.id"))
#     name = db.Column(db.String(255), nullable=False)
#     key_hash = db.Column(db.String(255), unique=True, nullable=False)
#     is_active = db.Column(db.Boolean, default=True)
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
#
#     def __repr__(self):
#         return f"<APIKey {self.name}>"
