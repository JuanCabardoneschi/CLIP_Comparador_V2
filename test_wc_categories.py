#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test WooCommerce API - Solo obtener categorías con permisos de lectura
Según la documentación oficial de WooCommerce REST API
"""

import requests

# Configuración de la tienda
STORE_URL = "https://goodyshop.com.ar"
CONSUMER_KEY = "ck_f33c84759c035cf972347fd7b811e4afc6411d31"
CONSUMER_SECRET = "cs_622b4487002880cb739a900c8f77c6ae310b9a3b"

# Endpoint de categorías
url = f"{STORE_URL}/wp-json/wc/v3/products/categories"

print("=" * 70)
print("🔍 TEST WOOCOMMERCE - OBTENER CATEGORÍAS (SOLO LECTURA)")
print("=" * 70)
print(f"\n📍 Tienda: {STORE_URL}")
print(f"🔗 Endpoint: {url}")
print(f"🔑 Consumer Key: {CONSUMER_KEY[:20]}...")
print(f"🔐 Consumer Secret: {CONSUMER_SECRET[:20]}...")

print("\n" + "-" * 70)
print("📦 Obteniendo categorías de productos...")
print("-" * 70)

# Método 1: Query parameters (recomendado para problemas con FastCGI)
params = {
    "consumer_key": CONSUMER_KEY,
    "consumer_secret": CONSUMER_SECRET,
    "per_page": 20  # Obtener hasta 20 categorías
}

try:
    response = requests.get(url, params=params, timeout=15)

    print(f"\n✅ Status Code: {response.status_code}")

    if response.status_code == 200:
        categories = response.json()

        print(f"\n🎯 Total de categorías obtenidas: {len(categories)}")
        print("\n" + "=" * 70)
        print("CATEGORÍAS ENCONTRADAS:")
        print("=" * 70)

        for i, cat in enumerate(categories, 1):
            print(f"\n{i}. {cat.get('name', 'Sin nombre')}")
            print(f"   ID: {cat.get('id')}")
            print(f"   Slug: {cat.get('slug', 'N/A')}")
            print(f"   Descripción: {cat.get('description', 'Sin descripción')[:100]}")
            print(f"   Cantidad de productos: {cat.get('count', 0)}")
            if cat.get('parent'):
                print(f"   Categoría padre ID: {cat.get('parent')}")

        print("\n" + "=" * 70)
        print("✅ ÉXITO: Las credenciales funcionan correctamente")
        print("=" * 70)

    elif response.status_code == 401:
        print("\n❌ ERROR 401: No autorizado")
        print(f"Respuesta: {response.text}")
        print("\n💡 Verifica que:")
        print("   1. Las claves sean exactamente las generadas en WooCommerce")
        print("   2. Los permisos sean 'Lectura' o 'Lectura/Escritura'")
        print("   3. El usuario asociado tenga permisos de administrador")

    else:
        print(f"\n⚠️  Status inesperado: {response.status_code}")
        print(f"Respuesta: {response.text}")

except requests.exceptions.Timeout:
    print("\n❌ ERROR: Tiempo de espera agotado")
    print("   La tienda no respondió en 15 segundos")

except requests.exceptions.ConnectionError:
    print("\n❌ ERROR: No se pudo conectar a la tienda")
    print(f"   Verifica que {STORE_URL} esté accesible")

except Exception as e:
    print(f"\n❌ ERROR inesperado: {str(e)}")

print("\n" + "=" * 70)
