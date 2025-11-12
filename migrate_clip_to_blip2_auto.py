"""
Script definitivo de migración CLIP → BLIP-2
Hace todos los cambios necesarios en el codebase
"""

import re
from pathlib import Path

def migrate_api_file():
    """Migra api.py específicamente (archivo más complejo)"""
    filepath = Path('clip_admin_backend/app/blueprints/api.py')

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    changes = 0

    while i < len(lines):
        line = lines[i]

        # Detectar bloques de encoding de imagen con CLIP
        if 'model, processor = get_clip_model()' in line:
            changes += 1
            # Reemplazar con BLIP-2
            indent = len(line) - len(line.lstrip())
            new_lines.append(' ' * indent + 'blip2 = get_blip2_system()\n')
            i += 1
            continue

        # Detectar bloques de encoding de imagen
        if 'model.get_image_features' in line:
            # Saltar todo el bloque hasta encontrar embedding_list
            indent = len(line) - len(line.lstrip())
            # Reemplazar todo el bloque
            new_lines.append(' ' * indent + 'embedding_array = blip2.encode_image(pil_image)\n')
            new_lines.append(' ' * indent + 'embedding_list = embedding_array.tolist()\n')
            # Saltar líneas hasta encontrar el cierre del bloque
            while i < len(lines) and 'embedding_list' not in lines[i]:
                i += 1
            i += 1  # Saltar también la línea con embedding_list
            changes += 1
            continue

        # Detectar bloques de encoding de texto
        if 'model.get_text_features' in line:
            # Buscar el nombre de la variable de query
            j = i - 10 if i >= 10 else 0
            query_var = 'text'
            for prev_line in lines[j:i]:
                if 'processor(text=' in prev_line:
                    match = re.search(r'text=\[([^\]]+)\]', prev_line)
                    if match:
                        query_var = match.group(1)
                    break

            indent = len(line) - len(line.lstrip())
            new_lines.append(' ' * indent + f'query_embedding = blip2.encode_text({query_var})\n')

            # Saltar todo el bloque
            while i < len(lines) and 'query_embedding' not in lines[i]:
                i += 1
            i += 1
            changes += 1
            continue

        # Detectar clip_model, clip_processor (variante)
        if 'clip_model, clip_processor = get_clip_model()' in line:
            indent = len(line) - len(line.lstrip())
            new_lines.append(' ' * indent + 'blip2 = get_blip2_system()\n')
            i += 1
            changes += 1
            continue

        # Línea normal, mantener
        new_lines.append(line)
        i += 1

    # Escribir archivo actualizado
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"✅ api.py: {changes} bloques actualizados")

def migrate_simple_file(filepath: str):
    """Migra archivos más simples (solo reemplazos directos)"""
    file_path = Path(filepath)

    if not file_path.exists():
        print(f"⚠️  {filepath} no encontrado")
        return

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    original = content

    # Reemplazos simples
    content = content.replace(
        'from app.blueprints.embeddings import get_clip_model',
        'from app.utils.blip2_embeddings import get_blip2_system'
    )

    content = content.replace(
        'model, processor = get_clip_model()',
        'blip2 = get_blip2_system()'
    )

    content = content.replace(
        'clip_model, clip_processor = get_clip_model()',
        'blip2 = get_blip2_system()'
    )

    content = content.replace(
        'get_clip_model()',
        'get_blip2_system()'
    )

    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ {filepath}: Actualizado")
    else:
        print(f"⏭️  {filepath}: Sin cambios")

def main():
    print("🚀 Migración CLIP → BLIP-2\n")

    # api.py requiere lógica especial
    print("📝 Migrando api.py...")
    migrate_api_file()

    # Otros archivos son más simples
    files = [
        'clip_admin_backend/app/blueprints/categories.py',
        'clip_admin_backend/app/blueprints/diagnostic.py',
        'clip_admin_backend/app/blueprints/calibration.py',
        'clip_admin_backend/app.py',
        'clip_admin_backend/wsgi.py',
        'clip_admin_backend/app/services/query_enrichment_service.py',
        'clip_admin_backend/app/services/attribute_autofill_service.py',
    ]

    print("\n📝 Migrando archivos adicionales...")
    for filepath in files:
        migrate_simple_file(filepath)

    print("\n✅ Migración completa!")

if __name__ == "__main__":
    main()
