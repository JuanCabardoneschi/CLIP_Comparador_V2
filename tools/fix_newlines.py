"""
Script para arreglar los saltos de línea rotos en search_text.py
"""

FILE_PATH = r"c:\Personal\CLIP_Comparador_V2\clip_admin_backend\app\blueprints\search_text.py"

with open(FILE_PATH, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed_lines = []
for i, line in enumerate(lines):
    # Buscar líneas que terminen con "="*60 + " (string sin cerrar)
    if '"="*60 + "' in line and not line.strip().endswith('")'):
        # Está roto, cerrar el string correctamente
        # La siguiente línea debería ser ")
        if i + 1 < len(lines) and lines[i + 1].strip() == '")':
            # Reemplazar ambas líneas con una sola correcta
            fixed_line = line.rstrip() + '\\n")\n'
            fixed_lines.append(fixed_line)
            lines[i + 1] = ''  # Marcar la siguiente línea para omitir
        else:
            fixed_lines.append(line)
    elif line.strip() == '")' and i > 0 and lines[i-1] == '':
        # Esta línea ya fue procesada, omitir
        continue
    else:
        fixed_lines.append(line)

with open(FILE_PATH, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print("✅ Arreglados saltos de línea en search_text.py")
