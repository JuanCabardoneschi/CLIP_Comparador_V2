#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migración de Imágenes Locales a Cloudinary
Migra todas las imágenes de static/uploads/ a Cloudinary
"""
import os
import sys
from pathlib import Path
import time
from datetime import datetime

# Configurar el proyecto
project_root = Path(__file__).parent.parent
backend_dir = project_root / "clip_admin_backend"
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

import cloudinary
import cloudinary.uploader
import cloudinary.api

def configure_cloudinary():
    """Configurar Cloudinary"""
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET")
    )

def migrate_images():
    """Migrar todas las imágenes a Cloudinary"""
    print("🚀 MIGRACIÓN DE IMÁGENES A CLOUDINARY")
    print("="*50)
    print(f"🕒 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    configure_cloudinary()

    # Directorio de imágenes
    uploads_dir = Path("static/uploads")
    if not uploads_dir.exists():
        print(f"❌ Error: Directorio {uploads_dir} no existe")
        return False

    # Buscar todas las imágenes
    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp']
    all_images = []

    for ext in image_extensions:
        all_images.extend(uploads_dir.rglob(ext))

    total_images = len(all_images)
    print(f"📊 Total de imágenes encontradas: {total_images}")

    if total_images == 0:
        print("❌ No se encontraron imágenes para migrar")
        return False

    # Confirmar migración
    confirm = input(f"\\n¿Proceder con la migración de {total_images} imágenes? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Migración cancelada")
        return False

    # Iniciar migración
    success_count = 0
    error_count = 0
    migrated_urls = {}

    print(f"\\n🔄 Iniciando migración...")

    for i, image_path in enumerate(all_images, 1):
        try:
            # Crear public_id basado en la ruta relativa
            relative_path = image_path.relative_to(uploads_dir)
            public_id = f"clip_v2/{relative_path.as_posix().replace('/', '_').replace('.', '_')}"

            print(f"[{i}/{total_images}] Subiendo: {image_path.name}")

            # Subir imagen
            result = cloudinary.uploader.upload(
                str(image_path),
                public_id=public_id,
                folder="clip_v2",
                resource_type="image",
                quality="auto",
                fetch_format="auto"
            )

            # Guardar información
            original_path = str(image_path.relative_to(Path("static")))
            migrated_urls[original_path] = {
                'cloudinary_url': result['secure_url'],
                'public_id': result['public_id'],
                'size': result.get('bytes', 0),
                'width': result.get('width', 0),
                'height': result.get('height', 0)
            }

            success_count += 1
            print(f"✅ {image_path.name} → {result['secure_url']}")

            # Pausa pequeña para no saturar la API
            time.sleep(0.1)

        except Exception as e:
            error_count += 1
            print(f"❌ Error con {image_path.name}: {e}")
            continue

    # Resumen final
    print(f"\\n📈 RESUMEN DE MIGRACIÓN")
    print("="*50)
    print(f"✅ Éxitos: {success_count}")
    print(f"❌ Errores: {error_count}")
    print(f"📊 Total procesadas: {success_count + error_count}/{total_images}")
    print(f"🕒 Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Guardar mapeo de URLs
    if migrated_urls:
        mapping_file = project_root / "cloudinary_migration_mapping.json"
        import json
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(migrated_urls, f, indent=2, ensure_ascii=False)

        print(f"\\n💾 Mapeo guardado en: {mapping_file}")
        print("\\n📝 SIGUIENTE PASO:")
        print("   Actualizar las referencias en la base de datos")
        print("   usando el archivo de mapeo generado")

    return success_count > 0

if __name__ == "__main__":
    try:
        success = migrate_images()
        if success:
            print("\\n🎉 ¡Migración completada!")
            print("\\n⚠️  IMPORTANTE:")
            print("   1. Verificar que las imágenes están en Cloudinary")
            print("   2. Actualizar las referencias en la base de datos")
            print("   3. Después de verificar, eliminar archivos locales")
        else:
            print("\\n❌ La migración no se completó correctamente")
    except KeyboardInterrupt:
        print("\\n\\n⚠️  Migración interrumpida por el usuario")
    except Exception as e:
        print(f"\\n❌ Error crítico: {e}")
