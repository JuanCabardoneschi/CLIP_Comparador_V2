#!/usr/bin/env python3
"""
Script robusto para eliminar Fallback 2 y agregar análisis de calidad de match
Usa enfoque de líneas en lugar de búsqueda de strings
"""

# Configuración
API_FILE = "clip_admin_backend/app/blueprints/api.py"
FALLBACK_START = 2787  # Línea "# Fallback 2: Si tras el scoring no hay resultados..."
FALLBACK_END = 2874    # Última línea del fallback (antes del print final)

# Código nuevo a insertar
NEW_QUALITY_ANALYSIS = '''
        # 🎯 Análisis de calidad de match en lugar de fallback global
        # En vez de reintentar globalmente, analizamos QUÉ encontramos y damos contexto al usuario

        if len(results) == 0:
            # No hay resultados - analizar por qué y dar feedback útil
            match_quality = "none"

            # Verificar si la categoría existe pero está vacía
            if detected_category:
                category_product_count = len([p for p in all_client_products if p.category_id == detected_category.id])
                if category_product_count == 0:
                    partial_match_info = {
                        "message": f"No tenemos productos en la categoría '{detected_category.name}' actualmente.",
                        "suggestion": "Intenta buscar en otras categorías o consulta nuestro catálogo completo.",
                        "reason": "empty_category"
                    }
                else:
                    # Categoría tiene productos pero ninguno matcheó - problema de atributos/color
                    partial_match_info = {
                        "message": f"No encontramos '{query_text}' exactamente en nuestra categoría '{detected_category.name}'.",
                        "suggestion": "Prueba buscar sin especificar color o características tan específicas.",
                        "reason": "no_attribute_match"
                    }
            else:
                # No se detectó categoría o búsqueda global falló
                partial_match_info = {
                    "message": f"No encontramos productos que coincidan con '{query_text}'.",
                    "suggestion": "Intenta usar términos más generales o explora nuestro catálogo.",
                    "reason": "no_match_global"
                }

            detected_attributes = {
                "color": detected_color,
                "tipo": detected_tipo,
                "context": detected_context
            }
        else:
            # Hay resultados - analizar calidad del match
            COLOR_EXACT_THRESHOLD = 0.75
            COLOR_PARTIAL_THRESHOLD = 0.45
            ATTR_EXACT_THRESHOLD = 0.4

            best_result = results[0]
            best_color_sim = best_result.get('color_similarity', 0.0)
            best_attr_score = best_result.get('attribute_match_score', 0.0)

            # Determinar calidad del match
            if detected_color:
                if best_color_sim >= COLOR_EXACT_THRESHOLD:
                    match_quality = "exact"
                elif best_color_sim >= COLOR_PARTIAL_THRESHOLD:
                    match_quality = "partial"
                else:
                    match_quality = "poor"
            else:
                # Sin color especificado, basar en atributos
                if best_attr_score >= ATTR_EXACT_THRESHOLD:
                    match_quality = "exact"
                else:
                    match_quality = "partial"

            detected_attributes = {
                "color": detected_color,
                "tipo": detected_tipo,
                "context": detected_context
            }

            # Si match es parcial o pobre, dar contexto adicional
            partial_match_info = None
            if match_quality in ["partial", "poor"] and detected_color:
                # Extraer colores disponibles en los resultados
                available_colors = set()
                for r in results[:10]:  # Top 10 para no saturar
                    prod_id = r['product_id']
                    product = next((p for p in all_client_products if str(p.id) == prod_id), None)
                    if product and product.attributes_data:
                        prod_color = product.attributes_data.get('color')
                        if prod_color:
                            available_colors.add(prod_color)

                if available_colors:
                    colors_list = sorted(list(available_colors))
                    if match_quality == "poor":
                        message = f"No tenemos '{detected_tipo or 'productos'}' en color '{detected_color}'. "
                        message += f"Tenemos en: {', '.join(colors_list)}."
                        partial_match_info = {
                            "message": message,
                            "available_colors": colors_list,
                            "requested_color": detected_color,
                            "reason": "color_not_available"
                        }
                    else:  # partial
                        message = f"Coincidencia aproximada para '{detected_color}'. "
                        message += f"También disponible en: {', '.join(colors_list)}."
                        partial_match_info = {
                            "message": message,
                            "available_colors": colors_list,
                            "requested_color": detected_color,
                            "reason": "partial_color_match"
                        }
'''

def main():
    print("🔧 Iniciando eliminación de Fallback 2 y adición de análisis de calidad...")

    # Leer archivo completo
    try:
        with open(API_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return 1

    print(f"📄 Archivo leído: {len(lines)} líneas totales")

    # Verificar que las líneas a eliminar existen
    if FALLBACK_START > len(lines) or FALLBACK_END > len(lines):
        print(f"❌ Líneas fuera de rango: archivo tiene {len(lines)} líneas")
        return 1

    # Mostrar preview de lo que se va a eliminar
    print(f"\n🗑️  Eliminando líneas {FALLBACK_START} a {FALLBACK_END}:")
    print("---")
    for i in range(FALLBACK_START - 1, min(FALLBACK_START + 2, FALLBACK_END)):
        print(f"  L{i+1}: {lines[i].rstrip()}")
    print("  ...")
    for i in range(max(FALLBACK_END - 3, FALLBACK_START), FALLBACK_END):
        print(f"  L{i+1}: {lines[i].rstrip()}")
    print("---\n")

    # Construir nuevo contenido
    new_lines = []

    # Parte 1: Antes del fallback
    new_lines.extend(lines[:FALLBACK_START - 1])

    # Parte 2: Nuevo código de análisis de calidad
    new_lines.append(NEW_QUALITY_ANALYSIS)

    # Parte 3: Después del fallback
    new_lines.extend(lines[FALLBACK_END:])

    print(f"✅ Nuevo contenido construido: {len(new_lines)} líneas")

    # Hacer backup
    backup_file = API_FILE + ".backup_before_fallback2_removal"
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"💾 Backup guardado en: {backup_file}")
    except Exception as e:
        print(f"⚠️  No se pudo guardar backup: {e}")

    # Escribir nuevo archivo
    try:
        with open(API_FILE, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"✅ Archivo actualizado exitosamente")
    except Exception as e:
        print(f"❌ Error escribiendo archivo: {e}")
        return 1

    print("\n🎯 Resumen de cambios:")
    print(f"   - Eliminadas: {FALLBACK_END - FALLBACK_START + 1} líneas (Fallback 2)")
    print(f"   - Agregadas: ~{len(NEW_QUALITY_ANALYSIS.split(chr(10)))} líneas (Análisis de calidad)")
    print(f"   - Total final: {len(new_lines)} líneas")

    return 0

if __name__ == "__main__":
    exit(main())
