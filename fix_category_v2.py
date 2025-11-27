#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para actualizar mensajes de categoría no detectada - Approach line by line
"""

file_path = r'clip_admin_backend\app\blueprints\api.py'

# Leer archivo
with open(file_path, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

print(f"✅ Leídas {len(lines)} líneas")

# Buscar y reemplazar el primer bloque (líneas ~1054-1064)
i = 0
changes = 0
while i < len(lines):
    # Detectar inicio del primer bloque
    if 'if not detected_categories:' in lines[i] and i > 1050 and i < 1100:
        print(f"\n🔍 Encontrado primer bloque en línea {i+1}")
        # Avanzar hasta encontrar el comentario
        j = i + 1
        while j < len(lines) and '# Mensaje genérico adaptado al rubro del cliente' in lines[j]:
            # Reemplazar comentario
            lines[j] = '                # Mensaje genérico y útil sin asumir vertical específico\n'
            print(f"  ✏️  Línea {j+1}: comentario actualizado")
            j += 1
            # Eliminar línea de industry_msg
            if 'industry_msg = f"productos de {client.industry}"' in lines[j]:
                del lines[j]
                print(f"  🗑️  Línea {j+1}: eliminada industry_msg")
            # Actualizar message
            if '"message": f"La imagen no contiene {industry_msg}' in lines[j]:
                lines[j] = '                    "message": f"La imagen no coincide con los productos disponibles en {client.name}",\n'
                print(f"  ✏️  Línea {j+1}: message actualizado")
            j += 1
            # Actualizar details
            if '"details": "No pudimos identificar categorías comercializadas' in lines[j]:
                lines[j] = '                    "details": "No pudimos identificar productos de nuestro catálogo en esta imagen. Por favor, intenta con una foto clara de un producto similar a los que ofrecemos.",\n'
                print(f"  ✏️  Línea {j+1}: details actualizado")
            changes += 1
            break

    # Detectar inicio del segundo bloque (líneas ~1240-1250)
    if 'if detected_category is None:' in lines[i] and i > 1230 and i < 1260:
        print(f"\n🔍 Encontrado segundo bloque en línea {i+1}")
        j = i + 1
        while j < len(lines) and j < i + 15:
            # Reemplazar comentario
            if '# Mensaje genérico adaptado al rubro del cliente' in lines[j]:
                lines[j] = '            # Mensaje genérico y útil sin asumir vertical específico\n'
                print(f"  ✏️  Línea {j+1}: comentario actualizado")
            # Eliminar industry_msg
            if 'industry_msg = f"productos de {client.industry}"' in lines[j]:
                del lines[j]
                print(f"  🗑️  Línea {j+1}: eliminada industry_msg")
                continue
            # Actualizar message
            if '"message": f"La imagen no contiene {industry_msg}' in lines[j]:
                lines[j] = '                "message": f"La imagen no coincide con los productos disponibles en {client.name}",\n'
                print(f"  ✏️  Línea {j+1}: message actualizado")
            # Actualizar details
            if '"details": f"La imagen no pudo identificarse dentro de nuestras categorías' in lines[j]:
                lines[j] = '                "details": f"No pudimos identificar productos de nuestro catálogo en esta imagen (confianza máxima: {category_confidence:.1%}). Por favor, intenta con una foto clara de un producto similar a los que ofrecemos.",\n'
                print(f"  ✏️  Línea {j+1}: details actualizado")
                changes += 1
                break
            j += 1

    i += 1

# Escribir archivo
with open(file_path, 'w', encoding='utf-8-sig') as f:
    f.writelines(lines)

print(f"\n✅ Archivo actualizado con {changes} cambios")
