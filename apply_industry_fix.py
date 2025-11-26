#!/usr/bin/env python3
# -*- coding: utf-8 -*-

with open('clip_admin_backend/app/blueprints/api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

output = []
i = 0
while i < len(lines):
    line = lines[i]

    # Primer bloque: después de "if not detected_categories:"
    if 'if not detected_categories:' in line and i + 1 < len(lines) and 'MULTI-CATEGORY' in lines[i+1]:
        output.append(line)  # if not detected_categories:
        output.append(lines[i+1])  # print(f"...")
        # Insertar la lógica de industry_msg
        indent = '                '
        output.append(f'{indent}# Mensaje genérico adaptado al rubro del cliente\n')
        output.append(f'{indent}industry_msg = f"productos de {{client.industry}}" if client.industry and client.industry != \'general\' else "productos"\n')
        i += 2
        # Copiar hasta el mensaje, modificándolo
        while i < len(lines):
            if '"message"' in lines[i] and 'Esta imagen no corresponde' in lines[i]:
                output.append(f'{indent}    "message": f"La imagen no contiene {{industry_msg}} que comercializa {{client.name}}",\n')
                i += 1
                break
            elif '"details"' in lines[i] and 'No pudimos identificar' in lines[i]:
                output.append(f'{indent}    "details": "No se identificaron categorías aplicables en la imagen proporcionada.",\n')
                i += 1
                break
            else:
                output.append(lines[i])
                i += 1
        continue

    # Segundo bloque: después de "if detected_category is None:"
    elif 'if detected_category is None:' in line:
        output.append(line)  # if detected_category is None:
        if i + 1 < len(lines):
            output.append(lines[i+1])  # # No se pudo detectar...
            i += 2
        if i < len(lines) and 'railway_log' in lines[i]:
            output.append(lines[i])  # railway_log(f"...")
            i += 1
        # Insertar la lógica de industry_msg
        indent = '            '
        output.append(f'{indent}# Mensaje genérico adaptado al rubro del cliente\n')
        output.append(f'{indent}industry_msg = f"productos de {{client.industry}}" if client.industry and client.industry != \'general\' else "productos"\n')
        # Copiar hasta el mensaje, modificándolo
        while i < len(lines):
            if '"message"' in lines[i] and 'Esta imagen no corresponde' in lines[i]:
                output.append(f'{indent}    "message": f"La imagen no contiene {{industry_msg}} que comercializa {{client.name}}",\n')
                i += 1
                break
            elif '"details"' in lines[i] and 'La imagen no pudo identificarse' in lines[i]:
                # Extraer la parte de category_confidence
                output.append(f'{indent}    "details": f"No se identificaron categorías aplicables (confianza máxima: {{category_confidence:.1%}}). Intenta con una imagen de productos del catálogo.",\n')
                i += 1
                break
            else:
                output.append(lines[i])
                i += 1
        continue

    output.append(line)
    i += 1

with open('clip_admin_backend/app/blueprints/api.py', 'w', encoding='utf-8') as f:
    f.writelines(output)

print('✅ Cambios aplicados correctamente')
print('   - Mensaje 1: Adaptado al rubro del cliente')
print('   - Mensaje 2: Adaptado al rubro del cliente')
