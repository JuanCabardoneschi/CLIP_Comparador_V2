#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eliminar Imágenes Sample de Cloudinary
Elimina las imágenes de muestra que vienen por defecto
"""
import os
import sys
from pathlib import Path
import time

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

def delete_sample_images():
    """Eliminar todas las imágenes sample de Cloudinary"""
    print("🗑️  ELIMINANDO IMÁGENES SAMPLE DE CLOUDINARY")
    print("="*50)

    configure_cloudinary()

    try:
        # Listar todas las imágenes en la carpeta samples
        print("🔍 Buscando imágenes sample...")

        # Buscar en la carpeta 'samples' que es donde Cloudinary pone las muestras
        sample_resources = cloudinary.api.resources(
            type="upload",
            prefix="samples/",
            max_results=500
        )

        sample_images = sample_resources.get('resources', [])
        total_samples = len(sample_images)

        print(f"📊 Imágenes sample encontradas: {total_samples}")

        if total_samples == 0:
            print("✅ No hay imágenes sample para eliminar")
            return True

        # Mostrar lista de imágenes sample
        print("\\n📋 Imágenes sample encontradas:")
        for img in sample_images:
            print(f"   🖼️  {img['public_id']} ({img.get('format', 'unknown')})")

        # Confirmar eliminación
        confirm = input(f"\\n¿Eliminar {total_samples} imágenes sample? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Eliminación cancelada")
            return False

        # Eliminar imágenes
        deleted_count = 0
        error_count = 0

        print(f"\\n🗑️  Eliminando imágenes...")

        for i, img in enumerate(sample_images, 1):
            try:
                public_id = img['public_id']
                print(f"[{i}/{total_samples}] Eliminando: {public_id}")

                # Eliminar imagen
                result = cloudinary.uploader.destroy(public_id)

                if result.get('result') == 'ok':
                    deleted_count += 1
                    print(f"✅ Eliminado: {public_id}")
                else:
                    error_count += 1
                    print(f"❌ Error eliminando {public_id}: {result}")

                # Pausa pequeña para no saturar la API
                time.sleep(0.1)

            except Exception as e:
                error_count += 1
                print(f"❌ Error con {public_id}: {e}")
                continue

        # Resumen
        print(f"\\n📈 RESUMEN DE ELIMINACIÓN")
        print("="*40)
        print(f"✅ Eliminadas: {deleted_count}")
        print(f"❌ Errores: {error_count}")
        print(f"📊 Total procesadas: {deleted_count + error_count}/{total_samples}")

        # También intentar eliminar la carpeta samples si está vacía
        if deleted_count > 0:
            try:
                print("\\n🗂️  Intentando eliminar carpeta samples...")
                cloudinary.api.delete_folder("samples")
                print("✅ Carpeta samples eliminada")
            except Exception as e:
                print(f"⚠️  No se pudo eliminar la carpeta samples: {e}")

        return deleted_count > 0

    except Exception as e:
        print(f"❌ Error al listar imágenes sample: {e}")
        return False

def verify_cleanup():
    """Verificar que las imágenes sample fueron eliminadas"""
    print("\\n🔍 VERIFICANDO LIMPIEZA...")

    try:
        # Verificar que no queden samples
        sample_resources = cloudinary.api.resources(
            type="upload",
            prefix="samples/",
            max_results=10
        )

        remaining_samples = len(sample_resources.get('resources', []))

        if remaining_samples == 0:
            print("✅ Todas las imágenes sample fueron eliminadas")
        else:
            print(f"⚠️  Quedan {remaining_samples} imágenes sample")

        # Mostrar todas las carpetas actuales
        print("\\n📁 Carpetas actuales en Cloudinary:")
        folders = cloudinary.api.root_folders()
        for folder in folders.get('folders', []):
            print(f"   📂 {folder['name']}")

        return remaining_samples == 0

    except Exception as e:
        print(f"❌ Error verificando: {e}")
        return False

if __name__ == "__main__":
    try:
        print("🚀 Iniciando limpieza de imágenes sample...")
        success = delete_sample_images()

        if success:
            verify_cleanup()
            print("\\n🎉 ¡Limpieza completada!")
            print("\\n📋 SIGUIENTE PASO:")
            print("   Actualizar referencias en base de datos")
        else:
            print("\\n❌ La limpieza no se completó")

    except Exception as e:
        print(f"\\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
