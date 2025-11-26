import re

# Leer archivo
with open('clip_admin_backend/app/blueprints/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Primer bloque: Detectado en posición ~1043
block1_old = '''if not detected_categories:
                print(f"❌ MULTI-CATEGORY: No se detectó ninguna categoría")
                return jsonify({
                    "success": False,
                    "error": "category_not_detected",
                    "message": f"La imagen no contiene {'+'productos de {client.industry}' if client.industry and client.industry != 'general' else 'productos'} que comercializa {client.name}",
                    "details": "No pudimos identificar categorías comercializadas en la imagen.",'''

block1_new = '''if not detected_categories:
                print(f"❌ MULTI-CATEGORY: No se detectó ninguna categoría")
                # Mensaje genérico adaptado al rubro del cliente
                industry_msg = f"productos de {client.industry}" if client.industry and client.industry != 'general' else "productos"
                return jsonify({
                    "success": False,
                    "error": "category_not_detected",
                    "message": f"La imagen no contiene {industry_msg} que comercializa {client.name}",
                    "details": "No se identificaron categorías aplicables en la imagen proporcionada.",'''

content = content.replace(block1_old, block1_new)

# Segundo bloque: Detectado en posición ~1227
block2_pattern = r'''if detected_category is None:
            # No se pudo detectar una categoría válida
            railway_log\(f"⚠️ LOG: CATEGORÍA NO DETECTADA - devolviendo error"\)
            return jsonify\(\{
                "success": False,
                "error": "category_not_detected",
                "message": f"Esta imagen no corresponde a productos que comercializa \{client\.name\}",
                "details": f"La imagen no pudo identificarse dentro de nuestras categorías disponibles \(confianza máxima: \{category_confidence:\.1%\}\)\. Por favor, intenta con una imagen de un producto de nuestro catálogo\.",'''

block2_new = '''if detected_category is None:
            # No se pudo detectar una categoría válida
            railway_log(f"⚠️ LOG: CATEGORÍA NO DETECTADA - devolviendo error")
            # Mensaje genérico adaptado al rubro del cliente
            industry_msg = f"productos de {client.industry}" if client.industry and client.industry != 'general' else "productos"
            return jsonify({
                "success": False,
                "error": "category_not_detected",
                "message": f"La imagen no contiene {industry_msg} que comercializa {client.name}",
                "details": f"No se identificaron categorías aplicables (confianza máxima: {category_confidence:.1%}). Intenta con una imagen de productos del catálogo.",'''

content = re.sub(block2_pattern, block2_new, content)

# Guardar
with open('clip_admin_backend/app/blueprints/api.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ Todos los cambios aplicados correctamente')
