#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de Conexión Cloudinary
"""
import os
import sys
from pathlib import Path

# Asegurarse de usar el directorio correcto
project_root = Path(__file__).parent.parent
backend_dir = project_root / "clip_admin_backend"
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

# Test de conexión básico
import cloudinary
import cloudinary.api
import cloudinary.uploader

def test_cloudinary():
    """Test básico de conexión"""
    print("🧪 TEST DE CONEXIÓN CLOUDINARY")
    print("="*40)

    # Configurar
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET")
    )

    print(f"Cloud: {os.getenv('CLOUDINARY_CLOUD_NAME')}")
    print(f"API Key: {os.getenv('CLOUDINARY_API_KEY')[:10]}...")

    try:
        # Test de ping
        result = cloudinary.api.ping()
        print(f"✅ Conexión exitosa: {result}")

        # Test de subida de imagen
        print("\\n🧪 Test de subida...")
        images_dir = Path("static/uploads/clients/demo_fashion_store")

        if images_dir.exists():
            image_files = list(images_dir.glob("*.jpg"))[:1]  # Solo 1 imagen

            if image_files:
                test_image = image_files[0]
                print(f"Subiendo: {test_image.name}")

                upload_result = cloudinary.uploader.upload(
                    str(test_image),
                    public_id=f"test/clip_v2_test_{test_image.stem}",
                    folder="test",
                )

                print(f"✅ Subida exitosa: {upload_result['secure_url']}")
                print(f"📊 Tamaño: {upload_result.get('bytes', 'N/A')} bytes")
                print(f"📐 Dimensiones: {upload_result.get('width')}x{upload_result.get('height')}")

                # Eliminar la imagen de prueba
                cloudinary.uploader.destroy(upload_result['public_id'])
                print("🗑️ Imagen de prueba eliminada")

                return True
            else:
                print("❌ No hay imágenes para probar")
        else:
            print(f"❌ Directorio no encontrado: {images_dir}")

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_cloudinary()
    if success:
        print("\\n🎉 ¡Cloudinary configurado correctamente!")
        print("Ya puedes proceder con la migración completa")
    else:
        print("\\n❌ Revisa la configuración de Cloudinary")
