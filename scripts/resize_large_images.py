#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redimensionar y Migrar Imágenes Grandes
Procesa las imágenes que fallaron por tamaño > 10MB
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
from PIL import Image
import tempfile

def configure_cloudinary():
    """Configurar Cloudinary"""
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET")
    )

def get_failed_images():
    """Obtener lista de imágenes que fallaron por tamaño"""
    # Lista de imágenes que fallaron en la migración anterior
    failed_images = [
        "104cb838-d36c-4fae-8bda-b77e2ca5408e_DELANTAL PECHERA LONETA RAYA ANCH NEGRO CON TOSTADO (4).jpg",
        "18b946a7-d628-4c70-a2d0-60ead627067f_AMBO VESTIR GOODY DAMA (2).jpg",
        "1f36ac07-201f-4ad0-86d5-af8747efe483_CASACA SLIM NEGRA  (8).jpg",
        "2214d2ac-ed6d-4dd4-bf18-281812d082fc_ZUECO SOFT WORKS BB61 (1).jpg",
        "34866fa2-462a-4781-ab9b-d46e0afb7043_BOINA CALADA (1).jpg",
        "3647e7bb-9559-4136-a4e8-f55e85fdada9_MEDIO DELANTAL AZUL ALPACUNA (2).jpg",
        "45c51e6b-0035-4713-80bc-969d1b27e431_CHALECO NEGRO DAMA (1).jpg",
        "5b1de765-9950-4163-b84a-43de7141c49b_CAMISA MOD. HOTELGA 2025 (2).jpg",
        "6856018d-46a1-4b18-9f40-be945cdf931e_GORRO BACCIO NEGRO (2).jpg",
        "76ebbb37-3826-4c36-8ab6-215d76ced1eb_CASACA MERCURE 2.0  (1).jpg",
        "7d9ae7d6-f6f2-4354-828e-fa4ec7d4573e_GOODY-0323.jpg",
        "91970588-b9a0-470d-b5ce-51336a134a2f_CHALECO NEGRO HOMBRE (1).jpg",
        "9636ae1e-383e-4e6f-90dc-ea8a12fa62b7_GOODY-0524.jpg",
        "b586676b-275d-48e0-85fc-ecf196d0078a_GOODY-0331.jpg",
        "e3d28961-1355-4bff-93da-156bc3451fe0_GOODY-0518.jpg",
        "ec6833a6-28da-41d8-bce7-cb6825b8e4f1_GORRA CUP NEGRA (1).jpg"
    ]

    uploads_dir = Path("static/uploads/clients/demo_fashion_store")
    existing_images = []

    for filename in failed_images:
        image_path = uploads_dir / filename
        if image_path.exists():
            existing_images.append(image_path)
        else:
            print(f"⚠️  Imagen no encontrada: {filename}")

    return existing_images

def resize_image(image_path, max_size_mb=9, quality=85):
    """
    Redimensionar imagen para que sea menor a max_size_mb

    Args:
        image_path: Ruta de la imagen original
        max_size_mb: Tamaño máximo en MB (default 9MB para estar seguro)
        quality: Calidad JPEG (default 85)

    Returns:
        Ruta del archivo temporal redimensionado
    """
    target_size = max_size_mb * 1024 * 1024  # Convertir a bytes

    with Image.open(image_path) as img:
        # Convertir a RGB si es necesario
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Comenzar con dimensiones originales
        width, height = img.size
        current_quality = quality

        print(f"   📐 Dimensiones originales: {width}x{height}")

        # Intentar diferentes estrategias de reducción
        for attempt in range(5):
            # Crear archivo temporal
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            temp_path = temp_file.name
            temp_file.close()

            try:
                # Redimensionar imagen
                resized_img = img.resize((width, height), Image.Resampling.LANCZOS)

                # Guardar con calidad específica
                resized_img.save(temp_path, 'JPEG', quality=current_quality, optimize=True)

                # Verificar tamaño
                file_size = os.path.getsize(temp_path)
                print(f"   🔄 Intento {attempt + 1}: {width}x{height}, calidad {current_quality}, tamaño: {file_size / 1024 / 1024:.2f}MB")

                if file_size <= target_size:
                    print(f"   ✅ Imagen optimizada: {file_size / 1024 / 1024:.2f}MB")
                    return temp_path

                # Si es muy grande, ajustar para siguiente intento
                os.unlink(temp_path)

                if attempt < 2:
                    # Primero reducir calidad
                    current_quality = max(60, current_quality - 15)
                else:
                    # Luego reducir dimensiones
                    width = int(width * 0.8)
                    height = int(height * 0.8)
                    current_quality = max(70, current_quality)

            except Exception as e:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                print(f"   ❌ Error en intento {attempt + 1}: {e}")
                continue

        print(f"   ❌ No se pudo reducir suficientemente después de 5 intentos")
        return None

def migrate_large_images():
    """Migrar imágenes grandes después de redimensionarlas"""
    print("🔧 REDIMENSIONADO Y MIGRACIÓN DE IMÁGENES GRANDES")
    print("="*60)
    print(f"🕒 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    configure_cloudinary()

    failed_images = get_failed_images()
    total_images = len(failed_images)

    print(f"📊 Imágenes grandes encontradas: {total_images}")

    if total_images == 0:
        print("✅ No hay imágenes grandes para procesar")
        return True

    # Confirmar procesamiento
    confirm = input(f"\\n¿Proceder con el redimensionado y migración de {total_images} imágenes? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Procesamiento cancelado")
        return False

    success_count = 0
    error_count = 0
    migrated_urls = {}

    print(f"\\n🔄 Iniciando procesamiento...")

    for i, image_path in enumerate(failed_images, 1):
        try:
            print(f"\\n[{i}/{total_images}] Procesando: {image_path.name}")

            # Verificar tamaño original
            original_size = image_path.stat().st_size
            print(f"   📊 Tamaño original: {original_size / 1024 / 1024:.2f}MB")

            # Redimensionar imagen
            resized_path = resize_image(image_path)

            if not resized_path:
                error_count += 1
                print(f"   ❌ No se pudo redimensionar: {image_path.name}")
                continue

            try:
                # Crear public_id
                relative_path = image_path.relative_to(Path("static/uploads"))
                public_id = f"clip_v2/{relative_path.as_posix().replace('/', '_').replace('.', '_')}"

                print(f"   ☁️  Subiendo a Cloudinary...")

                # Subir imagen redimensionada
                result = cloudinary.uploader.upload(
                    resized_path,
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
                    'height': result.get('height', 0),
                    'original_size': original_size,
                    'compression_ratio': f"{original_size / result.get('bytes', 1):.2f}x"
                }

                success_count += 1
                print(f"   ✅ Subida exitosa: {result['secure_url']}")
                print(f"   📉 Reducción: {original_size / 1024 / 1024:.2f}MB → {result.get('bytes', 0) / 1024 / 1024:.2f}MB")

            finally:
                # Limpiar archivo temporal
                if os.path.exists(resized_path):
                    os.unlink(resized_path)

            # Pausa para no saturar la API
            time.sleep(0.2)

        except Exception as e:
            error_count += 1
            print(f"   ❌ Error con {image_path.name}: {e}")
            continue

    # Resumen final
    print(f"\\n📈 RESUMEN DE PROCESAMIENTO")
    print("="*60)
    print(f"✅ Éxitos: {success_count}")
    print(f"❌ Errores: {error_count}")
    print(f"📊 Total procesadas: {success_count + error_count}/{total_images}")
    print(f"🕒 Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Actualizar mapeo si hay nuevas URLs
    if migrated_urls:
        mapping_file = project_root / "cloudinary_migration_mapping.json"

        # Cargar mapeo existente
        existing_mapping = {}
        if mapping_file.exists():
            import json
            with open(mapping_file, 'r', encoding='utf-8') as f:
                existing_mapping = json.load(f)

        # Agregar nuevas URLs
        existing_mapping.update(migrated_urls)

        # Guardar mapeo actualizado
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(existing_mapping, f, indent=2, ensure_ascii=False)

        print(f"\\n💾 Mapeo actualizado en: {mapping_file}")

    return success_count > 0

if __name__ == "__main__":
    try:
        success = migrate_large_images()
        if success:
            print("\\n🎉 ¡Redimensionado y migración completados!")
            print("\\n📋 SIGUIENTE PASO:")
            print("   Ejecutar update_database_urls.py para actualizar la BD")
        else:
            print("\\n❌ El procesamiento no se completó correctamente")
    except KeyboardInterrupt:
        print("\\n\\n⚠️  Procesamiento interrumpido por el usuario")
    except Exception as e:
        print(f"\\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
