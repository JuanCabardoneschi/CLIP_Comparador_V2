#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análisis simplificado de WooCommerce API.
"""

import sys
import json
import requests
from requests.auth import HTTPBasicAuth

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

STORE_URL = "https://goodyshop.com.ar"
CONSUMER_KEY = "ck_f33c84759c035cf972347fd7b811e4afc6411d31"
CONSUMER_SECRET = "cs_622b4487002880cb739a900c8f77c6ae310b9a3b"

def get_product_sample():
    """Obtener un producto de ejemplo."""
    url = f"{STORE_URL}/wp-json/wc/v3/products"
    response = requests.get(
        url,
        params={"per_page": 1},
        auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=10
    )

    if response.status_code != 200:
        print(f"ERROR: HTTP {response.status_code}")
        return None

    products = response.json()
    return products[0] if products else None

def analyze_images(product):
    """Analizar imágenes del producto."""
    print("\n[ANALISIS DE IMAGENES]")
    print("-" * 60)

    images = product.get('images', [])
    print(f"Total de imagenes: {len(images)}")

    if not images:
        print("El producto NO tiene imagenes")
        return

    print(f"\nEstructura de primera imagen:")
    print(json.dumps(images[0], indent=2, ensure_ascii=False))

    # Verificar acceso
    print("\n[VERIFICACION DE ACCESO A URLS]")
    for idx, img in enumerate(images[:2], 1):
        src = img.get('src')
        print(f"\nImagen {idx}:")
        print(f"  URL: {src[:80]}...")

        try:
            resp = requests.head(src, timeout=5)
            print(f"  Acceso: HTTP {resp.status_code} [EXITOSO]")
            print(f"  Content-Type: {resp.headers.get('Content-Type')}")
        except Exception as e:
            print(f"  Acceso: ERROR - {str(e)}")

def analyze_attributes(product):
    """Analizar atributos."""
    print("\n[ANALISIS DE ATRIBUTOS]")
    print("-" * 60)

    attrs = product.get('attributes', [])
    print(f"Total de atributos en producto: {len(attrs)}")

    if attrs:
        print("\nEstructura de atributos:")
        print(json.dumps(attrs, indent=2, ensure_ascii=False))
    else:
        print("Producto no tiene atributos asignados")

    # Obtener atributos globales
    print("\n[ATRIBUTOS GLOBALES DISPONIBLES EN TIENDA]")
    url = f"{STORE_URL}/wp-json/wc/v3/products/attributes"
    response = requests.get(
        url,
        auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=10
    )

    if response.status_code == 200:
        attributes = response.json()
        print(f"Total de atributos globales: {len(attributes)}")
        for attr in attributes[:3]:
            print(f"  - {attr['name']} (ID: {attr['id']}, tipo: {attr.get('type', 'N/A')})")
    else:
        print(f"ERROR al obtener atributos: HTTP {response.status_code}")

def analyze_categories(product):
    """Analizar categorías."""
    print("\n[ANALISIS DE CATEGORIAS]")
    print("-" * 60)

    cats = product.get('categories', [])
    print(f"Producto en {len(cats)} categoria(s):")
    for cat in cats:
        print(f"  - {cat['name']} (ID: {cat['id']})")

def analyze_variants():
    """Analizar variantes."""
    print("\n[VARIANTES DE PRODUCTOS]")
    print("-" * 60)

    url = f"{STORE_URL}/wp-json/wc/v3/products"
    response = requests.get(
        url,
        params={"per_page": 20, "type": "variable"},
        auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=10
    )

    if response.status_code != 200:
        print(f"ERROR: HTTP {response.status_code}")
        return

    products = response.json()
    var_product = None

    for p in products:
        if p.get('type') == 'variable':
            var_product = p
            break

    if not var_product:
        print("No se encontraron productos con variantes")
        return

    print(f"Producto encontrado: {var_product['name']}")
    print(f"  Tipo: {var_product['type']}")
    print(f"  ID: {var_product['id']}")

    # Obtener variantes
    url_var = f"{STORE_URL}/wp-json/wc/v3/products/{var_product['id']}/variations"
    resp_var = requests.get(
        url_var,
        params={"per_page": 1},
        auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=10
    )

    if resp_var.status_code == 200:
        variations = resp_var.json()
        if variations:
            print("\nEstructura de primera variante:")
            print(json.dumps(variations[0], indent=2, ensure_ascii=False)[:500])
            print("...")
    else:
        print(f"ERROR obteniendo variantes: HTTP {resp_var.status_code}")

if __name__ == "__main__":
    print("=" * 60)
    print("ANALISIS DE WOOCOMMERCE API")
    print("=" * 60)

    product = get_product_sample()
    if not product:
        print("No se pudo obtener producto de ejemplo")
        sys.exit(1)

    print(f"\nProducto analizado: {product['name']}")
    print(f"ID: {product['id']}, Tipo: {product['type']}")

    analyze_images(product)
    analyze_attributes(product)
    analyze_categories(product)
    analyze_variants()

    print("\n" + "=" * 60)
    print("ANALISIS COMPLETADO")
    print("=" * 60)
