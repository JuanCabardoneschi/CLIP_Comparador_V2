#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actualizar URLs de Cloudinary en Base de Datos
Actualiza las URLs en la tabla images usando el mapeo de migración
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

def update_cloudinary_urls():
    """Actualizar URLs de Cloudinary en la tabla images"""
    print("🔄 ACTUALIZANDO URLS DE CLOUDINARY EN BASE DE DATOS")
    print("="*60)

    # Cargar el mapeo de migración
    mapping_file = project_root / "cloudinary_migration_mapping.json"
    if not mapping_file.exists():
        print(f"❌ Error: Archivo de mapeo no encontrado: {mapping_file}")
        return False

    with open(mapping_file, 'r', encoding='utf-8') as f:
        url_mapping = json.load(f)

    print(f"📄 Cargado mapeo con {len(url_mapping)} imágenes migradas")

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

        for image_id, filename, current_cloudinary_url, product_id in images:
            print(f"\\n🔍 Imagen: {filename}")

            # Si ya tiene URL de Cloudinary, skip
            if current_cloudinary_url and 'cloudinary.com' in current_cloudinary_url:
                already_updated_count += 1
                print(f"   ✅ Ya tiene URL de Cloudinary: {current_cloudinary_url[:80]}...")
                continue

            # Buscar en el mapeo
            # El filename en la BD puede ser: '024fd665-410c-4639-bf69-ccd8d258bf9d_CASACA SLIM AZUL (14).jpg'
            # El mapeo tiene: 'uploads\\\\clients\\\\demo_fashion_store\\\\024fd665...'

            # Crear las posibles rutas a buscar
            possible_paths = [
                f"uploads\\\\clients\\\\demo_fashion_store\\\\{filename}",
                f"uploads/clients/demo_fashion_store/{filename}",
                f"static/uploads/clients/demo_fashion_store/{filename}",
                f"/static/uploads/clients/demo_fashion_store/{filename}"
            ]

            cloudinary_data = None
            found_path = None

            for path in possible_paths:
                if path in url_mapping:
                    cloudinary_data = url_mapping[path]
                    found_path = path
                    break

            if cloudinary_data:
                cloudinary_url = cloudinary_data['cloudinary_url']
                public_id = cloudinary_data['public_id']

                print(f"   ✅ Encontrado en mapeo: {found_path}")
                print(f"   🔗 Nueva URL: {cloudinary_url[:80]}...")

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
                print(f"   ❌ No encontrado en mapeo de Cloudinary")
                print(f"   📄 Filename: {filename}")

        # Confirmar cambios
        if updated_count > 0:
            confirm = input(f"\\n¿Guardar {updated_count} cambios en la base de datos? (y/N): ")
            if confirm.lower() == 'y':
                conn.commit()
                print(f"✅ {updated_count} imágenes actualizadas exitosamente")
            else:
                conn.rollback()
                print("❌ Cambios descartados")
                conn.close()
                return False

        # Resumen final
        print(f"\\n📊 RESUMEN:")
        print(f"   ✅ Actualizadas: {updated_count}")
        print(f"   🔄 Ya tenían Cloudinary: {already_updated_count}")
        print(f"   ❌ No encontradas: {not_found_count}")
        print(f"   📦 Total procesadas: {updated_count + already_updated_count + not_found_count}")

        conn.close()
        return updated_count > 0

    except Exception as e:
        print(f"❌ Error con la base de datos: {e}")
        return False

def verify_updates():
    """Verificar que las actualizaciones se realizaron correctamente"""
    print("\\n🔍 VERIFICACIÓN DE ACTUALIZACIONES")
    print("="*40)

    db_path = backend_dir / "instance" / "clip_comparador_v2.db"

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Contar imágenes con Cloudinary
        cursor.execute("SELECT COUNT(*) FROM images WHERE cloudinary_url IS NOT NULL AND cloudinary_url LIKE '%cloudinary.com%';")
        cloudinary_count = cursor.fetchone()[0]

        # Contar imágenes sin Cloudinary
        cursor.execute("SELECT COUNT(*) FROM images WHERE cloudinary_url IS NULL OR cloudinary_url NOT LIKE '%cloudinary.com%';")
        local_count = cursor.fetchone()[0]

        # Mostrar algunas que no tienen Cloudinary
        if local_count > 0:
            cursor.execute("SELECT filename FROM images WHERE cloudinary_url IS NULL OR cloudinary_url NOT LIKE '%cloudinary.com%' LIMIT 5;")
            missing = cursor.fetchall()

            print(f"⚠️  Imágenes sin Cloudinary:")
            for filename, in missing:
                print(f"   📄 {filename}")

        print(f"\\n📊 ESTADO ACTUAL:")
        print(f"   ☁️  URLs de Cloudinary: {cloudinary_count}")
        print(f"   💽 URLs sin Cloudinary: {local_count}")

        conn.close()

        if local_count == 0:
            print("\\n🎉 ¡Todas las imágenes tienen URLs de Cloudinary!")
            return True
        else:
            print(f"\\n⚠️  Quedan {local_count} imágenes sin URL de Cloudinary")
            return False

    except Exception as e:
        print(f"❌ Error verificando: {e}")
        return False

if __name__ == "__main__":
    try:
        print("🚀 Iniciando actualización de URLs...")
        success = update_cloudinary_urls()

        if success:
            verify_updates()
            print("\\n✅ Proceso completado exitosamente")
            print("\\n📋 PRÓXIMOS PASOS:")
            print("   1. Probar el sistema manualmente")
            print("   2. Verificar que las imágenes se muestran correctamente")
            print("   3. El sistema está listo para Railway!")
        else:
            print("\\n❌ No se realizaron actualizaciones")

    except Exception as e:
        print(f"\\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
