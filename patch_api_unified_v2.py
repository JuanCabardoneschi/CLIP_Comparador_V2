"""
Script para modificar /api/search para usar Sistema Unificado V2 internamente.
Mantiene el mismo formato de respuesta para que el frontend no cambie.
"""

import re

API_FILE = r'C:\Personal\CLIP_Comparador_V2\clip_admin_backend\app\blueprints\api.py'

# Leer archivo
with open(API_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# ============= PATCH 1: MODO SINGLE =============
old_single = '''        # MODO SINGLE (original)
        railway_log(f" LOG: INICIANDO DETECCIÓN DE CATEGORÍA ESPECÍFICA (SINGLE MODE)")

        detected_category, category_confidence = detect_image_category_with_centroids(
            image_data,
            client.id,
            confidence_threshold=category_confidence_threshold  # Sensibilidad por cliente
        )'''

new_single = '''        # MODO SINGLE (original)
        # 🔧 MODIFICADO: Usar Sistema Unificado V2 por debajo (mantener respuesta igual)
        railway_log(f" LOG: INICIANDO DETECCIÓN DE CATEGORÍA ESPECÍFICA (SINGLE MODE - Sistema Unificado V2)")

        # 🚀 USAR SISTEMA UNIFICADO V2 EN LUGAR DEL VIEJO SISTEMA
        from app.blueprints.embeddings import detect_categories_centroid_based

        detected_results = detect_categories_centroid_based(
            image_data,
            client.id,
            threshold=category_confidence_threshold,
            top_k=1,  # Solo necesitamos la mejor
            apply_pair_exclusion=True
        )

        if not detected_results:
            detected_category = None
            category_confidence = 0.0
        else:
            from app.models.category import Category
            detected_category = Category.query.get(detected_results[0]['category_id'])
            category_confidence = detected_results[0]['score']'''

# Reemplazar (manejar caracteres especiales)
content_patched = content.replace(old_single, new_single)

if content == content_patched:
    print("❌ PATCH 1 (SINGLE MODE) no aplicado - no se encontró el texto exacto")
    print("Buscando variantes con caracteres especiales...")

    # Intentar con variantes de encoding
    for encoding_test in [old_single, old_single.replace('Ó', '\u00d3').replace('Í', '\u00cd')]:
        if encoding_test in content:
            content_patched = content.replace(encoding_test, new_single)
            print(f"✅ PATCH 1 aplicado con encoding alternativo")
            break
else:
    print("✅ PATCH 1 (SINGLE MODE) aplicado exitosamente")

# ============= PATCH 2: MODO MULTI =============
old_multi_search = '''            # Detectar múltiples categorías (thresholds hardcodeados)
            detected_categories = detect_multiple_categories(
                image_data,
                client.id,
                min_prob_threshold=0.03,
                min_conf_threshold=0.18,
                prelimit_topk=8
            )'''

new_multi = '''            # 🚀 USAR SISTEMA UNIFICADO V2: detect_categories_centroid_based
            from app.blueprints.embeddings import detect_categories_centroid_based

            detected_results = detect_categories_centroid_based(
                image_data,
                client.id,
                threshold=category_confidence_threshold,
                top_k=8,
                apply_pair_exclusion=True
            )

            # Convertir formato de Sistema Unificado V2 al formato legacy esperado
            detected_categories = []
            for result in detected_results:
                from app.models.category import Category
                category = Category.query.get(result['category_id'])
                if category:
                    detected_categories.append({
                        'category': category,
                        'confidence': result['score'],
                        'probability': 0.0,  # No usado en multi-category
                        'best_crop': result.get('best_crop', 'unknown'),
                        'crop_scores': result.get('crop_scores', {})
                    })

            print(f"✅ Sistema Unificado V2: {len(detected_categories)} categorías detectadas")'''

content_patched_2 = content_patched.replace(old_multi_search, new_multi)

if content_patched == content_patched_2:
    print("⚠️ PATCH 2 (MULTI MODE) no aplicado - posiblemente ya no existe o texto diferente")
else:
    print("✅ PATCH 2 (MULTI MODE) aplicado exitosamente")
    content_patched = content_patched_2

# Guardar archivo modificado
with open(API_FILE, 'w', encoding='utf-8') as f:
    f.write(content_patched)

print("\n" + "="*60)
print("✅ MODIFICACIÓN COMPLETADA")
print("="*60)
print(f"Archivo: {API_FILE}")
print("\nCambios aplicados:")
print("  1. Modo SINGLE ahora usa detect_categories_centroid_based()")
print("  2. Modo MULTI ahora usa detect_categories_centroid_based()")
print("\nEl formato de respuesta se mantiene idéntico.")
print("El frontend (demo-store.html) NO necesita cambios.")
print("\n🔄 Reinicia Flask para aplicar los cambios.")
