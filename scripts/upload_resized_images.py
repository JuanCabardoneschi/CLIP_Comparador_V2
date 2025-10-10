#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Subir Imágenes Redimensionadas a Cloudinary
Sube las 16 imágenes que fueron redimensionadas
"""
import os
import sys
import json
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

def upload_resized_images():
    """Subir las imágenes redimensionadas a Cloudinary"""
    print("📤 SUBIENDO IMÁGENES REDIMENSIONADAS A CLOUDINARY")
    print("="*60)
    print(f"🕒 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    configure_cloudinary()

    # Directorio de imágenes redimensionadas
    resized_dir = project_root / "resized_images"
    if not resized_dir.exists():
        print(f"❌ Error: Directorio {resized_dir} no existe")
        return False

    # Buscar todas las imágenes redimensionadas
    resized_images = list(resized_dir.glob("*.jpg"))
    total_images = len(resized_images)

    print(f"📊 Imágenes redimensionadas encontradas: {total_images}")

    if total_images == 0:
        print("❌ No se encontraron imágenes redimensionadas para subir")
        return False

    # Mostrar lista de archivos
    print("\\n📋 Archivos a subir:")
    for img in resized_images:
        size_mb = img.stat().st_size / (1024 * 1024)
        print(f"   📄 {img.name} ({size_mb:.2f} MB)")

    # Confirmar subida
    confirm = input(f"\\n¿Proceder con la subida de {total_images} imágenes? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Subida cancelada")
        return False

    # Iniciar subida
    success_count = 0
    error_count = 0
    uploaded_mapping = {}

    print(f"\\n🔄 Iniciando subida...")

    for i, image_path in enumerate(resized_images, 1):
        try:
            # Crear public_id basado en el nombre original
            # Remover el prefijo "resized_" si existe
            original_name = image_path.stem
            if original_name.startswith("resized_"):
                original_name = original_name[8:]  # Remover "resized_"

            public_id = f"clip_v2/clients_demo_fashion_store_{original_name}"

            print(f"[{i}/{total_images}] Subiendo: {image_path.name}")

            # Subir imagen
            result = cloudinary.uploader.upload(
                str(image_path),
                public_id=public_id,
                folder="clip_v2",
                resource_type="image",
                quality="auto",
                fetch_format="auto",
                overwrite=True  # Sobrescribir si ya existe
            )

            # Guardar información
            uploaded_mapping[image_path.name] = {
                'original_path': f"uploads\\\\clients\\\\demo_fashion_store\\\\{original_name}.jpg",
                'cloudinary_url': result['secure_url'],
                'public_id': result['public_id'],
                'size': result.get('bytes', 0),
                'width': result.get('width', 0),
                'height': result.get('height', 0)
            }

            success_count += 1
            print(f"✅ {image_path.name} → {result['secure_url']}")
            print(f"   📊 Tamaño final: {result.get('bytes', 0) / (1024*1024):.2f} MB")

            # Pausa pequeña para no saturar la API
            time.sleep(0.1)

        except Exception as e:
            error_count += 1
            print(f"❌ Error con {image_path.name}: {e}")
            continue

    # Resumen final
    print(f"\\n📈 RESUMEN DE SUBIDA")
    print("="*50)
    print(f"✅ Éxitos: {success_count}")
    print(f"❌ Errores: {error_count}")
    print(f"📊 Total procesadas: {success_count + error_count}/{total_images}")
    print(f"🕒 Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Actualizar el mapeo principal
    if uploaded_mapping:
        main_mapping_file = project_root / "cloudinary_migration_mapping.json"

        # Cargar mapeo existente
        existing_mapping = {}
        if main_mapping_file.exists():
            with open(main_mapping_file, 'r', encoding='utf-8') as f:
                existing_mapping = json.load(f)

        # Agregar nuevas imágenes al mapeo
        for filename, data in uploaded_mapping.items():
            original_path = data['original_path']
            existing_mapping[original_path] = {
                'cloudinary_url': data['cloudinary_url'],
                'public_id': data['public_id'],
                'size': data['size'],
                'width': data['width'],
                'height': data['height']
            }

        # Guardar mapeo actualizado
        with open(main_mapping_file, 'w', encoding='utf-8') as f:
            json.dump(existing_mapping, f, indent=2, ensure_ascii=False)

        print(f"\\n💾 Mapeo actualizado en: {main_mapping_file}")
        print(f"📊 Total de imágenes en mapeo: {len(existing_mapping)}")

    return success_count > 0

if __name__ == "__main__":
    try:
        success = upload_resized_images()
        if success:
            print("\\n🎉 ¡Subida completada exitosamente!")
            print("\\n📋 SIGUIENTE PASO:")
            print("   Eliminar imágenes sample de Cloudinary")
        else:
            print("\\n❌ La subida no se completó correctamente")
    except KeyboardInterrupt:
        print("\\n\\n⚠️  Subida interrumpida por el usuario")
    except Exception as e:
        print(f"\\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
