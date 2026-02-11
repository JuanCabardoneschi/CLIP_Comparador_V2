"""
Verificar qué información exacta devuelve WooCommerce API sobre imágenes
Usando requests directo sin autenticación (productos públicos)
"""
import requests
import json

# URL pública de producto de WooCommerce
# Intentemos obtener vía la API pública
store_url = "https://goodyshop.com.ar"

# Intentar obtener un producto público
# La API REST de WooCommerce puede estar restringida, pero intentemos

print("🔍 INVESTIGANDO API DE WOOCOMMERCE\n")

# Intentar endpoint público
endpoints = [
    f"{store_url}/wp-json/wc/v3/products/",
    f"{store_url}/wp-json/wc/store/products",
    f"{store_url}/wp-json/wp/v2/media"
]

for endpoint in endpoints:
    print(f"Probando: {endpoint}")
    try:
        resp = requests.get(endpoint, timeout=10, verify=True)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Datos: {type(data)}, {len(data) if isinstance(data, list) else 'N/A'} items")
            if isinstance(data, list) and len(data) > 0:
                print("\n  PRIMER ITEM:")
                print(json.dumps(data[0], indent=2)[:1000])
    except Exception as e:
        print(f"  Error: {e}")
    print()
