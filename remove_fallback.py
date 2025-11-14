"""
Script para eliminar el fallback global del endpoint /search/text
"""
import os

file_path = r'c:\Personal\CLIP_Comparador_V2\clip_admin_backend\app\blueprints\api.py'

# Leer archivo
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Encontrar y reemplazar el bloque del fallback (líneas 2734-2761 aprox)
# Buscar desde "if detected_category and len(products) == 0:" hasta el segundo "print(f"[REQ {request_id}] DEBUG: query SQL"

start_idx = None
end_idx = None

for i, line in enumerate(lines):
    if 'if detected_category and len(products) == 0:' in line and start_idx is None:
        start_idx = i
    if start_idx is not None and i > start_idx and 'TEXT SEARCH: Analizando' in line:
        end_idx = i
        break

if start_idx and end_idx:
    print(f"Encontrado bloque fallback: líneas {start_idx+1} a {end_idx}")
    print(f"Líneas a eliminar:")
    for i in range(start_idx, end_idx):
        print(f"  {i+1}: {lines[i][:80]}")

    # Construir nuevo contenido
    new_lines = lines[:start_idx]

    # Agregar código de reemplazo
    indent = '        '
    new_lines.append(f"{indent}if detected_category and len(products) == 0:\n")
    new_lines.append(f"{indent}    print(f\"⚠️ TEXT SEARCH: Categoría '{{detected_category.name}}' sin productos → Retornando error 404\")\n")
    new_lines.append(f"{indent}    available_categories = [cat.name for cat in categories if Product.query.filter_by(category_id=cat.id, client_id=client.id).count() > 0]\n")
    new_lines.append(f"{indent}    return jsonify({{\n")
    new_lines.append(f"{indent}        \"success\": False,\n")
    new_lines.append(f"{indent}        \"error\": \"category_empty\",\n")
    new_lines.append(f"{indent}        \"message\": f\"No tenemos productos en '{{detected_category.name}}' actualmente.\",\n")
    new_lines.append(f"{indent}        \"detected_category\": detected_category.name,\n")
    new_lines.append(f"{indent}        \"available_categories\": available_categories[:10],\n")
    new_lines.append(f"{indent}        \"suggestion_message\": \"Explora nuestras categorías disponibles.\",\n")
    new_lines.append(f"{indent}        \"processing_time\": round(time.time() - start_time, 3)\n")
    new_lines.append(f"{indent}    }}), 404\n\n")

    # Agregar resto del archivo desde end_idx
    new_lines.extend(lines[end_idx:])

    # Escribir archivo
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"\n✅ Fallback eliminado exitosamente")
    print(f"Total líneas eliminadas: {end_idx - start_idx}")
else:
    print("❌ No se encontró el bloque del fallback")
