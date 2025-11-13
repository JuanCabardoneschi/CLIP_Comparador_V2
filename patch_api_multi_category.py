#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Patch para unificar detección de categorías en /api/search (demo-store.html)
Hace que use MULTI-CATEGORÍA como multicrop test, en lugar de SINGLE
"""

import sys

# Leer archivo
with open('clip_admin_backend/app/blueprints/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Buscar y reemplazar el bloque de búsqueda
old_block = """        # ===== BUSCAR SOLO EN LA CATEGORÍA DETECTADA =====
        railway_log(f" LOG: Buscando productos en {detected_category.name}")

        # Modificar la búsqueda para filtrar por categoría detectada
        product_best_match = _find_similar_products_in_category(
            client,
            query_embedding,
            product_similarity_threshold,
            detected_category.id
        )

        print(f"🎯 DEBUG: Productos encontrados en categoría {detected_category.name}: {len(product_best_match)}")"""

new_block = """        # ===== BUSCAR EN TODAS LAS CATEGORÍAS DETECTADAS (como multicrop) =====
        railway_log(f" LOG: Buscando productos en {len(detected_results)} categorías detectadas")

        # Acumular productos de todas las categorías detectadas
        product_best_match_global = {}

        for cat_result in detected_results:
            from app.models.category import Category
            cat = Category.query.get(cat_result['category_id'])
            if not cat:
                continue

            railway_log(f" LOG: → Buscando en {cat.name} (score={cat_result['score']:.3f})")

            # Buscar productos en esta categoría
            product_best_match_cat = _find_similar_products_in_category(
                client,
                query_embedding,
                product_similarity_threshold,
                cat.id
            )

            # Agregar al global (sin duplicados, conservando el mejor score)
            for prod_id, match_data in product_best_match_cat.items():
                if prod_id not in product_best_match_global:
                    product_best_match_global[prod_id] = match_data
                elif match_data['similarity'] > product_best_match_global[prod_id]['similarity']:
                    product_best_match_global[prod_id] = match_data

        product_best_match = product_best_match_global
        print(f"🎯 DEBUG: Total productos encontrados en TODAS las categorías: {len(product_best_match)}")"""

# Hacer reemplazo
if old_block in content:
    content = content.replace(old_block, new_block)
    print("✅ Reemplazo exitoso")
else:
    print("❌ No se encontró el bloque a reemplazar")
    sys.exit(1)

# Guardar
with open('clip_admin_backend/app/blueprints/api.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Archivo guardado correctamente")
print("\n📌 Cambios realizados:")
print("  - /api/search ahora detecta múltiples categorías (como multicrop)")
print("  - Busca productos en TODAS las categorías detectadas (no solo la primera)")
print("  - Mantiene backward compatibility en formato de respuesta")
