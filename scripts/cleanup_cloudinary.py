#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Limpieza de Imágenes de Prueba en Cloudinary
Elimina imágenes que no pertenecen al catálogo real
"""
import os
import sys
from pathlib import Path

# Configurar el proyecto
project_root = Path(__file__).parent.parent
backend_dir = project_root / "clip_admin_backend"
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

import cloudinary
import cloudinary.api
import cloudinary.uploader

def configure_cloudinary():
    """Configurar Cloudinary"""
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET")
    )

def list_cloudinary_images():
    """Listar todas las imágenes en Cloudinary"""
    print("📋 LISTANDO IMÁGENES EN CLOUDINARY")
    print("="*50)

    configure_cloudinary()

    try:
        # Listar todas las imágenes
        result = cloudinary.api.resources(
            type="upload",
            prefix="",
            max_results=500
        )

        print(f"📊 Total de imágenes encontradas: {len(result['resources'])}")

        # Categorizar imágenes
        test_images = []
        clip_v2_images = []
        other_images = []

        for image in result['resources']:
            public_id = image['public_id']

            if 'test/' in public_id or 'clip_v2_test' in public_id:
                test_images.append(image)
            elif 'clip_v2/' in public_id:
                clip_v2_images.append(image)
            else:
                other_images.append(image)

        print(f"\\n📈 CATEGORIZACIÓN:")
        print(f"   🧪 Imágenes de test: {len(test_images)}")
        print(f"   📦 Imágenes del catálogo (clip_v2): {len(clip_v2_images)}")
        print(f"   ❓ Otras imágenes: {len(other_images)}")

        # Mostrar imágenes de test para confirmar eliminación
        if test_images:
            print(f"\\n🧪 IMÁGENES DE TEST ENCONTRADAS:")
            for img in test_images:
                print(f"   - {img['public_id']} ({img.get('bytes', 0)} bytes)")

        if other_images:
            print(f"\\n❓ OTRAS IMÁGENES:")
            for img in other_images:
                print(f"   - {img['public_id']} ({img.get('bytes', 0)} bytes)")

        return test_images, other_images

    except Exception as e:
        print(f"❌ Error al listar imágenes: {e}")
        return [], []

def delete_test_images(test_images):
    """Eliminar imágenes de test"""
    if not test_images:
        print("✅ No hay imágenes de test para eliminar")
        return True

    print(f"\\n🗑️  ELIMINACIÓN DE {len(test_images)} IMÁGENES DE TEST")
    print("="*50)

    confirm = input(f"¿Confirmar eliminación de {len(test_images)} imágenes de test? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Eliminación cancelada")
        return False

    deleted_count = 0
    error_count = 0

    for img in test_images:
        try:
            result = cloudinary.uploader.destroy(img['public_id'])
            if result.get('result') == 'ok':
                deleted_count += 1
                print(f"✅ Eliminado: {img['public_id']}")
            else:
                error_count += 1
                print(f"❌ Error al eliminar: {img['public_id']} - {result}")
        except Exception as e:
            error_count += 1
            print(f"❌ Error: {img['public_id']} - {e}")

    print(f"\\n📊 RESUMEN:")
    print(f"   ✅ Eliminadas: {deleted_count}")
    print(f"   ❌ Errores: {error_count}")

    return deleted_count > 0

if __name__ == "__main__":
    try:
        test_images, other_images = list_cloudinary_images()

        if test_images:
            success = delete_test_images(test_images)
            if success:
                print("\\n🎉 Limpieza completada exitosamente")
            else:
                print("\\n❌ Limpieza cancelada o con errores")
        else:
            print("\\n✅ No hay imágenes de test para limpiar")

        if other_images:
            print(f"\\n⚠️  Quedan {len(other_images)} imágenes no categorizadas")
            print("   Revisa manualmente si son necesarias")

    except Exception as e:
        print(f"\\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
