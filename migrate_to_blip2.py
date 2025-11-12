"""
Script de migración masiva CLIP → BLIP-2
Reemplaza todas las referencias a get_clip_model() por get_blip2_system()
"""

import re
import os
from pathlib import Path

# Patrones de reemplazo
REPLACEMENTS = [
    # Imports
    (r'from app\.blueprints\.embeddings import get_clip_model',
     'from app.utils.blip2_embeddings import get_blip2_system'),

    # Llamadas get_clip_model()
    (r'model, processor = get_clip_model\(\)',
     'blip2 = get_blip2_system()'),

    (r'clip_model, clip_processor = get_clip_model\(\)',
     'blip2 = get_blip2_system()'),

    # Encoding de imágenes
    (r'with torch\.no_grad\(\):\s+inputs = processor\(\s+images=([^,]+),\s+return_tensors="pt"\s+\)\s+(?:.*?\n)*?\s+image_features = model\.get_image_features\(\*\*inputs\)\s+(?:.*?\n)*?\s+embedding = image_features / image_features\.norm\(dim=-1, keepdim=True\)\s+(?:.*?\n)*?\s+embedding_list = embedding\.squeeze\(\)\.cpu\(\)\.numpy\(\)\.tolist\(\)',
     r'embedding_array = blip2.encode_image(\1)\nembedding_list = embedding_array.tolist()'),

    # Encoding de texto
    (r'with torch\.no_grad\(\):\s+text_inputs = processor\(text=\[([^\]]+)\], return_tensors="pt", padding=True\)\s+text_features = model\.get_text_features\(\*\*text_inputs\)\s+text_features = text_features / text_features\.norm\(dim=-1, keepdim=True\)\s+query_embedding = text_features\.cpu\(\)\.numpy\(\)\[0\]',
     r'query_embedding = blip2.encode_text(\1)'),
]

# Archivos a actualizar
FILES_TO_UPDATE = [
    'clip_admin_backend/app/blueprints/api.py',
    'clip_admin_backend/app/blueprints/categories.py',
    'clip_admin_backend/app/blueprints/diagnostic.py',
    'clip_admin_backend/app/blueprints/calibration.py',
    'clip_admin_backend/app.py',
    'clip_admin_backend/wsgi.py',
    'clip_admin_backend/app/services/query_enrichment_service.py',
    'clip_admin_backend/app/services/attribute_autofill_service.py',
]

def migrate_file(filepath: str):
    """Migra un archivo de CLIP a BLIP-2"""
    file_path = Path(filepath)

    if not file_path.exists():
        print(f"⚠️  {filepath} no encontrado")
        return False

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        changes_made = 0

        # Aplicar reemplazos
        for pattern, replacement in REPLACEMENTS:
            new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
            if new_content != content:
                changes_made += 1
                content = new_content

        # Guardar si hubo cambios
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ {filepath}: {changes_made} cambios aplicados")
            return True
        else:
            print(f"⏭️  {filepath}: Sin cambios necesarios")
            return False

    except Exception as e:
        print(f"❌ Error en {filepath}: {e}")
        return False

def main():
    print("🚀 Iniciando migración CLIP → BLIP-2\n")

    total_updated = 0
    for filepath in FILES_TO_UPDATE:
        if migrate_file(filepath):
            total_updated += 1

    print(f"\n📊 Migración completa: {total_updated}/{len(FILES_TO_UPDATE)} archivos actualizados")

if __name__ == "__main__":
    main()
