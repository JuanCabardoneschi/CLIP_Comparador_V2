"""DEPRECATED: Servicio de entrenamiento visual eliminado.
Este archivo permanece solo para compatibilidad y evitar import errors.
Todas las funciones levantarán NotImplementedError.
"""
from typing import List, Dict, Any
from app import db
raise ImportError("training_service removed: módulos de entrenamiento deshabilitados")
from app.models.training import TrainingEvent, ClientCategoryVariant  # type: ignore # pragma: no cover
from app.models.image import Image
import json
import numpy as np


def log_training_event(*args, **kwargs):
    raise NotImplementedError("training_service: log_training_event deshabilitado")


def _fetch_product_image_embeddings(product_ids: List[str]) -> List[np.ndarray]:
    from flask import current_app
    if not product_ids:
        return []

    current_app.logger.debug(f"🔍 Buscando embeddings para {len(product_ids)} productos")
    images = Image.query.filter(Image.product_id.in_(product_ids), Image.is_processed.is_(True)).all()
    current_app.logger.debug(f"📸 Encontradas {len(images)} imágenes procesadas")

    vectors = []
    for img in images:
        try:
            vec = img.embedding_vector
            if vec:
                arr = np.array(vec)
                arr = arr / np.linalg.norm(arr)
                vectors.append(arr)
                current_app.logger.debug(f"✅ Embedding OK para imagen {img.id}")
            else:
                current_app.logger.warning(f"⚠️  Imagen {img.id}: embedding_vector es None")
        except Exception as e:
            current_app.logger.error(f"❌ Error procesando imagen {img.id}: {e}")
            continue

    current_app.logger.debug(f"📦 Total vectors extraídos: {len(vectors)}")
    return vectors


def recompute_variants(*args, **kwargs):
    raise NotImplementedError("training_service: recompute_variants deshabilitado")


def list_variants(*args, **kwargs):
    raise NotImplementedError("training_service: list_variants deshabilitado")


def upsert_variant(*args, **kwargs):
    raise NotImplementedError("training_service: upsert_variant deshabilitado")
