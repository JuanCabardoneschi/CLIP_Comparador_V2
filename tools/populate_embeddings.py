"""
Script para poblar la tabla embeddings con todos los colores y categorías activas.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../clip_admin_backend')))

import json
import uuid
from app import db
from app.models.category import Category
from app.models.embedding import Embedding
from app.models.client import Client
from app.utils.llm_query_normalizer import get_model, normalize_query
from dotenv import load_dotenv

# Cargar variables de entorno desde .env.local
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env.local'))

# --- Configuración ---
os.environ['FLASK_ENV'] = 'development'

# --- Poblar categorías ---
def populate_category_embeddings():
    llm_model = get_model()
    for client in Client.query.all():
        for category in Category.query.filter_by(client_id=client.id).all():
            key = f"category:{client.id}:{category.name.lower()}"
            emb = llm_model.encode(category.name.lower(), convert_to_tensor=False)
            emb_json = json.dumps([float(x) for x in emb])
            exists = Embedding.query.filter_by(key=key, type="category").first()
            if not exists:
                db.session.add(Embedding(
                    id=str(uuid.uuid4()),
                    key=key,
                    embedding=emb_json,
                    type="category"
                ))
    db.session.commit()
    print("Embeddings de categorías generados.")

# --- Poblar colores ---
def populate_color_embeddings():
    # Colores típicos, podés ampliar la lista
    colores = [
        "blanco", "negro", "rojo", "azul", "verde", "amarillo", "gris", "marrón", "beige", "celeste", "naranja", "violeta", "rosa"
    ]
    for color in colores:
        key = f"color:{color.lower()}"
        result = normalize_query(color)
        emb = result.get('embedding')
        if emb:
            emb_json = json.dumps([float(x) for x in emb])
            exists = Embedding.query.filter_by(key=key, type="color").first()
            if not exists:
                db.session.add(Embedding(
                    id=str(uuid.uuid4()),
                    key=key,
                    embedding=emb_json,
                    type="color"
                ))
    db.session.commit()
    print("Embeddings de colores generados.")

if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        populate_category_embeddings()
        populate_color_embeddings()
