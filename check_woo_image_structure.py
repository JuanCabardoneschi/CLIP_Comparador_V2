"""
Script para verificar estructura de imágenes en WooCommerce API
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from app import create_app
from app.models import WooCommerceIntegration
from app.services.woocommerce_api_client import WooCommerceAPIClient
import json

app = create_app()

with app.app_context():
    client_id = '0fb8cf5d-1ae6-40dd-9741-4004110202a8'
    woo = WooCommerceIntegration.query.filter_by(client_id=client_id).first()

    if not woo:
        print("❌ No se encontró integración WooCommerce")
        sys.exit(1)

    print(f"✅ Store: {woo.store_url}")

    api = WooCommerceAPIClient(woo.store_url, woo.consumer_key, woo.consumer_secret)

    # Obtener 1 producto
    products = api.get_products(per_page=1)

    if not products:
        print("❌ No se encontraron productos")
        sys.exit(1)

    product = products[0]
    print(f"\n📦 Producto: {product.get('name')}")
    print(f"ID: {product.get('id')}")

    images = product.get('images', [])
    print(f"\n🖼️  Imágenes: {len(images)}")

    if images:
        print("\n" + "="*80)
        print("ESTRUCTURA DE IMAGEN EN WOOCOMMERCE API:")
        print("="*80)
        print(json.dumps(images[0], indent=2))
        print("\n" + "="*80)
        print("CLAVES DISPONIBLES:")
        print("="*80)
        for key in images[0].keys():
            print(f"  - {key}: {type(images[0][key]).__name__}")
