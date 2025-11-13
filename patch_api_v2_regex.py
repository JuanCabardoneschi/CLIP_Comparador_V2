"""
Script v2: Usa regex para manejar caracteres especiales en español
"""

import re

API_FILE = r'C:\Personal\CLIP_Comparador_V2\clip_admin_backend\app\blueprints\api.py'

# Leer archivo
with open(API_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

original_content = content

# ============= PATCH 1: MODO SINGLE (usando regex para evitar problemas de encoding) =============
# Buscar el patrón: detect_image_category_with_centroids(
pattern_single = re.compile(
    r'(\s+# MODO SINGLE.*?\n'
    r'\s+railway_log.*?SINGLE MODE.*?\n'
    r'\s*\n'
    r'\s+detected_category, category_confidence = detect_image_category_with_centroids\(\n'
    r'\s+image_data,\n'
    r'\s+client\.id,\n'
    r'\s+confidence_threshold=category_confidence_threshold.*?\n'
    r'\s+\))',
    re.DOTALL | re.MULTILINE
)

replacement_single = r'''        # MODO SINGLE (original)
        # 🔧 MODIFICADO: Usar Sistema Unificado V2 por debajo (mantener respuesta igual)
        railway_log(f" LOG: INICIANDO DETECCIÓN DE CATEGORÍA (SINGLE MODE - Sistema Unificado V2)")

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

content, count1 = pattern_single.subn(replacement_single, content, count=1)

if count1 > 0:
    print(f"✅ PATCH 1 (SINGLE MODE) aplicado ({count1} reemplazo)")
else:
    print("❌ PATCH 1 (SINGLE MODE) NO aplicado - patrón no encontrado")

# ============= PATCH 2: MODO MULTI =============
pattern_multi = re.compile(
    r'(\s+# Detectar m.ltiples categor.as.*?\n'
    r'\s+detected_categories = detect_multiple_categories\(\n'
    r'\s+image_data,\n'
    r'\s+client\.id,\n'
    r'\s+min_prob_threshold=.*?,\n'
    r'\s+min_conf_threshold=.*?,\n'
    r'\s+prelimit_topk=.*?\n'
    r'\s+\))',
    re.DOTALL | re.MULTILINE
)

replacement_multi = '''            # 🚀 USAR SISTEMA UNIFICADO V2: detect_categories_centroid_based
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
                        'probability': 0.0,
                        'best_crop': result.get('best_crop', 'unknown'),
                        'crop_scores': result.get('crop_scores', {})
                    })

            print(f"✅ Sistema Unificado V2: {len(detected_categories)} categorías detectadas")'''

content, count2 = pattern_multi.subn(replacement_multi, content, count=1)

if count2 > 0:
    print(f"✅ PATCH 2 (MULTI MODE) aplicado ({count2} reemplazo)")
else:
    print("⚠️ PATCH 2 (MULTI MODE) NO aplicado")

# Solo guardar si hubo cambios
if content != original_content:
    with open(API_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print("\n" + "="*70)
    print("✅ ARCHIVO MODIFICADO EXITOSAMENTE")
    print("="*70)
    print(f"Total de patches aplicados: {count1 + count2}")
    print("\n🔄 REINICIA FLASK para aplicar los cambios:")
    print("   1. Ctrl+C en la terminal de Flask")
    print("   2. cd clip_admin_backend && python app.py")
else:
    print("\n⚠️ No se realizaron cambios (patches ya aplicados o patrones no encontrados)")
