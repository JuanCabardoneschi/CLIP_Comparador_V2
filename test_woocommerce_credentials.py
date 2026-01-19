"""
Script de prueba para validar credenciales de WooCommerce
"""

import sys
import os

# Agregar el path del proyecto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from app.services.woocommerce_api_client import WooCommerceAPIClient

# Credenciales de la imagen
CONSUMER_KEY = "ck_60c02ad7d36562523219902c8724c37bc7b88370"
CONSUMER_SECRET = "cs_5ab6931f373d1f25eee022559e827a1f3ac270f"

# URL de la tienda (necesitas proporcionarla)
STORE_URL = input("Ingresa la URL de tu tienda WooCommerce (ej: https://goodyshop.com): ").strip()

print("\n" + "="*60)
print("🔍 PRUEBA DE CREDENCIALES WOOCOMMERCE")
print("="*60)
print(f"\n📍 URL: {STORE_URL}")
print(f"🔑 Consumer Key: {CONSUMER_KEY[:20]}...")
print(f"🔐 Consumer Secret: {CONSUMER_SECRET[:20]}...")
print("\n" + "-"*60)

try:
    # Crear cliente de API
    print("\n1️⃣  Creando cliente WooCommerce API...")
    client = WooCommerceAPIClient(STORE_URL, CONSUMER_KEY, CONSUMER_SECRET)

    # Probar conexión
    print("2️⃣  Probando conexión...")
    result = client.test_connection()

    if result.get("success"):
        print("\n✅ ¡CONEXIÓN EXITOSA!")
        print(f"   Tienda: {result.get('store_name', 'N/A')}")
        print(f"   WC Version: {result.get('wc_version', 'N/A')}")
        print(f"   WP Version: {result.get('wp_version', 'N/A')}")
        print(f"   URL API: {result.get('api_url', 'N/A')}")

        # Intentar obtener productos
        print("\n3️⃣  Obteniendo productos de prueba...")
        products_result = client.list_products(per_page=5)

        if products_result.get("success"):
            products = products_result.get("products", [])
            print(f"\n✅ Se encontraron {len(products)} productos (mostrando primeros 5):")
            for i, product in enumerate(products, 1):
                print(f"   {i}. {product.get('name')} (ID: {product.get('id')})")
        else:
            print(f"\n⚠️  No se pudieron obtener productos: {products_result.get('error')}")

        # Intentar obtener categorías
        print("\n4️⃣  Obteniendo categorías...")
        categories_result = client.list_categories(per_page=10)

        if categories_result.get("success"):
            categories = categories_result.get("categories", [])
            print(f"\n✅ Se encontraron {len(categories)} categorías (mostrando primeras 10):")
            for i, cat in enumerate(categories, 1):
                print(f"   {i}. {cat.get('name')} (ID: {cat.get('id')}, Count: {cat.get('count', 0)})")
        else:
            print(f"\n⚠️  No se pudieron obtener categorías: {categories_result.get('error')}")

        print("\n" + "="*60)
        print("✅ PRUEBA COMPLETADA CON ÉXITO")
        print("="*60)
        print("\n💡 Las credenciales son válidas y puedes usarlas para crear el cliente en CLIP.")

    else:
        print("\n❌ ERROR EN LA CONEXIÓN")
        print(f"   Razón: {result.get('error', 'Error desconocido')}")
        print("\n🔍 Verifica:")
        print("   1. La URL de la tienda es correcta")
        print("   2. Las credenciales son válidas")
        print("   3. La tienda tiene HTTPS habilitado")
        print("   4. Los permisos de API están habilitados en WooCommerce")

except Exception as e:
    print("\n❌ ERROR INESPERADO")
    print(f"   {str(e)}")
    print("\n🔍 Verifica que:")
    print("   1. La URL incluye http:// o https://")
    print("   2. No hay espacios en las credenciales")
    print("   3. La tienda está accesible")

print("\n" + "="*60 + "\n")
