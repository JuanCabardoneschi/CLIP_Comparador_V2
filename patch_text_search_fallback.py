"""
Script para eliminar fallbacks y agregar análisis de calidad de match en text_search
"""

# Leer archivo
with open('clip_admin_backend/app/blueprints/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Buscar inicio del fallback 2
fallback_start = content.find("# Fallback 2: Si tras el scoring no hay resultados")
if fallback_start == -1:
    print("❌ No se encontró el fallback 2")
    exit(1)

# Buscar el final del fallback (antes de "print(f"✅ TEXT SEARCH:")
fallback_end = content.find('print(f"✅ TEXT SEARCH: {len(results)} resultados', fallback_start)
if fallback_end == -1:
    print("❌ No se encontró el final del fallback")
    exit(1)

# Código de reemplazo
replacement = '''# === ANÁLISIS DE CALIDAD DE MATCH ===
        match_quality = "exact"
        partial_match_info = None
        detected_attributes = {}

        if detected_color:
            detected_attributes['color'] = detected_color
        if detected_tipo:
            detected_attributes['tipo'] = detected_tipo

        if detected_category and results:
            # Analizar calidad del match si se detectó categoría
            best_result = results[0]
            best_color_sim = best_result.get('color_similarity', 0.0)
            best_attr_boost = best_result.get('attr_boost', 0.0)

            # Umbrales para clasificación
            COLOR_EXACT_THRESHOLD = 0.75
            COLOR_PARTIAL_THRESHOLD = 0.45
            ATTR_EXACT_THRESHOLD = 0.4

            # Determinar calidad de match
            has_exact_color = detected_color and best_color_sim >= COLOR_EXACT_THRESHOLD
            has_partial_color = detected_color and best_color_sim >= COLOR_PARTIAL_THRESHOLD
            has_good_attrs = best_attr_boost >= ATTR_EXACT_THRESHOLD

            if detected_color and not has_exact_color:
                # Color solicitado pero no encontrado con precisión
                match_quality = "partial" if has_partial_color else "poor"

                # Obtener colores disponibles en la categoría
                available_colors = set()
                for res in results[:10]:  # Analizar top 10
                    attrs = res.get('attributes', {})
                    if isinstance(attrs, dict):
                        for key in ['color', 'colour', 'color_principal']:
                            if key in attrs and attrs[key]:
                                available_colors.add(str(attrs[key]).lower())

                # Construir mensaje contextual
                cat_name = detected_category.name.lower()
                missing_attrs = []
                if detected_color:
                    missing_attrs.append(f"color: {detected_color}")

                if match_quality == "partial":
                    message = f"No encontramos {cat_name} en {detected_color} exacto. Te mostramos las opciones más cercanas."
                else:
                    message = f"No tenemos {cat_name} en {detected_color}. Te mostramos otras {cat_name} disponibles."

                if available_colors:
                    colors_list = ', '.join(sorted(available_colors)[:5])
                    suggestions = f"Tenemos {cat_name} en: {colors_list}"
                else:
                    suggestions = f"Explora otras opciones de {cat_name}"

                partial_match_info = {
                    "message": message,
                    "missing_attributes": missing_attrs,
                    "best_color_similarity": round(best_color_sim, 3),
                    "available_colors": sorted(list(available_colors))[:10],
                    "suggestions": suggestions
                }

                print(f"🎨 PARTIAL MATCH: {message}")
                print(f"   Colores disponibles: {available_colors}")

            elif not has_good_attrs and detected_tipo:
                # Tipo detectado pero atributos débiles
                match_quality = "partial"
                partial_match_info = {
                    "message": f"Resultados aproximados para '{query_text}'. Los productos pueden no coincidir exactamente.",
                    "best_attr_score": round(best_attr_boost, 3),
                    "suggestions": f"Intenta ser más específico en tu búsqueda"
                }

        elif detected_category and len(results) == 0:
            # Categoría detectada pero SIN resultados (data gap)
            match_quality = "none"
            cat_name = detected_category.name.lower()

            # Construir mensaje de "sin stock"
            if detected_color:
                message = f"No tenemos {cat_name} en {detected_color} disponibles actualmente."
            else:
                message = f"No tenemos {cat_name} disponibles actualmente."

            partial_match_info = {
                "message": message,
                "category_detected": detected_category.name,
                "products_in_category": 0,
                "suggestions": "Intenta con otra categoría o contacta con el equipo de ventas."
            }
            print(f"❌ NO RESULTS: {message}")

        '''

# Reemplazar
new_content = content[:fallback_start] + replacement + content[fallback_end:]

# Actualizar el response para incluir nuevos campos
response_start = new_content.find('response = {', fallback_start)
old_response = '''response = {
            "success": True,
            "query": query_text,
            "detected_category": {
                "id": str(detected_category.id),
                "name": detected_category.name,
                "name_en": detected_category.name_en
            } if detected_category else None,
            "results": results,
            "total_products_analyzed": len(products),
            "search_time_seconds": round(elapsed_time, 3)
        }'''

new_response = '''response = {
            "success": True,
            "query": query_text,
            "detected_category": {
                "id": str(detected_category.id),
                "name": detected_category.name,
                "name_en": detected_category.name_en
            } if detected_category else None,
            "detected_attributes": detected_attributes,
            "match_quality": match_quality,
            "results": results,
            "total_products_analyzed": len(products),
            "search_time_seconds": round(elapsed_time, 3)
        }

        # Agregar info de match parcial si existe
        if partial_match_info:
            response['partial_match_info'] = partial_match_info'''

new_content = new_content.replace(old_response, new_response)

# Guardar
with open('clip_admin_backend/app/blueprints/api.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ Fallback eliminado y análisis de calidad agregado")
