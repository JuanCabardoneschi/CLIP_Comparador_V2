#!/usr/bin/env python3
"""
Sincronizar campos CLIP de categorías desde Eve's Store hacia Test Clip (TiendaNube).

Copia name_en, clip_prompt, vision_hint desde categorías de Eve's Store
hacia categorías equivalentes (mismo name/slug) en Test Clip.
"""

import sys
import os

# Agregar el path del backend al PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from app import create_app, db
from app.models.category import Category
from sqlalchemy.orm.attributes import flag_modified
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# IDs de clientes
EVE_STORE_ID = '6d55d2d9-4791-4ab7-b0da-13c6e38daab5'
TEST_CLIP_ID = '747ff760-8eae-46e8-94ca-8ad076370316'

def sync_category_fields():
    """Sincronizar campos CLIP desde Eve's Store hacia Test Clip."""

    app = create_app()

    with app.app_context():
        # Obtener todas las categorías de Eve's Store
        eve_categories = Category.query.filter_by(
            client_id=EVE_STORE_ID
        ).all()

        logger.info(f"📚 Encontradas {len(eve_categories)} categorías en Eve's Store")

        # Obtener todas las categorías de Test Clip
        tiendanube_categories = Category.query.filter_by(
            client_id=TEST_CLIP_ID
        ).all()

        logger.info(f"📚 Encontradas {len(tiendanube_categories)} categorías en Test Clip")

        # Crear mapeo por nombre normalizado
        tiendanube_map = {
            cat.name.lower().strip(): cat
            for cat in tiendanube_categories
        }

        synced = 0
        not_found = []

        for eve_cat in eve_categories:
            # Buscar categoría equivalente en Test Clip
            normalized_name = eve_cat.name.lower().strip()
            tn_cat = tiendanube_map.get(normalized_name)

            if not tn_cat:
                not_found.append(eve_cat.name)
                logger.warning(f"⚠️  '{eve_cat.name}' no encontrada en Test Clip")
                continue

            # Verificar si necesita actualización
            needs_update = False
            changes = []

            if eve_cat.name_en and tn_cat.name_en != eve_cat.name_en:
                tn_cat.name_en = eve_cat.name_en
                needs_update = True
                changes.append(f"name_en='{eve_cat.name_en}'")

            if eve_cat.clip_prompt and tn_cat.clip_prompt != eve_cat.clip_prompt:
                tn_cat.clip_prompt = eve_cat.clip_prompt
                needs_update = True
                changes.append(f"clip_prompt='{eve_cat.clip_prompt}'")

            if eve_cat.vision_hint and tn_cat.vision_hint != eve_cat.vision_hint:
                tn_cat.vision_hint = eve_cat.vision_hint
                needs_update = True
                changes.append(f"vision_hint='{eve_cat.vision_hint}'")

            # Copiar visual_features si existe
            if eve_cat.visual_features and tn_cat.visual_features != eve_cat.visual_features:
                tn_cat.visual_features = eve_cat.visual_features
                flag_modified(tn_cat, 'visual_features')
                needs_update = True
                changes.append(f"visual_features={list(eve_cat.visual_features.keys())}")

            if needs_update:
                db.session.commit()
                synced += 1
                logger.info(f"✅ '{eve_cat.name}' → {', '.join(changes)}")
            else:
                logger.info(f"⏭️  '{eve_cat.name}' ya está sincronizada")

        logger.info(f"\n" + "="*60)
        logger.info(f"📊 RESUMEN:")
        logger.info(f"  ✅ Sincronizadas: {synced}")
        logger.info(f"  ⏭️  Sin cambios: {len(eve_categories) - synced - len(not_found)}")
        logger.info(f"  ⚠️  No encontradas: {len(not_found)}")

        if not_found:
            logger.info(f"\n❌ Categorías de Eve's Store sin equivalente en Test Clip:")
            for name in not_found:
                logger.info(f"   - {name}")

        logger.info("="*60)

        return synced, not_found

if __name__ == '__main__':
    logger.info("🚀 Iniciando sincronización de campos CLIP...")
    logger.info(f"   Origen: Eve's Store ({EVE_STORE_ID})")
    logger.info(f"   Destino: Test Clip ({TEST_CLIP_ID})")
    logger.info("")

    try:
        synced, not_found = sync_category_fields()

        if synced > 0:
            logger.info(f"\n✅ Proceso completado exitosamente")
            logger.info(f"   {synced} categorías actualizadas en Railway")
        else:
            logger.info(f"\n⚠️  No se realizaron cambios")

    except Exception as e:
        logger.error(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
