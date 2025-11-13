#!/usr/bin/env python3
"""
Script para recalcular atributos de todos los productos de Goody Store
Usa AttributeAutofillService para extraer color, material, etc. desde imágenes con CLIP
"""

import sys
import os

# Agregar el directorio del backend al path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clip_admin_backend')
sys.path.insert(0, backend_path)

# Cambiar al directorio del backend para que las rutas relativas funcionen
original_dir = os.getcwd()
os.chdir(backend_path)

from app import db
from app.models import Client, Product
from app.services.attribute_autofill_service import AttributeAutofillService
from flask import Flask

def create_app():
    """Crear aplicación Flask mínima para el script"""
    app = Flask(__name__)

    # Configuración directa (ajusta la contraseña si es necesaria)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Laurana%4001@localhost:5432/clip_comparador_v2'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    return app

def recalculate_all_attributes():
    """Recalcula atributos para todos los productos de Goody Store"""
    app = create_app()

    with app.app_context():
        # Buscar cliente Goody Store
        goody = Client.query.filter_by(name='Goody Store').first()

        if not goody:
            print("❌ Cliente 'Goody Store' no encontrado")
            return

        print(f"🏪 Cliente encontrado: {goody.name} (ID: {goody.id})")

        # Obtener todos los productos del cliente
        products = Product.query.filter_by(client_id=goody.id).all()
        print(f"📦 Productos encontrados: {len(products)}")

        if not products:
            print("⚠️  No hay productos para procesar")
            return

        # Procesar cada producto
        success_count = 0
        error_count = 0
        skipped_count = 0

        for i, product in enumerate(products, 1):
            print(f"\n[{i}/{len(products)}] Procesando: {product.name}")

            # Verificar si tiene imágenes
            images_list = list(product.images)
            if not images_list or len(images_list) == 0:
                print(f"  ⏭️  Sin imágenes, saltando...")
                skipped_count += 1
                continue

            try:
                # Ejecutar autofill con overwrite=True para recalcular todo
                result = AttributeAutofillService.autofill_product_attributes(
                    product=product,
                    overwrite=True
                )

                if result.get('success'):
                    # IMPORTANTE: Guardar los atributos detectados en el producto
                    if result.get('attributes'):
                        if not product.attributes:
                            product.attributes = {}

                        # Actualizar attributes con los valores detectados
                        product.attributes.update(result['attributes'])

                        # Actualizar tags si se detectaron
                        if result.get('tags'):
                            product.tags = result['tags']

                        # Marcar como modificado (importante para JSONB)
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(product, 'attributes')

                        # COMMIT para persistir en BD
                        db.session.commit()

                    filled = len(result.get('attributes', {}))
                    print(f"  ✅ Atributos guardados en BD: {filled} atributos")
                    if result.get('attributes'):
                        for attr, value in result['attributes'].items():
                            print(f"     - {attr}: {value}")
                    success_count += 1
                else:
                    print(f"  ⚠️  Advertencia: {result.get('message', 'Sin mensaje')}")
                    error_count += 1

            except Exception as e:
                print(f"  ❌ Error procesando producto: {e}")
                error_count += 1
                db.session.rollback()
                # import traceback
                # traceback.print_exc()

        # Resumen final
        print("\n" + "="*60)
        print("📊 RESUMEN DE PROCESAMIENTO")
        print("="*60)
        print(f"✅ Exitosos:  {success_count}")
        print(f"❌ Errores:   {error_count}")
        print(f"⏭️  Saltados:  {skipped_count}")
        print(f"📦 Total:     {len(products)}")
        print("="*60)

if __name__ == "__main__":
    print("🔧 Iniciando recálculo de atributos para Goody Store...\n")
    recalculate_all_attributes()
    print("\n✅ Proceso completado")
