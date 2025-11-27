#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para actualizar mensajes de categoría no detectada
Hace los mensajes más genéricos y útiles sin asumir ropa/textil
"""

import re

file_path = r'clip_admin_backend\app\blueprints\api.py'

# Leer el archivo con encoding correcto
with open(file_path, 'r', encoding='utf-8-sig') as f:
    content = f.read()

print("✅ Archivo leído correctamente")

# Primer patrón: Multi-category block (línea ~1054)
pattern1 = r'(if not detected_categories:\s+print\(f"❌ MULTI-CATEGORY: No se detectó ninguna categoría"\)\s+)# Mensaje genérico adaptado al rubro del cliente\s+industry_msg = f"productos de \{client\.industry\}" if client\.industry and client\.industry != \'general\' else "productos"\s+(return jsonify\(\{\s+"success": False,\s+"error": "category_not_detected",\s+)"message": f"La imagen no contiene \{industry_msg\} que comercializa \{client\.name\}",\s+"details": "No pudimos identificar categorías comercializadas en la imagen\.",'

replacement1 = r'\1# Mensaje genérico y útil sin asumir vertical específico\n                \2"message": f"La imagen no coincide con los productos disponibles en {client.name}",\n                    "details": "No pudimos identificar productos de nuestro catálogo en esta imagen. Por favor, intenta con una foto clara de un producto similar a los que ofrecemos.",'

content = re.sub(pattern1, replacement1, content, flags=re.MULTILINE)

# Segundo patrón: detected_category is None block (línea ~1240)
pattern2 = r'(if detected_category is None:\s+# No se pudo detectar una categoría válida\s+railway_log\(f" LOG: CATEGORÍA NO DETECTADA - devolviendo error"\)\s+)# Mensaje genérico adaptado al rubro del cliente\s+industry_msg = f"productos de \{client\.industry\}" if client\.industry and client\.industry != \'general\' else "productos"\s+(return jsonify\(\{\s+"success": False,\s+"error": "category_not_detected",\s+)"message": f"La imagen no contiene \{industry_msg\} que comercializa \{client\.name\}",\s+"details": f"La imagen no pudo identificarse dentro de nuestras categorías disponibles \(confianza máxima: \{category_confidence:.1%\}\)\. Por favor, intenta con una imagen de un producto de nuestro catálogo\.",'

replacement2 = r'\1# Mensaje genérico y útil sin asumir vertical específico\n            \2"message": f"La imagen no coincide con los productos disponibles en {client.name}",\n                "details": f"No pudimos identificar productos de nuestro catálogo en esta imagen (confianza máxima: {category_confidence:.1%}). Por favor, intenta con una foto clara de un producto similar a los que ofrecemos.",'

content = re.sub(pattern2, replacement2, content, flags=re.MULTILINE)

# Escribir de vuelta
with open(file_path, 'w', encoding='utf-8-sig') as f:
    f.write(content)

print("✅ Mensajes actualizados correctamente")
print("\nCambios realizados:")
print("1. Primer bloque (multi-category): mensaje genérico sin mencionar industry/ropa")
print("2. Segundo bloque (detected_category None): mensaje genérico sin mencionar industry/ropa")
