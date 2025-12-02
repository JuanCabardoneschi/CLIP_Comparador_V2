"""
Script one-shot para migrar productos de Eve's Store a Tiendanube
USAR SOLO UNA VEZ - Migra categorías, productos e imágenes
"""

import os
import sys
import time
import json
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('.env.local')

# Configuración
STORE_ID = "7019043"  # Test Clip store
ACCESS_TOKEN = os.getenv('TIENDANUBE_ACCESS_TOKEN')  # Debe estar en .env.local

if not ACCESS_TOKEN:
    print("❌ Error: TIENDANUBE_ACCESS_TOKEN no está configurado en .env.local")
    sys.exit(1)

# Headers para API Tiendanube
HEADERS = {
    'Authentication': f'bearer {ACCESS_TOKEN}',
    'Content-Type': 'application/json',
    'User-Agent': 'CLIP Comparador V2 (esilvestre@redsis.com.ar)'
}

BASE_URL = f"https://api.tiendanube.com/v1/{STORE_ID}"

# Conexión a Railway PostgreSQL
RAILWAY_DB = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

def execute_query(query):
    """Ejecutar query y retornar resultados como lista de dicts"""
    try:
        conn = psycopg2.connect(**RAILWAY_DB)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query)
        results = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in results]
    except Exception as e:
        print(f"❌ Error ejecutando query: {e}")
        return []

def get_eve_client():
    """Obtener datos del cliente Eve"""
    query = "SELECT id, name, email, api_key FROM clients WHERE name = 'Eve''s Store'"
    result = execute_query(query)
    if result and len(result) > 0:
        return result[0]
    return None

def get_eve_categories(client_id):
    """Obtener categorías de Eve"""
    query = f"""
        SELECT id, name, slug, description
        FROM categories
        WHERE client_id = '{client_id}'
        ORDER BY name
    """
    return execute_query(query)

def get_eve_products(client_id):
    """Obtener productos de Eve con sus categorías e imágenes"""
    query = f"""
        SELECT
            p.id,
            p.name,
            p.sku,
            p.price,
            p.stock,
            p.attributes,
            p.description,
            cat.name as category_name,
            cat.slug as category_slug,
            COALESCE(
                json_agg(
                    json_build_object(
                        'url', i.cloudinary_url,
                        'is_primary', i.is_primary
                    ) ORDER BY i.is_primary DESC, i.display_order
                ) FILTER (WHERE i.id IS NOT NULL AND i.cloudinary_url IS NOT NULL AND LENGTH(i.cloudinary_url) > 60),
                '[]'
            ) as images
        FROM products p
        JOIN categories cat ON cat.id = p.category_id
        LEFT JOIN images i ON i.product_id = p.id
        WHERE p.client_id = '{client_id}' AND p.is_active = TRUE
        GROUP BY p.id, p.name, p.sku, p.price, p.stock, p.attributes, p.description, cat.name, cat.slug
        ORDER BY cat.name, p.name
    """
    return execute_query(query)

def get_eve_products_with_invalid_price(client_id):
    """Obtener productos con precio NULL para reintento"""
    query = f"""
        SELECT
            p.id,
            p.name,
            p.sku,
            p.price,
            p.stock,
            p.attributes,
            p.description,
            cat.name as category_name,
            cat.slug as category_slug,
            COALESCE(
                json_agg(
                    json_build_object(
                        'url', i.cloudinary_url,
                        'is_primary', i.is_primary
                    ) ORDER BY i.is_primary DESC, i.display_order
                ) FILTER (WHERE i.id IS NOT NULL AND i.cloudinary_url IS NOT NULL AND LENGTH(i.cloudinary_url) > 60),
                '[]'
            ) as images
        FROM products p
        JOIN categories cat ON cat.id = p.category_id
        LEFT JOIN images i ON i.product_id = p.id
        WHERE p.client_id = '{client_id}'
          AND p.is_active = TRUE
          AND p.price IS NULL
        GROUP BY p.id, p.name, p.sku, p.price, p.stock, p.attributes, p.description, cat.name, cat.slug
        ORDER BY cat.name, p.name
    """
    return execute_query(query)

def get_tiendanube_categories():
    """Obtener categorías existentes en Tiendanube"""
    try:
        response = requests.get(
            f"{BASE_URL}/categories",
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()
        categories = response.json()
        print(f"✅ {len(categories)} categorías encontradas en Tiendanube")
        return categories
    except requests.exceptions.RequestException as e:
        print(f"❌ Error obteniendo categorías de Tiendanube: {e}")
        return []

def create_tiendanube_category(name, description=None):
    """Crear categoría en Tiendanube"""
    data = {
        'name': {'es': name},
        'description': {'es': description or f'Categoría {name}'},
        'handle': {'es': name.lower().replace(' ', '-')},
        'parent': None,
        'subcategories': []
    }

    try:
        response = requests.post(
            f"{BASE_URL}/categories",
            headers=HEADERS,
            json=data,
            timeout=30
        )
        response.raise_for_status()
        category = response.json()
        print(f"  ✅ Categoría creada: {name} (ID: {category['id']})")
        return category
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error creando categoría {name}: {e}")
        if hasattr(e.response, 'text'):
            print(f"     Response: {e.response.text}")
        return None

def create_tiendanube_product(product, category_id):
    """Crear producto en Tiendanube"""
    # Parsear atributos JSON
    attributes = {}
    if product['attributes']:
        try:
            if isinstance(product['attributes'], str):
                attributes = json.loads(product['attributes'])
            else:
                attributes = product['attributes']
        except:
            pass

    # Preparar precio: si falta o es inválido, usar un precio por defecto
    def sanitize_price(raw):
        try:
            if raw is None:
                return "15000.00"
            # Convertir a string, normalizar comas/puntos
            s = str(raw).strip()
            # Si viene como entero/float válido
            val = float(s.replace(',', '.'))
            return f"{val:.2f}"
        except Exception:
            return "15000.00"

    price_value = sanitize_price(product.get('price'))

    # Preparar variantes (por ahora una sola variante base)
    variants = [{
        'price': price_value,
        'stock_management': True,
        'stock': product['stock'] or 0,
        'sku': product['sku'] or ''
    }]

    # Preparar descripción con atributos
    description_parts = []
    if product.get('description'):
        description_parts.append(product['description'])

    if attributes:
        description_parts.append("\n\n**Características:**")
        for key, value in attributes.items():
            description_parts.append(f"- {key.title()}: {value}")

    description = '\n'.join(description_parts) if description_parts else product['name']

    data = {
        'name': {'es': product['name']},
        'description': {'es': description},
        'handle': {'es': product['name'].lower().replace(' ', '-')},
        'categories': [category_id],
        'published': True,
        'free_shipping': False,
        'variants': variants
    }

    # Agregar imágenes si existen
    if product.get('images'):
        try:
            images_data = json.loads(product['images']) if isinstance(product['images'], str) else product['images']
            if images_data and len(images_data) > 0:
                data['images'] = [{'src': img['url']} for img in images_data if img.get('url')]
        except Exception as e:
            print(f"  ⚠️  Error procesando imágenes: {e}")

    try:
        response = requests.post(
            f"{BASE_URL}/products",
            headers=HEADERS,
            json=data,
            timeout=30
        )
        response.raise_for_status()
        product_data = response.json()
        print(f"  ✅ Producto creado: {product['name']} (ID: {product_data['id']})")
        return product_data
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error creando producto {product['name']}: {e}")
        if hasattr(e.response, 'text'):
            print(f"     Response: {e.response.text[:500]}")
        return None

def main():
    print("=" * 70)
    print("🚀 MIGRACIÓN EVE'S STORE → TIENDANUBE")
    print("=" * 70)
    print()

    # Confirmar antes de proceder
    print("⚠️  Este script va a:")
    print("   1. Usar las categorías YA CREADAS en Tiendanube")
    print("   2. Crear todos los productos con sus imágenes")
    print("   3. Esto NO se puede deshacer fácilmente")
    print()
    confirm = input("¿Continuar? (escribe 'SI' para confirmar): ")
    if confirm != 'SI':
        print("❌ Operación cancelada")
        return

    print("\n📊 Obteniendo datos de Eve's Store...")

    # Obtener cliente Eve
    eve_client = get_eve_client()
    if not eve_client:
        print("❌ Cliente Eve's Store no encontrado")
        return

    print(f"✅ Cliente encontrado: {eve_client['name']} (ID: {eve_client['id']})")

    # Obtener categorías de Tiendanube (ya creadas)
    tn_categories = get_tiendanube_categories()
    if not tn_categories:
        print("❌ No se encontraron categorías en Tiendanube")
        return

    # Mapear por nombre (case-insensitive)
    category_map = {}
    for tn_cat in tn_categories:
        cat_name = tn_cat['name']['es'].lower()
        category_map[cat_name] = tn_cat['id']

    print(f"✅ Mapeadas {len(category_map)} categorías de Tiendanube")

    # Obtener productos
    mode = input("¿Solo reintentar fallidos por precio? (SI/NO): ")
    if mode.strip().upper() == 'SI':
        products = get_eve_products_with_invalid_price(eve_client['id'])
        print(f"✅ {len(products)} productos con precio inválido encontrados")
    else:
        products = get_eve_products(eve_client['id'])
        print(f"✅ {len(products)} productos encontrados")

    if len(products) == 0:
        print("⚠️  No se encontraron productos. Verificando query...")
        print(f"   Client ID: {eve_client['id']}")
        return

    print("\n" + "=" * 70)
    print("📦 CREANDO PRODUCTOS")
    print("=" * 70)

    created_count = 0
    failed_count = 0

    for product in products:
        print(f"\n📦 Creando: {product['name']} (Categoría: {product['category_name']})")

        # Buscar categoría por nombre (case-insensitive)
        category_key = product['category_name'].lower()
        if category_key not in category_map:
            print(f"  ⚠️  Categoría '{product['category_name']}' no encontrada en Tiendanube, saltando...")
            failed_count += 1
            continue

        tn_category_id = category_map[category_key]

        # Crear producto
        tn_product = create_tiendanube_product(product, tn_category_id)
        if tn_product:
            created_count += 1
        else:
            failed_count += 1

        time.sleep(0.7)  # Rate limiting más conservador

    print("\n" + "=" * 70)
    print("✅ MIGRACIÓN COMPLETA")
    print("=" * 70)
    print(f"📊 Productos creados: {created_count}")
    print(f"❌ Productos fallidos: {failed_count}")
    print(f"🏷️  Categorías usadas: {len(category_map)}")
    print()
    print("🔗 Revisar en: https://test-clip-1.mitiendanube.com/admin/products")
    print()

if __name__ == '__main__':
    main()
