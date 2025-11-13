#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Patch directo por líneas para unificar detección multi-categoría en /api/search
"""

# Leer archivo original
with open('clip_admin_backend/app/blueprints/api.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Encontrar y reemplazar líneas 2218-2229 (0-indexed: 2217-2228)
# Buscamos el comentario "BUSCAR SOLO EN LA CATEGORIA DETECTADA"
start_marker = None
for i, line in enumerate(lines):
    if 'BUSCAR SOLO EN LA CATEGOR' in line:
        start_marker = i
        break

if start_marker is None:
    print("❌ No se encontró el marcador de inicio")
    exit(1)

print(f"✅ Encontrado marcador en línea {start_marker + 1}")

# Reemplazar desde start_marker hasta donde termina el bloque (hasta "NO APLICAR BOOST")
end_marker = None
for i in range(start_marker, min(start_marker + 30, len(lines))):
    if 'NO APLICAR BOOST NI METADATA' in lines[i]:
        end_marker = i
        break

if end_marker is None:
    print("❌ No se encontró el marcador de fin")
    exit(1)

print(f"✅ Encontrado marcador fin en línea {end_marker + 1}")

# Nuevo bloque de código
new_lines = [
    "\n",
    "        # ===== BUSCAR EN TODAS LAS CATEGORÍAS DETECTADAS (como multicrop) =====\n",
    "        railway_log(f\" LOG: Buscando productos en {len(detected_results)} categorías detectadas\")\n",
    "\n",
    "        # Acumular productos de todas las categorías detectadas\n",
    "        product_best_match_global = {}\n",
    "\n",
    "        for cat_result in detected_results:\n",
    "            from app.models.category import Category\n",
    "            cat = Category.query.get(cat_result['category_id'])\n",
    "            if not cat:\n",
    "                continue\n",
    "\n",
    "            railway_log(f\" LOG: → Buscando en {cat.name} (score={cat_result['score']:.3f})\")\n",
    "\n",
    "            # Buscar productos en esta categoría\n",
    "            product_best_match_cat = _find_similar_products_in_category(\n",
    "                client,\n",
    "                query_embedding,\n",
    "                product_similarity_threshold,\n",
    "                cat.id\n",
    "            )\n",
    "\n",
    "            # Agregar al global (sin duplicados, conservando el mejor score)\n",
    "            for prod_id, match_data in product_best_match_cat.items():\n",
    "                if prod_id not in product_best_match_global:\n",
    "                    product_best_match_global[prod_id] = match_data\n",
    "                elif match_data['similarity'] > product_best_match_global[prod_id]['similarity']:\n",
    "                    product_best_match_global[prod_id] = match_data\n",
    "\n",
    "        product_best_match = product_best_match_global\n",
    "        print(f\"🎯 DEBUG: Total productos encontrados en TODAS las categorías: {len(product_best_match)}\")\n",
    "\n"
]

# Reemplazar líneas
lines[start_marker:end_marker] = new_lines

# Guardar archivo modificado
with open('clip_admin_backend/app/blueprints/api.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"✅ Reemplazadas líneas {start_marker + 1} a {end_marker}")
print("\n📌 Cambios aplicados:")
print("  - /api/search ahora busca en TODAS las categorías detectadas")
print("  - Igual que multicrop: detecta N categorías y busca productos en cada una")
print("  - Mantiene backward compatibility")
