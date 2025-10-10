#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actualizar URLs de Cloudinary en Base de Datos - SIMPLE
Extrae solo los nombres de archivo del mapeo y los asocia
"""
import os
import sys
import json
import sqlite3
from pathlib import Path

# Configurar el proyecto
project_root = Path(__file__).parent.parent
backend_dir = project_root / "clip_admin_backend"
os.chdir(backend_dir)

def update_cloudinary_urls_simple():
    """Actualizar URLs de Cloudinary usando solo nombres de archivo"""
    print("🔄 ACTUALIZANDO URLS DE CLOUDINARY (MÉTODO SIMPLE)")
    print("="*60)

    # Cargar el mapeo de migración
    mapping_file = project_root / "cloudinary_migration_mapping.json"
    if not mapping_file.exists():
        print(f"❌ Error: Archivo de mapeo no encontrado: {mapping_file}")
        return False

    with open(mapping_file, 'r', encoding='utf-8') as f:
        url_mapping = json.load(f)

    # Crear mapeo simplificado: filename -> cloudinary_data
    simple_mapping = {}
    for full_path, cloudinary_data in url_mapping.items():
        # Extraer solo el nombre del archivo
        if '\\\\' in full_path:
            filename = full_path.split('\\\\')[-1]  # Doble backslash
        elif '\\' in full_path:
            filename = full_path.split('\\')[-1]   # Single backslash
        else:
            filename = Path(full_path).name  # Fallback usando pathlib
        simple_mapping[filename] = cloudinary_data

    print(f"📄 Mapeo simplificado creado con {len(simple_mapping)} archivos")

    # Conectar a la base de datos
    db_path = backend_dir / "instance" / "clip_comparador_v2.db"

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Obtener todas las imágenes
        cursor.execute("SELECT id, filename, cloudinary_url, product_id FROM images;")
        images = cursor.fetchall()

        print(f"📊 Imágenes en base de datos: {len(images)}")

        updated_count = 0
        not_found_count = 0
        already_updated_count = 0

        # Mostrar primeros elementos del mapeo para debug
        print(f"\\n🔍 Primeras 3 claves del mapeo simplificado:")
        for i, filename in enumerate(list(simple_mapping.keys())[:3]):
            print(f"   {i+1}. {filename}")

        for image_id, filename, current_cloudinary_url, product_id in images:
            print(f"\\n🔍 Imagen BD: {filename}")

            # Si ya tiene URL de Cloudinary, skip
            if current_cloudinary_url and 'cloudinary.com' in current_cloudinary_url:
                already_updated_count += 1
                print(f"   ✅ Ya tiene Cloudinary")
                continue

            # Buscar en el mapeo simplificado
            if filename in simple_mapping:
                cloudinary_data = simple_mapping[filename]
                cloudinary_url = cloudinary_data['cloudinary_url']
                public_id = cloudinary_data['public_id']

                print(f"   ✅ Encontrado en mapeo")
                print(f"   🔗 URL: {cloudinary_url[:80]}...")

                # Actualizar en la base de datos
                cursor.execute("""
                    UPDATE images
                    SET cloudinary_url = ?,
                        cloudinary_public_id = ?,
                        is_processed = 1,
                        upload_status = 'completed'
                    WHERE id = ?
                """, (cloudinary_url, public_id, image_id))

                updated_count += 1

            else:
                not_found_count += 1
                print(f"   ❌ No encontrado en mapeo")

        # Mostrar resumen antes de confirmar
        print(f"\\n📊 RESUMEN PREVIO:")
        print(f"   ✅ Para actualizar: {updated_count}")
        print(f"   🔄 Ya tenían Cloudinary: {already_updated_count}")
        print(f"   ❌ No encontradas: {not_found_count}")

        # Confirmar cambios
        if updated_count > 0:
            confirm = input(f"\\n¿Guardar {updated_count} cambios en la base de datos? (y/N): ")
            if confirm.lower() == 'y':
                conn.commit()
                print(f"✅ {updated_count} imágenes actualizadas exitosamente")
                success = True
            else:
                conn.rollback()
                print("❌ Cambios descartados")
                success = False
        else:
            print("\\n⚠️  No hay cambios para guardar")
            success = False

        conn.close()
        return success

    except Exception as e:
        print(f"❌ Error con la base de datos: {e}")
        return False

if __name__ == "__main__":
    try:
        print("🚀 Iniciando actualización simple de URLs...")
        success = update_cloudinary_urls_simple()

        if success:
            print("\\n🎉 ¡Actualización completada!")
            print("\\n📋 PRÓXIMOS PASOS:")
            print("   1. Probar el sistema manualmente")
            print("   2. Verificar que las imágenes se muestran")
            print("   3. ¡El sistema está listo para Railway!")
        else:
            print("\\n❌ La actualización no se completó")

    except Exception as e:
        print(f"\\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
