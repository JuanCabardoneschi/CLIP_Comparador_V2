"""Servicio de lógica para el módulo de entrenamiento visual.
Iteraciones 1 y 2.
"""
from typing import List, Dict, Any
from app import db
from app.models.training import TrainingEvent, ClientCategoryVariant
from app.models.image import Image
import json
import numpy as np


def log_training_event(client_id: str, category_id: str, query_image_ref: str,
                       topk_results: List[Dict[str, Any]], positives: List[str],
                       negatives: List[str], variant_key: str | None) -> TrainingEvent:
    event = TrainingEvent(
        client_id=client_id,
        category_id=category_id,
        query_image_ref=query_image_ref,
        topk_results=topk_results,
        positives=positives,
        negatives=negatives,
        variant_key=variant_key
    )
    db.session.add(event)
    db.session.commit()
    return event


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


def recompute_variants(client_id: str, category_id: str) -> Dict[str, Any]:
    from flask import current_app
    print(f"🔄 RECOMPUTE_VARIANTS: Iniciando para client={client_id}, category={category_id}")
    current_app.logger.info(f"🔄 RECOMPUTE_VARIANTS: Iniciando para client={client_id}, category={category_id}")

    events = TrainingEvent.query.filter_by(client_id=client_id, category_id=category_id).all()
    print(f"📊 Encontrados {len(events)} training events")
    current_app.logger.info(f"📊 Encontrados {len(events)} training events")

    grouped: Dict[str, List[str]] = {}
    for ev in events:
        if not ev.variant_key:
            continue
        grouped.setdefault(ev.variant_key, [])
        grouped[ev.variant_key].extend(ev.positives)

    print(f"📦 Variants agrupados: {list(grouped.keys())}")
    current_app.logger.info(f"📦 Variants agrupados: {list(grouped.keys())}")

    updated = []
    for variant_key, product_ids in grouped.items():
        unique_ids = list(set(product_ids))
        print(f"🎯 Procesando variant '{variant_key}' con {len(unique_ids)} productos únicos")
        current_app.logger.info(f"🎯 Procesando variant '{variant_key}' con {len(unique_ids)} productos únicos")

        embeddings = _fetch_product_image_embeddings(unique_ids)
        print(f"📐 Obtenidos {len(embeddings)} embeddings para variant '{variant_key}'")
        current_app.logger.info(f"📐 Obtenidos {len(embeddings)} embeddings para variant '{variant_key}'")

        if not embeddings:
            print(f"⚠️  VARIANT SKIPPED: '{variant_key}' - NO tiene embeddings")
            current_app.logger.warning(f"⚠️  VARIANT SKIPPED: '{variant_key}' - NO tiene embeddings")
            continue

        centroid = np.mean(np.vstack(embeddings), axis=0)
        centroid = centroid / np.linalg.norm(centroid)

        variant = ClientCategoryVariant.query.filter_by(
            client_id=client_id,
            category_id=category_id,
            variant_key=variant_key
        ).first()

        if not variant:
            print(f"✨ Creando NUEVO variant '{variant_key}'")
            current_app.logger.info(f"✨ Creando NUEVO variant '{variant_key}'")
            variant = ClientCategoryVariant(
                client_id=client_id,
                category_id=category_id,
                variant_key=variant_key,
                name=variant_key,
                centroid_embedding=json.dumps(centroid.tolist()),
                support_count=len(embeddings),
                prompts=[]
            )
            db.session.add(variant)
        else:
            print(f"🔄 Actualizando variant existente '{variant_key}'")
            current_app.logger.info(f"🔄 Actualizando variant existente '{variant_key}'")
            variant.centroid_embedding = json.dumps(centroid.tolist())
            variant.support_count = len(embeddings)
        updated.append(variant_key)

    db.session.commit()
    print(f"✅ RECOMPUTE completado: {len(updated)} variants actualizados - {updated}")
    current_app.logger.info(f"✅ RECOMPUTE completado: {len(updated)} variants actualizados")
    return {'updated_variants': updated, 'variant_count': len(updated)}


def list_variants(client_id: str, category_id: str) -> List[Dict[str, Any]]:
    variants = ClientCategoryVariant.get_active_variants(client_id, category_id)
    return [v.to_dict() for v in variants]


def upsert_variant(client_id: str, category_id: str, variant_key: str, name: str,
                   active: bool = True, prompts: List[str] | None = None) -> Dict[str, Any]:
    variant = ClientCategoryVariant.query.filter_by(
        client_id=client_id,
        category_id=category_id,
        variant_key=variant_key
    ).first()
    if not variant:
        variant = ClientCategoryVariant(
            client_id=client_id,
            category_id=category_id,
            variant_key=variant_key,
            name=name,
            prompts=prompts or []
        )
        db.session.add(variant)
    else:
        variant.name = name
        variant.active = active
        if prompts is not None:
            variant.prompts = prompts
    db.session.commit()
    return variant.to_dict()
