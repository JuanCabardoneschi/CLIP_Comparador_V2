"""Script para aplicar patch force_category limpiando caracteres especiales"""
import re

file_path = r'clip_admin_backend\app\blueprints\api.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Buscar el patrón con caracteres normalizados
old_pattern = r'        # MODO SINGLE \(original\)\s+railway_log\(f" LOG: INICIANDO DETECCIÓN DE CATEGORÍA ESPECÍFICA \(SINGLE MODE\)"\)\s+detected_category, category_confidence = detect_image_category_with_centroids\(\s+image_data,\s+client\.id,\s+confidence_threshold=category_confidence_threshold  # Sensibilidad por cliente\s+\)\s+railway_log\(f" LOG: Resultado detección = \{detected_category\.name if detected_category else \'NULL\'\} \(conf: \{category_confidence:.3f\}\)"\)'

new_code = '''        # MODO SINGLE (original)
        railway_log(f" LOG: INICIANDO DETECCIÓN DE CATEGORÍA ESPECÍFICA (SINGLE MODE)")

        # Verificar si hay categoría forzada
        force_category = request.form.get('force_category', 'false').lower() == 'true'
        forced_category_id = request.form.get('category_id') if force_category else None

        if force_category and forced_category_id:
            # Saltar autodetección y usar categoría forzada
            railway_log(f" LOG: MODO FORZADO - usando category_id={forced_category_id}")
            try:
                forced_category = Category.query.get(forced_category_id)
                if not forced_category or forced_category.client_id != client.id:
                    return jsonify({
                        "success": False,
                        "error": "invalid_category",
                        "message": "Categoría forzada inválida o no pertenece al cliente",
                        "processing_time": round(time.time() - start_time, 3)
                    }), 400

                # Usar categoría forzada directamente
                detected_category = forced_category
                category_confidence = 1.0  # Confianza máxima porque fue manual
                railway_log(f" LOG: Categoría forzada: {detected_category.name}")
            except Exception as e:
                railway_log(f" ERROR: Fallo al forzar categoría: {e}")
                return jsonify({
                    "success": False,
                    "error": "internal_error",
                    "message": f"Error al forzar categoría: {str(e)}",
                    "processing_time": round(time.time() - start_time, 3)
                }), 500
        else:
            # Autodetección normal
            detected_category, category_confidence = detect_image_category_with_centroids(
                image_data,
                client.id,
                confidence_threshold=category_confidence_threshold  # Sensibilidad por cliente
            )

        railway_log(f" LOG: Resultado detección = {detected_category.name if detected_category else 'NULL'} (conf: {category_confidence:.3f})")'''

# Buscar línea específica
lines = content.split('\n')
start_idx = None
for i, line in enumerate(lines):
    if '# MODO SINGLE (original)' in line:
        start_idx = i
        break

if start_idx:
    # Buscar la segunda railway_log después del modo single
    end_idx = None
    for i in range(start_idx + 1, min(start_idx + 15, len(lines))):
        if 'railway_log(f" LOG: Resultado' in lines[i]:
            end_idx = i
            break

    if end_idx:
        # Reemplazar esas líneas
        new_lines = new_code.split('\n')
        lines[start_idx:end_idx+1] = new_lines

        content = '\n'.join(lines)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✓ Patch aplicado exitosamente")
        print(f"  Líneas reemplazadas: {start_idx}-{end_idx}")
    else:
        print("✗ No se encontró la línea de cierre (railway_log Resultado)")
else:
    print("✗ No se encontró el marcador '# MODO SINGLE (original)'")
