#!/usr/bin/env python3
"""
Script de Migración Simple de Imágenes a Cloudinary
"""
import os
import sys
import time
from pathlib import Path

# Cambiar al directorio correcto
backend_dir = os.path.join(os.path.dirname(__file__), '..', 'clip_admin_backend')
os.chdir(backend_dir)
sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv
load_dotenv()

# Ejecutar directamente la lógica del app.py
exec(open('app.py').read())

def migrate_simple():
    """Migración simple usando el contexto de Flask ya cargado"""

    print("🚀 MIGRACIÓN SIMPLE A CLOUDINARY")
    print("="*50)

    # Importar servicios
    from app.services.cloudinary_manager import cloudinary_manager
    from app.models.image import Image
    from app.models.client import Client

    # Usar el contexto de la app ya creada
    with app.app_context():

        # Probar conexión
        if not cloudinary_manager.test_connection():
            print("❌ Error conectando con Cloudinary")
            return False

        print("✅ Conexión Cloudinary exitosa")

        # Obtener cliente demo
        demo_client = Client.query.filter_by(slug='demo_fashion_store').first()
        if not demo_client:
            print("❌ Cliente demo no encontrado")
            return False

        print(f"✅ Cliente demo: {demo_client.name}")

        # Directorio de imágenes
        images_dir = Path("static/uploads/clients/demo_fashion_store")
        if not images_dir.exists():
            print(f"❌ Directorio no encontrado: {images_dir}")
            return False

        # Obtener archivos de imagen
        image_files = []
        for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            image_files.extend(images_dir.glob(f"*{ext}"))
            image_files.extend(images_dir.glob(f"*{ext.upper()}"))

        print(f"📁 Encontradas {len(image_files)} imágenes")

        if not image_files:
            print("⚠️ No hay imágenes para migrar")
            return True

        # Crear producto genérico si no existe
        from app.models.product import Product
        generic_product = Product.query.filter_by(
            client_id=demo_client.id,
            name="Producto Genérico"
        ).first()

        if not generic_product:
            # Necesitamos una categoría primero
            from app.models.category import Category
            generic_category = Category.query.filter_by(
                client_id=demo_client.id,
                name="General"
            ).first()

            if not generic_category:
                generic_category = Category(
                    client_id=demo_client.id,
                    name="General",
                    description="Categoría general"
                )
                db.session.add(generic_category)
                db.session.commit()
                print("✅ Categoría genérica creada")

            generic_product = Product(
                client_id=demo_client.id,
                category_id=generic_category.id,
                name="Producto Genérico",
                description="Producto para imágenes migradas",
                sku="MIGRATED-001"
            )
            db.session.add(generic_product)
            db.session.commit()
            print("✅ Producto genérico creado")

        # Migrar imágenes
        migrated = 0
        errors = 0

        for i, image_file in enumerate(image_files[:5], 1):  # Solo las primeras 5 para prueba
            print(f"\\n[{i}/5] {image_file.name}")

            try:
                # Verificar si ya existe
                existing = Image.query.filter_by(
                    client_id=demo_client.id,
                    filename=image_file.name
                ).first()

                if existing and existing.cloudinary_url:
                    print(f"   ⏭️ Ya existe en Cloudinary")
                    continue

                # Subir a Cloudinary
                result = cloudinary_manager.upload_local_file(
                    local_path=str(image_file),
                    product_id=generic_product.id,
                    client_id=demo_client.id,
                    client_slug=demo_client.slug,
                    is_primary=(i == 1)
                )

                if result:
                    if existing:
                        # Actualizar existente
                        existing.cloudinary_url = result.cloudinary_url
                        existing.cloudinary_public_id = result.cloudinary_public_id
                        existing.upload_status = "uploaded"
                        # Eliminar el duplicado
                        db.session.delete(result)
                        db.session.commit()

                    print(f"   ✅ Migrada: {result.cloudinary_url}")
                    migrated += 1
                else:
                    print(f"   ❌ Error en la migración")
                    errors += 1

                time.sleep(1)  # Pausa entre uploads

            except Exception as e:
                print(f"   ❌ Error: {e}")
                errors += 1

        print(f"\\n📊 RESULTADO:")
        print(f"✅ Migradas: {migrated}")
        print(f"❌ Errores: {errors}")

        if migrated > 0:
            print("\\n🎉 ¡Migración de prueba exitosa!")
            print("Para migrar todas las imágenes, modifica el script")

        return errors == 0

if __name__ == "__main__":
    print("🧪 MIGRACIÓN DE PRUEBA (5 imágenes)")
    migrate_simple()
