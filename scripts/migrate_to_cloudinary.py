#!/usr/bin/env python3
"""
Script de Migración de Imágenes a Cloudinary
Subir todas las imágenes locales existentes a Cloudinary
"""
import os
import sys
import time
from pathlib import Path

# Añadir paths para importar modelos Flask
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
backend_dir = os.path.join(parent_dir, 'clip_admin_backend')
sys.path.insert(0, backend_dir)
sys.path.insert(0, parent_dir)

from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def migrate_images_to_cloudinary():
    """Migrar todas las imágenes locales a Cloudinary"""

    print("🚀 INICIANDO MIGRACIÓN DE IMÁGENES A CLOUDINARY")
    print("=" * 60)

    # Importar después de configurar paths
    try:
        # Cambiar al directorio backend para importaciones
        os.chdir(backend_dir)

        # Importar la función create_app desde app.py
        import app as flask_app
        from app import db
        from app.models.image import Image
        from app.models.product import Product
        from app.models.client import Client
        from app.services.cloudinary_manager import cloudinary_manager
    except ImportError as e:
        print(f"❌ Error importando módulos: {e}")
        print("Asegúrate de estar en el directorio correcto y tener las dependencias instaladas")
        return False

    # Crear aplicación Flask
    app = flask_app.create_app()

    with app.app_context():
        print("📊 ANALIZANDO ESTADO ACTUAL...")

        # Verificar conexión con Cloudinary
        if not cloudinary_manager.test_connection():
            print("❌ Error: No se puede conectar con Cloudinary")
            print("Revisa tus credenciales en el archivo .env:")
            print("- CLOUDINARY_CLOUD_NAME")
            print("- CLOUDINARY_API_KEY")
            print("- CLOUDINARY_API_SECRET")
            return False

        # Obtener estadísticas actuales
        total_images = Image.query.count()
        images_with_cloudinary = Image.query.filter(
            (Image.cloudinary_url.isnot(None)) &
            (Image.cloudinary_url != '')
        ).count()
        images_without_cloudinary = total_images - images_with_cloudinary

        print(f"📈 ESTADÍSTICAS ACTUALES:")
        print(f"   • Total imágenes en BD: {total_images}")
        print(f"   • Con URL Cloudinary: {images_with_cloudinary}")
        print(f"   • Sin URL Cloudinary: {images_without_cloudinary}")

        # Directorio de imágenes locales
        local_images_dir = Path(backend_dir) / "static" / "uploads" / "clients" / "demo_fashion_store"

        if not local_images_dir.exists():
            print(f"❌ Directorio de imágenes no encontrado: {local_images_dir}")
            return False

        # Contar archivos locales
        local_files = list(local_images_dir.glob("*.*"))
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
        local_images = [f for f in local_files if f.suffix.lower() in image_extensions]

        print(f"📁 ARCHIVOS LOCALES:")
        print(f"   • Total archivos: {len(local_files)}")
        print(f"   • Imágenes válidas: {len(local_images)}")
        print(f"   • Directorio: {local_images_dir}")

        if not local_images:
            print("⚠️ No se encontraron imágenes locales para migrar")
            return True

        print("\\n" + "="*60)
        print("🔄 INICIANDO MIGRACIÓN...")
        print("="*60)

        # Contadores
        migrated = 0
        skipped = 0
        errors = 0

        # Obtener cliente demo
        demo_client = Client.query.filter_by(slug='demo_fashion_store').first()
        if not demo_client:
            print("❌ Cliente demo no encontrado. Creando cliente...")
            demo_client = Client(
                name="Demo Fashion Store",
                slug="demo_fashion_store",
                email="demo@fashionstore.com",
                industry="textil"
            )
            db.session.add(demo_client)
            db.session.commit()
            print(f"✅ Cliente demo creado: {demo_client.id}")

        client_id = demo_client.id
        client_slug = demo_client.slug

        # Procesar cada imagen local
        for i, local_file in enumerate(local_images, 1):
            filename = local_file.name

            print(f"\\n[{i}/{len(local_images)}] Procesando: {filename[:50]}...")

            # Verificar si ya existe en BD con Cloudinary URL
            existing_image = Image.query.filter_by(
                client_id=client_id,
                filename=filename
            ).first()

            if existing_image and existing_image.cloudinary_url:
                print(f"   ⏭️  Ya existe en Cloudinary: {existing_image.cloudinary_url}")
                skipped += 1
                continue

            # Buscar producto asociado (si existe)
            product_id = None
            if existing_image and existing_image.product_id:
                product_id = existing_image.product_id
            else:
                # Buscar producto por nombre similar (opcional)
                # Por ahora usamos un producto genérico o creamos uno
                product = Product.query.filter_by(client_id=client_id).first()
                if product:
                    product_id = product.id
                else:
                    # Crear producto genérico para imágenes huérfanas
                    generic_product = Product(
                        client_id=client_id,
                        name="Producto Genérico",
                        description="Producto creado automáticamente para imágenes migradas",
                        sku="GEN-001"
                    )
                    db.session.add(generic_product)
                    db.session.commit()
                    product_id = generic_product.id
                    print(f"   📦 Producto genérico creado: {product_id}")

            try:
                # Subir imagen a Cloudinary
                if existing_image:
                    # Actualizar registro existente
                    result = cloudinary_manager.upload_local_file(
                        local_path=str(local_file),
                        product_id=product_id,
                        client_id=client_id,
                        client_slug=client_slug,
                        is_primary=existing_image.is_primary
                    )

                    if result:
                        # Actualizar registro existente con datos de Cloudinary
                        existing_image.cloudinary_url = result.cloudinary_url
                        existing_image.cloudinary_public_id = result.cloudinary_public_id
                        existing_image.width = result.width
                        existing_image.height = result.height
                        existing_image.file_size = result.file_size
                        existing_image.upload_status = "uploaded"
                        existing_image.is_processed = True

                        # Eliminar el registro duplicado que se creó
                        db.session.delete(result)
                        db.session.commit()

                        print(f"   ✅ Actualizado en BD: {existing_image.cloudinary_url}")
                    else:
                        print(f"   ❌ Error subiendo imagen")
                        errors += 1
                        continue
                else:
                    # Crear nuevo registro
                    result = cloudinary_manager.upload_local_file(
                        local_path=str(local_file),
                        product_id=product_id,
                        client_id=client_id,
                        client_slug=client_slug,
                        is_primary=False
                    )

                    if result:
                        print(f"   ✅ Nuevo registro creado: {result.cloudinary_url}")
                    else:
                        print(f"   ❌ Error creando registro")
                        errors += 1
                        continue

                migrated += 1

                # Pausa pequeña para no sobrecargar Cloudinary
                time.sleep(0.5)

            except Exception as e:
                print(f"   ❌ Error: {e}")
                errors += 1
                continue

        print("\\n" + "="*60)
        print("📊 RESUMEN DE MIGRACIÓN")
        print("="*60)
        print(f"✅ Imágenes migradas: {migrated}")
        print(f"⏭️ Imágenes omitidas: {skipped}")
        print(f"❌ Errores: {errors}")
        print(f"📈 Total procesadas: {migrated + skipped + errors}")

        # Estadísticas finales
        final_total = Image.query.count()
        final_with_cloudinary = Image.query.filter(
            (Image.cloudinary_url.isnot(None)) &
            (Image.cloudinary_url != '')
        ).count()

        print(f"\\n📊 ESTADÍSTICAS FINALES:")
        print(f"   • Total imágenes en BD: {final_total}")
        print(f"   • Con URL Cloudinary: {final_with_cloudinary}")
        print(f"   • Porcentaje migrado: {(final_with_cloudinary/final_total*100):.1f}%")

        if errors == 0:
            print("\\n🎉 ¡MIGRACIÓN COMPLETADA EXITOSAMENTE!")
        else:
            print(f"\\n⚠️ Migración completada con {errors} errores")

        return errors == 0


def main():
    """Función principal"""
    print("📋 PREREQUISITOS:")
    print("1. ✅ Archivo .env configurado con credenciales Cloudinary")
    print("2. ✅ Base de datos SQLite funcionando")
    print("3. ✅ Imágenes locales en static/uploads/clients/demo_fashion_store/")
    print("\\nPresiona Enter para continuar o Ctrl+C para cancelar...")

    try:
        input()
    except KeyboardInterrupt:
        print("\\n❌ Migración cancelada por el usuario")
        return

    success = migrate_images_to_cloudinary()

    if success:
        print("\\n✅ ¡Migración exitosa! Ya puedes:")
        print("   1. Actualizar el código para usar URLs de Cloudinary")
        print("   2. Probar el sistema con imágenes en la nube")
        print("   3. Hacer deploy a Railway sin archivos locales")
    else:
        print("\\n❌ Migración falló. Revisa los errores y vuelve a intentar.")


if __name__ == "__main__":
    main()
