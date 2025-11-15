"""
Pre-carga el caché de vocabulario por cliente en la tabla client_vocabulary_cache (local).

Uso:
    python tools/populate_vocabulary_cache.py [--client CLIENT_ID]

- Si no se pasa --client, procesa todos los clientes activos.
- Realiza UPSERT por client_id.

Requisitos:
- PostgreSQL local configurado (.env.local)
- Ejecutar previamente la migración: migrations/20251115_add_client_vocabulary_cache.sql
"""
import os
import json
import time
import argparse
from datetime import datetime

from sqlalchemy import text

# Asegurar imports del app
import sys
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(PROJECT_ROOT)

# Cargar variables de entorno locales
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env.local'))

from sentence_transformers import SentenceTransformer

from clip_admin_backend.app import create_app  # factory
from clip_admin_backend.app import db
from clip_admin_backend.app.models import Client


def _build_vocabulary_from_db(client_id: str) -> dict:
    """Construye el vocabulario del cliente consultando productos/tags vía SQL directo.
    - Colores: heurística simple desde tags y atributos (si estuvieran)
    - Tipos: categorías y/o términos frecuentes
    - Contextos: tags normalizados únicos
    """
    vocabulary = {
        'colores': set(),
        'tipos': set(),
        'contextos': set(),
    }

    # 1) Extraer tags únicos (normalizados) desde products.tags
    tag_rows = db.session.execute(
        text(
            """
            SELECT DISTINCT UNNEST(string_to_array(tags, ',')) as tag
            FROM products
            WHERE client_id = :client_id
              AND tags IS NOT NULL
              AND tags <> ''
            """
        ),
        {"client_id": str(client_id)}
    ).fetchall()

    def _norm(s: str) -> str:
        s = (s or '').strip().lower()
        # limpieza simple
        return ''.join(ch for ch in s if ch.isalnum() or ch in [' ', '-']).strip()

    for row in tag_rows:
        tag = _norm(row[0]) if row and row[0] else None
        if tag and len(tag) > 2:
            vocabulary['contextos'].add(tag)

    # 2) Extraer posibles tipos desde categorías con productos activos
    cat_rows = db.session.execute(
        text(
            """
            SELECT DISTINCT c.name
            FROM categories c
            JOIN products p ON p.category_id = c.id
            WHERE c.client_id = :client_id AND p.is_active = TRUE
            """
        ),
        {"client_id": str(client_id)}
    ).fetchall()

    for row in cat_rows:
        if row and row[0]:
            vocabulary['tipos'].add(_norm(row[0]))

    # 3A) Colores desde ProductAttributeConfig (key='color', type='list')
    try:
        color_config_rows = db.session.execute(
            text(
                """
                SELECT options
                FROM product_attribute_config
                WHERE client_id = :client_id
                  AND key = 'color'
                  AND type = 'list'
                """
            ),
            {"client_id": str(client_id)}
        ).fetchall()

        for row in color_config_rows:
            if row and row[0]:
                options_data = row[0]
                # options puede ser dict JSONB con 'values'
                if isinstance(options_data, dict) and 'values' in options_data:
                    for color in options_data['values']:
                        if color and len(color) > 2:
                            vocabulary['colores'].add(_norm(color))
    except Exception as e:
        print(f"⚠️ Error extrayendo colores desde ProductAttributeConfig: {e}")

    # 3B) Colores desde products.attributes->>'color'
    try:
        product_color_rows = db.session.execute(
            text(
                """
                SELECT DISTINCT TRIM(LOWER(attributes->>'color')) as color
                FROM products
                WHERE client_id = :client_id
                  AND attributes ? 'color'
                  AND TRIM(attributes->>'color') <> ''
                """
            ),
            {"client_id": str(client_id)}
        ).fetchall()

        for row in product_color_rows:
            if row and row[0]:
                vocabulary['colores'].add(_norm(row[0]))
    except Exception as e:
        print(f"⚠️ Error extrayendo colores desde products.attributes: {e}")

    # 3C) Colores básicos desde tags (heurística de respaldo)
    COLORES_BASICOS = {
        'rojo','azul','verde','amarillo','negro','blanco','gris','rosa','morado','naranja','marron','beige','celeste','turquesa','dorado','plateado','violeta','cafe','crema','coral','fucsia'
    }
    for t in list(vocabulary['contextos']):
        tok = t.split(' ')
        for w in tok:
            if w in COLORES_BASICOS:
                vocabulary['colores'].add(w)

    return {
        'colores': sorted(list(vocabulary['colores'])),
        'tipos': sorted(list(vocabulary['tipos'])),
        'contextos': sorted(list(vocabulary['contextos'])),
    }


def upsert_client_vocabulary(client_id: str, vocabulary: dict):
    db.session.execute(
        text(
            """
            INSERT INTO client_vocabulary_cache (client_id, vocabulary, updated_at)
            VALUES (:cid, CAST(:vocab AS JSONB), NOW())
            ON CONFLICT (client_id)
            DO UPDATE SET vocabulary = CAST(:vocab AS JSONB), updated_at = NOW()
            """
        ),
        {"cid": str(client_id), "vocab": json.dumps(vocabulary)}
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--client', dest='client_id', help='UUID del cliente a procesar solo')
    args = parser.parse_args()

    # Cargar modelo de embeddings
    print("⏳ Cargando modelo de embeddings...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    print("✅ Modelo cargado")

    app = create_app()
    with app.app_context():
        if args.client_id:
            clients = Client.query.filter(Client.id == args.client_id).all()
        else:
            clients = Client.query.filter_by(is_active=True).all()

        print(f"Procesando {len(clients)} cliente(s)...")
        t0 = time.time()
        for cli in clients:
            c0 = time.time()
            vocab = _build_vocabulary_from_db(str(cli.id))

            # Calcular embeddings de colores
            if vocab['colores']:
                print(f"   🎨 Calculando embeddings para {len(vocab['colores'])} colores...")
                color_embs = model.encode(vocab['colores'])
                vocab['color_embeddings'] = {
                    color: emb.tolist() for color, emb in zip(vocab['colores'], color_embs)
                }
            else:
                vocab['color_embeddings'] = {}

            upsert_client_vocabulary(str(cli.id), vocab)
            db.session.commit()
            print(f" - {cli.name}: tipos={len(vocab['tipos'])} contextos={len(vocab['contextos'])} colores={len(vocab['colores'])} (con embeddings) en {time.time()-c0:.2f}s")

        print(f"Hecho en {time.time()-t0:.2f}s")


if __name__ == '__main__':
    main()
