"""
Script simple para llamar directamente a WooCommerce API y ver estructura de imágenes
"""
import requests
from requests.auth import HTTPBasicAuth
import json

# Credenciales de goodyshop.com.ar
STORE_URL = "https://goodyshop.com.ar"
CONSUMER_KEY = "ck_cf4f58c4f3cd44ad1da4bed97d2a1d5fd0f04dff"
CONSUMER_SECRET = "cs_1ab56cc21af74b88bb4e54cf621eea7f3efd3ba9"

# Hacer request directamente
url = f"{STORE_URL}/wp-json/wc/v3/products?per_page=1"
auth = HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET)

response = requests.get(url, auth=auth, verify=True)

if response.status_code == 200:
    products = response.json()
    if products:
        product = products[0]
        print(f"✅ Producto: {product.get('name')}")
        images = product.get('images', [])
        print(f"\n🖼️  Total imágenes: {len(images)}")

        if images:
            print("\n" + "="*80)
            print("ESTRUCTURA COMPLETA DE IMAGEN:")
            print("="*80)
            print(json.dumps(images[0], indent=2))
            print("\n" + "="*80)
            print("CAMPOS DISPONIBLES:")
            print("="*80)
            for key, value in images[0].items():
                print(f"  {key:20s} = {value if not isinstance(value, str) or len(value) < 80 else value[:77]+'...'}")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
