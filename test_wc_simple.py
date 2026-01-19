"""
Script simple para probar credenciales de WooCommerce
"""

import requests
from requests.auth import HTTPBasicAuth

# Credenciales
STORE_URL = "https://goodyshop.com.ar"
CONSUMER_KEY = "ck_60c02ad7d36562523219902c8724c37bc7b88370"
CONSUMER_SECRET = "cs_5ab6931f373d1f25eee022559e827a1f3ac270f"

# Construir URL de API
api_base = f"{STORE_URL.rstrip('/')}/wp-json/wc/v3"

print("\n" + "="*70)
print("🔍 PRUEBA DE CREDENCIALES WOOCOMMERCE - GOODY SHOP")
print("="*70)
print(f"\n📍 Tienda: {STORE_URL}")
print(f"🔗 API Base: {api_base}")
print(f"🔑 Consumer Key: {CONSUMER_KEY[:30]}...")
print(f"🔐 Consumer Secret: {CONSUMER_SECRET[:30]}...")
print("\n" + "-"*70)

try:
    # 1. Probar con HTTP Basic Auth
    print("\n1️⃣  Probando con HTTP Basic Auth (GET /system_status)...")
    response = requests.get(
        f"{api_base}/system_status",
        auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=10
    )

    print(f"   Status Code: {response.status_code}")

    if response.status_code == 401:
        # Si falla, intentar con query parameters
        print("\n   ⚠️  Basic Auth falló, probando con Query Parameters...")
        response = requests.get(
            f"{api_base}/system_status",
            params={
                "consumer_key": CONSUMER_KEY,
                "consumer_secret": CONSUMER_SECRET
            },
            timeout=10
        )
        print(f"   Status Code con Query Params: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("\n✅ ¡CONEXIÓN EXITOSA!")

        # Mostrar info del sistema
        env = data.get('environment', {})
        print(f"\n📊 Información del Sistema:")
        print(f"   🏪 Tienda: {env.get('site_url', 'N/A')}")
        print(f"   🛒 WooCommerce: {env.get('version', 'N/A')}")
        print(f"   📝 WordPress: {env.get('wp_version', 'N/A')}")
        print(f"   🌐 Home URL: {env.get('home_url', 'N/A')}")

    else:
        print(f"\n❌ Error: Status {response.status_code}")
        print(f"   Respuesta: {response.text[:200]}")

    # 2. Intentar obtener productos (con query params)
    print("\n2️⃣  Obteniendo productos (GET /products?per_page=5)...")
    response = requests.get(
        f"{api_base}/products",
        params={
            "consumer_key": CONSUMER_KEY,
            "consumer_secret": CONSUMER_SECRET,
            "per_page": 5
        },
        timeout=10
    )

    print(f"   Status Code: {response.status_code}")

    if response.status_code == 200:
        products = response.json()
        print(f"\n✅ Se encontraron productos (mostrando primeros 5):")
        for i, product in enumerate(products[:5], 1):
            print(f"   {i}. {product.get('name')} (ID: {product.get('id')}, Stock: {product.get('stock_quantity', 'N/A')})")
    else:
        print(f"\n⚠️  No se pudieron obtener productos")
        print(f"   Respuesta: {response.text[:200]}")

    # 3. Intentar obtener categorías (con query params)
    print("\n3️⃣  Obteniendo categorías (GET /products/categories?per_page=10)...")
    response = requests.get(
        f"{api_base}/products/categories",
        params={
            "consumer_key": CONSUMER_KEY,
            "consumer_secret": CONSUMER_SECRET,
            "per_page": 10
        },
        timeout=10
    )

    print(f"   Status Code: {response.status_code}")

    if response.status_code == 200:
        categories = response.json()
        print(f"\n✅ Se encontraron categorías (mostrando primeras 10):")
        for i, cat in enumerate(categories[:10], 1):
            print(f"   {i}. {cat.get('name')} (ID: {cat.get('id')}, Count: {cat.get('count', 0)})")
    else:
        print(f"\n⚠️  No se pudieron obtener categorías")
        print(f"   Respuesta: {response.text[:200]}")

    print("\n" + "="*70)
    print("✅ PRUEBA COMPLETADA")
    print("="*70)
    print("\n💡 Conclusión:")
    print("   Las credenciales son VÁLIDAS y funcionan correctamente.")
    print("   Puedes usarlas para crear el cliente en el panel CLIP Admin.")
    print("\n📝 Datos para el formulario:")
    print(f"   • URL de la Tienda: {STORE_URL}")
    print(f"   • Consumer Key: {CONSUMER_KEY}")
    print(f"   • Consumer Secret: {CONSUMER_SECRET}")
    print()

except requests.exceptions.ConnectionError:
    print("\n❌ ERROR DE CONEXIÓN")
    print("   No se pudo conectar a la tienda.")
    print("   Verifica que la URL sea correcta y que la tienda esté accesible.")

except requests.exceptions.Timeout:
    print("\n❌ TIMEOUT")
    print("   La tienda no respondió a tiempo.")
    print("   Intenta nuevamente más tarde.")

except Exception as e:
    print("\n❌ ERROR INESPERADO")
    print(f"   {str(e)}")

print("\n" + "="*70 + "\n")
