#!/usr/bin/env python3
"""
Sincronizar campos CLIP de categorías desde Eve's Store hacia Test Clip (TiendaNube).
Versión usando SQL directo via railway_db_tool.
"""

import psycopg2
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# IDs de clientes
EVE_STORE_ID = '57fc482f-2776-4816-b231-57d3c57348de'
TEST_CLIP_ID = '747ff760-8eae-46e8-94ca-8ad076370316'

# Conexión Railway
RAILWAY_URL = 'postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway'

def sync_category_fields():
    """Sincronizar campos CLIP desde Eve's Store hacia Test Clip."""

    conn = psycopg2.connect(RAILWAY_URL)
    cur = conn.cursor()

    # Obtener categorías de Eve's Store
    cur.execute("""
        SELECT id, name, name_en, clip_prompt, vision_hint, visual_features, alternative_terms
        FROM categories
        WHERE client_id = %s
        ORDER BY name
    """, (EVE_STORE_ID,))

    eve_categories = cur.fetchall()
    logger.info(f"📚 Encontradas {len(eve_categories)} categorías en Eve's Store")

    # Obtener categorías de Test Clip
    cur.execute("""
        SELECT id, name, name_en, clip_prompt, vision_hint, visual_features, alternative_terms
        FROM categories
        WHERE client_id = %s
        ORDER BY name
    """, (TEST_CLIP_ID,))

    tn_categories = cur.fetchall()
    logger.info(f"📚 Encontradas {len(tn_categories)} categorías en Test Clip\n")

    # Crear mapeo por nombre normalizado
    tn_map = {
        row[1].lower().strip(): row
        for row in tn_categories
    }

    synced = 0
    not_found = []

    for eve_cat in eve_categories:
        eve_id, eve_name, eve_name_en, eve_prompt, eve_hint, eve_visual, eve_alt_terms = eve_cat

        # Buscar categoría equivalente en Test Clip
        normalized_name = eve_name.lower().strip()
        tn_cat = tn_map.get(normalized_name)

        if not tn_cat:
            not_found.append(eve_name)
            logger.warning(f"⚠️  '{eve_name}' no encontrada en Test Clip")
            continue

        tn_id, tn_name, tn_name_en, tn_prompt, tn_hint, tn_visual, tn_alt_terms = tn_cat

        # Construir UPDATE dinámico
        updates = []
        params = []
        changes = []

        if eve_name_en and eve_name_en != tn_name_en:
            updates.append("name_en = %s")
            params.append(eve_name_en)
            changes.append(f"name_en='{eve_name_en}'")

        if eve_prompt and eve_prompt != tn_prompt:
            updates.append("clip_prompt = %s")
            params.append(eve_prompt)
            changes.append(f"clip_prompt='{eve_prompt[:50]}...'")

        if eve_hint and eve_hint != tn_hint:
            updates.append("vision_hint = %s")
            params.append(eve_hint)
            changes.append(f"vision_hint='{eve_hint}'")

        if eve_visual and eve_visual != tn_visual:
            updates.append("visual_features = %s")
            params.append(json.dumps(eve_visual))
            changes.append(f"visual_features={list(eve_visual.keys()) if eve_visual else None}")

        if eve_alt_terms and eve_alt_terms != tn_alt_terms:
            updates.append("alternative_terms = %s")
            params.append(eve_alt_terms)
            changes.append(f"alternative_terms='{eve_alt_terms}'")

        if updates:
            # Ejecutar UPDATE
            sql = f"""
                UPDATE categories
                SET {', '.join(updates)}, updated_at = NOW()
                WHERE id = %s
            """
            params.append(tn_id)

            cur.execute(sql, params)
            conn.commit()

            synced += 1
            logger.info(f"✅ '{eve_name}' → {', '.join(changes)}")
        else:
            logger.info(f"⏭️  '{eve_name}' ya está sincronizada")

    # Resumen
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

    cur.close()
    conn.close()

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
