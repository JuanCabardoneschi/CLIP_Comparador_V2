"""
Modelo para configuración de atributos de productos por cliente
"""
from .. import db

class ProductAttributeConfig(db.Model):
    __tablename__ = 'product_attribute_config'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)
    key = db.Column(db.String(100), nullable=False)  # nombre interno del campo
    label = db.Column(db.String(200), nullable=False)  # etiqueta para mostrar
    type = db.Column(db.String(20), nullable=False)  # text, number, date, list, url
    required = db.Column(db.Boolean, default=False)
    options = db.Column(db.JSON, nullable=True)  # solo para type='list', lista de opciones
    field_order = db.Column(db.Integer, default=0)  # para ordenar los campos en el formulario
    expose_in_search = db.Column(db.Boolean, default=False)  # incluir en respuestas de búsqueda

    def __repr__(self):
        return f"<ProductAttributeConfig {self.key} ({self.type})>"
