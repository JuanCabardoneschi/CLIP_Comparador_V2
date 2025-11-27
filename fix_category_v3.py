#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script final para actualizar mensajes - versión simplificada
"""

file_path = r'clip_admin_backend\app\blueprints\api.py'

# Leer archivo
with open(file_path, 'r', encoding='utf-8-sig') as f:
    content = f.read()

print("✅ Archivo leído")

# Cambio 1: Primer bloque (multi-category)
old1 = '''                # Mensaje genérico adaptado al rubro del cliente
                industry_msg = f"productos de {client.industry}" if client.industry and client.industry != 'general' else "productos"
                return jsonify({
                    "success": False,
                    "error": "category_not_detected",
                    "message": f"La imagen no contiene {industry_msg} que comercializa {client.name}",
                    "details": "No pudimos identificar categorías comercializadas en la imagen.",'''

new1 = '''                # Mensaje genérico y útil sin asumir vertical específico
                return jsonify({
                    "success": False,
                    "error": "category_not_detected",
                    "message": f"La imagen no coincide con los productos disponibles en {client.name}",
                    "details": "No pudimos identificar productos de nuestro catálogo en esta imagen. Por favor, intenta con una foto clara de un producto similar a los que ofrecemos.",'''

if old1 in content:
    content = content.replace(old1, new1)
    print("✅ Cambio 1 aplicado (primer bloque)")
else:
    print("⚠️  Cambio 1 no encontrado")

# Cambio 2: Segundo bloque (detected_category is None)
old2 = '''            # Mensaje genérico adaptado al rubro del cliente
            industry_msg = f"productos de {client.industry}" if client.industry and client.industry != 'general' else "productos"
            return jsonify({
                "success": False,
                "error": "category_not_detected",
                "message": f"La imagen no contiene {industry_msg} que comercializa {client.name}",
                "details": f"La imagen no pudo identificarse dentro de nuestras categorías disponibles (confianza máxima: {category_confidence:.1%}). Por favor, intenta con una imagen de un producto de nuestro catálogo.",'''

new2 = '''            # Mensaje genérico y útil sin asumir vertical específico
            return jsonify({
                "success": False,
                "error": "category_not_detected",
                "message": f"La imagen no coincide con los productos disponibles en {client.name}",
                "details": f"No pudimos identificar productos de nuestro catálogo en esta imagen (confianza máxima: {category_confidence:.1%}). Por favor, intenta con una foto clara de un producto similar a los que ofrecemos.",'''

if old2 in content:
    content = content.replace(old2, new2)
    print("✅ Cambio 2 aplicado (segundo bloque)")
else:
    print("⚠️  Cambio 2 no encontrado")

# Escribir archivo
with open(file_path, 'w', encoding='utf-8-sig') as f:
    f.write(content)

print("\n✅ Archivo actualizado correctamente")
