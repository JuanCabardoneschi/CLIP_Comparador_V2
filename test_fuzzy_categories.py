"""
Test de detección inteligente de categorías con fuzzy matching
Valida casos edge: diminutivos, sinónimos, fuera de catálogo
"""
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:5000"

# Obtener API key de Goody Store
def get_goody_api_key():
    try:
        resp = requests.get(f"{BASE_URL}/api/clients/list", timeout=5)
        resp.raise_for_status()
        data = resp.json()

        for client in data.get('clients', []):
            if 'Goody' in client.get('name', ''):
                return client.get('api_key')

        # Fallback: usar el primero
        if data.get('clients'):
            return data['clients'][0]['api_key']

        print("❌ No se encontraron clientes")
        return None
    except Exception as e:
        print(f"❌ Error obteniendo API key: {e}")
        return None

def test_text_search(query, api_key):
    """Ejecuta búsqueda textual y muestra resultado"""
    print(f"\n{'='*80}")
    print(f"🔍 Query: '{query}'")
    print(f"{'='*80}")

    try:
        headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }

        payload = {
            'query': query,
            'limit': 3
        }

        resp = requests.post(
            f"{BASE_URL}/api/search/text",
            headers=headers,
            json=payload,
            timeout=30
        )

        print(f"Status: {resp.status_code}")
        data = resp.json()

        if resp.status_code == 200:
            print(f"✅ SUCCESS")
            print(f"   Categoría detectada: {data.get('detected_category', {}).get('name', 'N/A')}")
            print(f"   Resultados: {len(data.get('results', []))}")
            print(f"   Match quality: {data.get('match_quality', 'N/A')}")

            if data.get('results'):
                print(f"\n   Top 3 productos:")
                for idx, prod in enumerate(data['results'][:3], 1):
                    print(f"      {idx}. {prod['name']} (score: {prod['final_score']:.3f})")

        elif resp.status_code == 404:
            print(f"⚠️  NOT FOUND (esperado)")
            print(f"   Error: {data.get('error')}")
            print(f"   Message: {data.get('message')}")

            if 'similar_categories' in data:
                print(f"\n   📋 Categorías similares sugeridas:")
                for cat in data['similar_categories']:
                    print(f"      - {cat['category_name']} (sim: {cat['similarity']:.3f}, productos: {cat['product_count']})")

            if 'available_categories' in data:
                cats = data['available_categories']
                print(f"\n   📚 Categorías disponibles: {', '.join(cats[:5])}")
                if len(cats) > 5:
                    print(f"      ... y {len(cats) - 5} más")
        else:
            print(f"❌ ERROR {resp.status_code}")
            print(f"   {json.dumps(data, indent=2, ensure_ascii=False)}")

    except requests.exceptions.Timeout:
        print("❌ TIMEOUT (>30s)")
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

def main():
    print("🧪 Test de Fuzzy Matching de Categorías")
    print("=" * 80)

    api_key = get_goody_api_key()
    if not api_key:
        print("❌ No se pudo obtener API key")
        sys.exit(1)

    print(f"✅ API Key obtenida: {api_key[:20]}...")

    # TEST 1: Diminutivo (delantalito → Delantal Completo)
    test_text_search("delantalito negro", api_key)

    # TEST 2: Sinónimo/variante (short → ¿alguna categoría similar?)
    test_text_search("short deportivo", api_key)

    # TEST 3: Sinónimo (pantalón corto → ¿alguna categoría similar?)
    test_text_search("pantalon corto azul", api_key)

    # TEST 4: Totalmente fuera de catálogo (auto → no match)
    test_text_search("auto verde", api_key)

    # TEST 5: Categoría real con productos (camisa)
    test_text_search("camisa blanca", api_key)

    # TEST 6: Variación ortográfica (delantales → delantal)
    test_text_search("delantales con bolsillos", api_key)

    print(f"\n{'='*80}")
    print("✅ Tests completados")
    print("=" * 80)

if __name__ == "__main__":
    main()
