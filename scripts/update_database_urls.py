#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actualizar Referencias de Imágenes en Base de Datos
Actualiza las URLs de imágenes locales por URLs de Cloudinary
"""
import os
import sys
import json
from pathlib import Path

# Configurar el proyecto
project_root = Path(__file__).parent.parent
backend_dir = project_root / "clip_admin_backend"
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

# Importar la aplicación Flask correctamente
import importlib.util
app_spec = importlib.util.spec_from_file_location("app", backend_dir / "app.py")
app_module = importlib.util.module_from_spec(app_spec)
app_spec.loader.exec_module(app_module)

app = app_module.create_app()
from app.models.client import Product
from app import db

def update_image_urls():
    """Actualizar URLs de imágenes en la base de datos"""
    print("🔄 ACTUALIZACIÓN DE URLS EN BASE DE DATOS")
    print("="*50)

    # Cargar el mapeo de migración
    mapping_file = project_root / "cloudinary_migration_mapping.json"
    if not mapping_file.exists():
        print(f"❌ Error: Archivo de mapeo no encontrado: {mapping_file}")
        return False

    with open(mapping_file, 'r', encoding='utf-8') as f:
        url_mapping = json.load(f)

    print(f"📄 Cargado mapeo con {len(url_mapping)} imágenes migradas")

    with app.app_context():
        # Obtener todos los productos
        products = Product.query.all()
        print(f"📦 Productos encontrados: {len(products)}")

        updated_count = 0
        not_found_count = 0

        for product in products:
            if not product.image_url:
                continue

            # Normalizar la URL del producto para buscar en el mapeo
            # Convertir /static/uploads/... a uploads\\...
            normalized_url = product.image_url.replace('/static/', '').replace('/', '\\\\')

            print(f"\\n🔍 Producto: {product.name}")
            print(f"   URL actual: {product.image_url}")
            print(f"   Buscando: {normalized_url}")

            if normalized_url in url_mapping:
                old_url = product.image_url
                new_url = url_mapping[normalized_url]['cloudinary_url']

                product.image_url = new_url
                updated_count += 1

                print(f"   ✅ Actualizado: {new_url}")
            else:
                not_found_count += 1
                print(f"   ❌ No encontrado en Cloudinary (imagen > 10MB o error)")

        # Confirmar cambios
        if updated_count > 0:
            confirm = input(f"\\n¿Guardar {updated_count} cambios en la base de datos? (y/N): ")
            if confirm.lower() == 'y':
                try:
                    db.session.commit()
                    print(f"✅ {updated_count} productos actualizados exitosamente")
                except Exception as e:
                    db.session.rollback()
                    print(f"❌ Error al guardar cambios: {e}")
                    return False
            else:
                db.session.rollback()
                print("❌ Cambios descartados")
                return False

        print(f"\\n📊 RESUMEN:")
        print(f"   ✅ Actualizados: {updated_count}")
        print(f"   ❌ No encontrados: {not_found_count}")
        print(f"   📦 Total procesados: {updated_count + not_found_count}")

        return updated_count > 0

def verify_updates():
    """Verificar que las actualizaciones se realizaron correctamente"""
    print("\\n🔍 VERIFICACIÓN DE ACTUALIZACIONES")
    print("="*40)

    with app.app_context():
        products = Product.query.all()

        cloudinary_count = 0
        local_count = 0

        for product in products:
            if not product.image_url:
                continue

            if 'cloudinary.com' in product.image_url:
                cloudinary_count += 1
            elif '/static/' in product.image_url:
                local_count += 1
                print(f"⚠️  Producto con URL local: {product.name} - {product.image_url}")

        print(f"\\n📊 ESTADO ACTUAL:")
        print(f"   ☁️  URLs de Cloudinary: {cloudinary_count}")
        print(f"   💽 URLs locales: {local_count}")

        if local_count == 0:
            print("\\n🎉 ¡Todas las imágenes están en Cloudinary!")
            return True
        else:
            print(f"\\n⚠️  Quedan {local_count} imágenes locales (probablemente > 10MB)")
            return False

if __name__ == "__main__":
    try:
        print("🚀 Iniciando actualización de URLs...")
        success = update_image_urls()

        if success:
            verify_updates()
            print("\\n✅ Proceso completado exitosamente")
            print("\\n📋 PRÓXIMOS PASOS:")
            print("   1. Verificar que las imágenes se muestran correctamente")
            print("   2. Para imágenes > 10MB, considerar redimensionar y volver a subir")
            print("   3. Después de verificar, eliminar archivos locales")
        else:
            print("\\n❌ No se realizaron actualizaciones")

    except Exception as e:
        print(f"\\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
