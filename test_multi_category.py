"""
Script de prueba para detección multi-categoría

Uso:
    python test_multi_category.py <ruta_imagen>

Ejemplo:
    python test_multi_category.py test_outfit.jpg
"""

import requests
import sys
import json

# Configuración
API_URL = "http://localhost:5000/api/search"
API_KEY = "clip_57fc482f-2776-4816-b231-57d3c57348de"  # Eve's Store

def test_single_category(image_path):
    """Test búsqueda con detección de categoría única (modo actual)"""
    print("\n" + "="*60)
    print("TEST 1: SINGLE CATEGORY MODE (actual)")
    print("="*60)

    with open(image_path, 'rb') as img:
        files = {'image': img}
        headers = {'X-API-Key': API_KEY}
        data = {
            'limit': 3,
            'multi_category': 'false'  # Modo single
        }

        response = requests.post(API_URL, files=files, headers=headers, data=data)

    print(f"\nStatus: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ Modo: {result.get('mode', 'N/A')}")
        print(f"Categoría detectada: {result['detected_category']['name']}")
        print(f"Confianza: {result['detected_category']['confidence']:.3f}")
        print(f"Productos encontrados: {result['total_results']}")

        for idx, prod in enumerate(result['results'][:3], 1):
            print(f"  {idx}. {prod['name']} - Score: {prod['similarity']:.4f}")
    else:
        print(f"\n❌ Error: {response.text}")

    return response

def test_multi_category(image_path):
    """Test búsqueda con detección de múltiples categorías (nuevo)"""
    print("\n" + "="*60)
    print("TEST 2: MULTI-CATEGORY MODE (nuevo)")
    print("="*60)

    with open(image_path, 'rb') as img:
        files = {'image': img}
        headers = {'X-API-Key': API_KEY}
        data = {
            'limit': 3,
            'multi_category': 'true'  # Modo multi
        }

        response = requests.post(API_URL, files=files, headers=headers, data=data)

    print(f"\nStatus: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ Modo: {result.get('mode', 'N/A')}")
        print(f"Categorías detectadas: {result.get('detected_categories', 0)}")

        categories = result.get('categories', {})
        for cat_name, cat_data in categories.items():
            print(f"\n📁 Categoría: {cat_name}")
            print(f"   Confianza: {cat_data['confidence']:.3f}")
            print(f"   Productos: {cat_data['total_products']}")

            for idx, prod in enumerate(cat_data['products'][:3], 1):
                print(f"     {idx}. {prod['name']} - Score: {prod['similarity']:.4f}")
    else:
        print(f"\n❌ Error: {response.text}")

    return response

def main():
    if len(sys.argv) < 2:
        print("❌ Error: Debes proporcionar la ruta de una imagen")
        print(f"\nUso: python {sys.argv[0]} <ruta_imagen>")
        print(f"Ejemplo: python {sys.argv[0]} test_outfit.jpg")
        sys.exit(1)

    image_path = sys.argv[1]

    print(f"\n🖼️  Imagen de prueba: {image_path}")
    print(f"🔑 API Key: {API_KEY}")
    print(f"🌐 Endpoint: {API_URL}")

    # Test 1: Modo single
    test_single_category(image_path)

    # Test 2: Modo multi
    test_multi_category(image_path)

    print("\n" + "="*60)
    print("TESTS COMPLETADOS")
    print("="*60)

if __name__ == "__main__":
    main()
