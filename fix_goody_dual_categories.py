#!/usr/bin/env python3
"""
Script para encontrar productos con Goody + otra categoría en WooCommerce
y reasignarlos solo a la categoría que no es Goody.

Usa parámetros en URL en lugar de HTTP Basic Auth.
Los webhooks se disparan automáticamente.
"""

import requests
import warnings

# Suprimir SSL warnings
warnings.filterwarnings('ignore')

STORE_URL = "https://goodyshop.com.ar"
CONSUMER_KEY = "ck_f33c84759c035cf972347f7d8811e4afc6411d31"
CONSUMER_SECRET = "cs_622b4487002880cb739a900c8f77c6ae310b9a3b"
GOODY_CATEGORY_ID = 86

api_base = f"{STORE_URL}/wp-json/wc/v3"

def get_request(endpoint, params=None):
    """GET con credenciales en URL"""
    if params is None:
        params = {}
    params["consumer_key"] = CONSUMER_KEY
    params["consumer_secret"] = CONSUMER_SECRET

    url = f"{api_base}{endpoint}"
    response = requests.get(url, params=params, verify=False)
    response.raise_for_status()
    return response.json()

def put_request(endpoint, data):
    """PUT con credenciales en URL"""
    url = f"{api_base}{endpoint}"
    params = {
        "consumer_key": CONSUMER_KEY,
        "consumer_secret": CONSUMER_SECRET
    }
    response = requests.put(url, json=data, params=params, verify=False)
    response.raise_for_status()
    return response.json()

def get_all_products():
    """Obtiene todos los productos (paginado)"""
    all_products = []
    page = 1
    while True:
        products = get_request("/products", {"per_page": 100, "page": page})
        if not products:
            break
        all_products.extend(products)
        page += 1
        print(f"Cargados {len(all_products)} productos...")
    return all_products

def find_goody_dual_category_products():
    """Encuentra productos con Goody + otra categoría"""
    print("Obteniendo productos...")
    products = get_all_products()
    print(f"Total: {len(products)} productos\n")

    dual_products = []
    for product in products:
        categories = product.get("categories", [])
        has_goody = any(cat["id"] == GOODY_CATEGORY_ID for cat in categories)
        has_other = any(cat["id"] != GOODY_CATEGORY_ID for cat in categories)

        if has_goody and has_other:
            dual_products.append({
                "id": product["id"],
                "name": product["name"],
                "categories": categories
            })

    return dual_products

def main():
    print("=" * 80)
    print("FIX GOODY DUAL CATEGORIES")
    print("=" * 80)
    print()

    try:
        dual_products = find_goody_dual_category_products()
    except Exception as e:
        print(f"Error obteniendo productos: {str(e)}")
        return

    if not dual_products:
        print("No hay productos con Goody + otra categoria")
        return

    print(f"Encontrados {len(dual_products)} productos:\n")
    for idx, product in enumerate(dual_products, 1):
        cat_names = ", ".join(f"{cat['name']} (ID: {cat['id']})" for cat in product["categories"])
        print(f"  [{idx}] {product['name'][:50]:50s} | {cat_names}")

    print()
    response = input("Deseas reasignar estos productos (remover Goody)? (s/n): ").lower().strip()

    if response != 's':
        print("Cancelado.")
        return

    print("\nReasignando productos...\n")

    updated = 0
    for product in dual_products:
        product_id = product["id"]
        old_categories = product["categories"]
        new_categories = [cat for cat in old_categories if cat["id"] != GOODY_CATEGORY_ID]

        try:
            put_request(f"/products/{product_id}", {"categories": new_categories})
            updated += 1
            old_str = ", ".join(c["name"] for c in old_categories)
            new_str = ", ".join(c["name"] for c in new_categories)
            print(f"  OK: {product['name'][:50]:50s}")
            print(f"      {old_str} -> {new_str}")
        except Exception as e:
            print(f"  ERROR: {product['name'][:50]:50s}: {str(e)}")

    print("\n" + "=" * 80)
    print(f"COMPLETADO: {updated}/{len(dual_products)} productos reasignados")
    print("Los webhooks se dispararon automaticamente")
    print("=" * 80)

if __name__ == "__main__":
    main()
