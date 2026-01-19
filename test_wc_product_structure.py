#!/usr/bin/env python3
"""
Análisis de estructura de productos WooCommerce.
Determina cómo acceder a imágenes, atributos y categorías.
"""

import sys
import json
import requests
from requests.auth import HTTPBasicAuth

# Configurar encoding UTF-8 para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Credenciales de prueba
STORE_URL = "https://goodyshop.com.ar"
CONSUMER_KEY = "ck_f33c84759c035cf972347fd7b811e4afc6411d31"
CONSUMER_SECRET = "cs_622b4487002880cb739a900c8f77c6ae310b9a3b"

def test_product_structure():
    """Obtener estructura completa de un producto."""
    print("=" * 80)
    print("[ESTRUCTURA DE PRODUCTOS WOOCOMMERCE]")
    print("=" * 80)

    url = f"{STORE_URL}/wp-json/wc/v3/products"
    params = {
        "per_page": 1,
        "orderby": "date",
        "order": "desc"
    }

    response = requests.get(
        url,
        params=params,
        auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=10
    )

    if response.status_code != 200:
        print(f"❌ Error: HTTP {response.status_code}")
        print(response.text)
        return

    products = response.json()
    if not products:
        print("❌ Sin productos disponibles")
        return

    product = products[0]

    print(f"\n✅ Producto obtenido: {product['name']} (ID: {product['id']})")
    print(f"\n📋 Estructura completa:")
    print(json.dumps(product, indent=2, ensure_ascii=False))

    # Analizar imágenes específicamente
    print("\n" + "=" * 80)
    print("📸 ANÁLISIS DE IMÁGENES")
    print("=" * 80)

    if 'images' in product and product['images']:
        images = product['images']
        print(f"\n✅ El producto tiene {len(images)} imagen(s)")

        for idx, img in enumerate(images, 1):
            print(f"\n  Imagen {idx}:")
            print(f"    - ID: {img.get('id')}")
            print(f"    - URL: {img.get('src')}")
            print(f"    - Alt: {img.get('alt', 'N/A')}")
            print(f"    - Nombre: {img.get('name', 'N/A')}")

            # Intentar acceder a la URL
            img_url = img.get('src')
            if img_url:
                print(f"\n    ✅ Verificando accesibilidad de la URL...")
                try:
                    img_response = requests.head(img_url, timeout=5)
                    print(f"       HTTP {img_response.status_code} ✅ URL ACCESIBLE")
                    print(f"       Content-Type: {img_response.headers.get('Content-Type', 'N/A')}")
                    print(f"       Content-Length: {img_response.headers.get('Content-Length', 'N/A')} bytes")
                except Exception as e:
                    print(f"       ❌ Error al acceder: {str(e)}")
    else:
        print("\n⚠️ El producto no tiene imágenes en su respuesta JSON")

    # Analizar atributos
    print("\n" + "=" * 80)
    print("🏷️  ANÁLISIS DE ATRIBUTOS")
    print("=" * 80)

    if 'attributes' in product and product['attributes']:
        attributes = product['attributes']
        print(f"\n✅ El producto tiene {len(attributes)} atributo(s):")

        for attr in attributes:
            print(f"\n  - {attr.get('name')}:")
            print(f"    Valor(es): {attr.get('options')}")
            print(f"    ID: {attr.get('id')}")
            print(f"    JSON completo: {json.dumps(attr, indent=6, ensure_ascii=False)}")
    else:
        print("\n⚠️ El producto no tiene atributos en su respuesta JSON")

    # Variantes
    print("\n" + "=" * 80)
    print("🔀 VARIANTES (Combinations de atributos)")
    print("=" * 80)

    if 'variations' in product and product['variations']:
        print(f"\n✅ El producto tiene {len(product['variations'])} variante(s)")
        print("   Nota: Use GET /wp-json/wc/v3/products/{id}/variations para detalles")
    else:
        print("\n⚠️ No hay variantes en la respuesta (puede requerir GET separado)")

    # Categorías
    print("\n" + "=" * 80)
    print("📁 CATEGORÍAS")
    print("=" * 80)

    if 'categories' in product:
        categories = product['categories']
        print(f"\n✅ El producto está en {len(categories)} categoría(s):")

        for cat in categories:
            print(f"  - {cat.get('name')} (ID: {cat.get('id')})")
    else:
        print("\n⚠️ Sin información de categorías")

    return product

def test_product_attributes_endpoint():
    """Obtener definiciones de atributos disponibles."""
    print("\n" + "=" * 80)
    print("🏷️  DEFINICIONES DE ATRIBUTOS GLOBALES")
    print("=" * 80)

    url = f"{STORE_URL}/wp-json/wc/v3/products/attributes"

    response = requests.get(
        url,
        auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=10
    )

    if response.status_code != 200:
        print(f"❌ Error: HTTP {response.status_code}")
        return

    attributes = response.json()
    print(f"\n✅ Atributos disponibles: {len(attributes)}")

    for attr in attributes[:5]:  # Mostrar primeros 5
        print(f"\n  {attr['name']}:")
        print(f"    ID: {attr['id']}")
        print(f"    Slug: {attr['slug']}")
        print(f"    Tipo: {attr.get('type', 'N/A')}")
        print(f"    Visible: {attr.get('visible', 'N/A')}")
        print(f"    Localizable: {attr.get('has_archives', 'N/A')}")

def test_product_variations():
    """Obtener estructura de variantes."""
    print("\n" + "=" * 80)
    print("🔀 VARIANTES DE PRODUCTOS")
    print("=" * 80)

    # Obtener primer producto con variantes
    url = f"{STORE_URL}/wp-json/wc/v3/products"
    params = {"per_page": 10}

    response = requests.get(
        url,
        params=params,
        auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=10
    )

    products = response.json()
    product_with_variations = None

    for p in products:
        if p.get('type') == 'variable' or len(p.get('variations', [])) > 0:
            product_with_variations = p
            break

    if not product_with_variations:
        print("⚠️ No se encontró producto con variantes en los primeros 10")
        return

    print(f"\n✅ Producto con variantes encontrado: {product_with_variations['name']}")
    print(f"   ID: {product_with_variations['id']}")
    print(f"   Tipo: {product_with_variations.get('type')}")

    # Obtener detalles de variantes
    product_id = product_with_variations['id']
    url_variations = f"{STORE_URL}/wp-json/wc/v3/products/{product_id}/variations"

    response_var = requests.get(
        url_variations,
        params={"per_page": 1},
        auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=10
    )

    if response_var.status_code == 200:
        variations = response_var.json()
        if variations:
            print(f"\n✅ Estructura de primera variante:")
            print(json.dumps(variations[0], indent=2, ensure_ascii=False))
    else:
        print(f"❌ Error obteniendo variantes: HTTP {response_var.status_code}")

def test_categories_structure():
    """Obtener estructura de categorías."""
    print("\n" + "=" * 80)
    print("📁 ESTRUCTURA DE CATEGORÍAS")
    print("=" * 80)

    url = f"{STORE_URL}/wp-json/wc/v3/products/categories"
    params = {"per_page": 3}

    response = requests.get(
        url,
        params=params,
        auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=10
    )

    if response.status_code != 200:
        print(f"❌ Error: HTTP {response.status_code}")
        return

    categories = response.json()
    print(f"\n✅ Categorías obtenidas: {len(categories)}")

    for cat in categories:
        print(f"\n  {cat['name']}:")
        print(f"    ID: {cat['id']}")
        print(f"    Slug: {cat['slug']}")
        print(f"    Descripción: {cat.get('description', 'N/A')[:80] if cat.get('description') else 'N/A'}")
        img = cat.get('image')
        print(f"    Imagen: {img.get('src', 'N/A') if img else 'N/A'}")
        print(f"    Padre: {cat.get('parent', 0)}")
        print(f"    Productos: {cat.get('count', 0)}")

if __name__ == "__main__":
    test_product_structure()
    test_product_attributes_endpoint()
    test_product_variations()
    test_categories_structure()

    print("\n" + "=" * 80)
    print("✅ ANÁLISIS COMPLETADO")
    print("=" * 80)
