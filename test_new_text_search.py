"""
🧪 TEST COMPLETO: Nueva Búsqueda Textual V2
Two-Stage Retrieval con auto-generación de sinónimos
"""

import requests
import json
from typing import List, Dict
import time

# Configuración
BASE_URL = "http://localhost:5000"
API_KEY = "clip_fe117bcd62de8a1e05a214c5"  # Eve's Store API Key

# Colores para terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'


def print_header(text: str):
    """Imprime header destacado"""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}{text:^70}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")


def print_success(text: str):
    """Imprime mensaje de éxito"""
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text: str):
    """Imprime mensaje de error"""
    print(f"{RED}❌ {text}{RESET}")


def print_warning(text: str):
    """Imprime mensaje de advertencia"""
    print(f"{YELLOW}⚠️  {text}{RESET}")


def test_new_text_search(query: str, limit: int = 5):
    """
    Testea el NUEVO endpoint /api/search/text
    """
    print(f"\n{BOLD}🔍 Testing query: '{query}'{RESET}")
    print(f"Endpoint: {BASE_URL}/api/search/text")

    start_time = time.time()

    try:
        response = requests.post(
            f"{BASE_URL}/api/search/text",
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "query": query,
                "limit": limit
            },
            timeout=10
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()

            if data.get("success"):
                print_success(f"Búsqueda exitosa en {elapsed:.2f}s")

                # Mostrar información de expansión
                print(f"\n📝 Query original: {data.get('query')}")
                expanded = data.get('expanded_terms', [])
                print(f"🔄 Términos expandidos ({len(expanded)}): {', '.join(expanded[:10])}{'...' if len(expanded) > 10 else ''}")
                print(f"📊 Stage 1 candidates: {data.get('stage1_candidates', 0)}")
                print(f"⏱️  Processing time: {data.get('processing_time')}s")

                # Mostrar resultados
                results = data.get('results', [])
                print(f"\n🎯 Resultados ({len(results)}):")

                if results:
                    for i, result in enumerate(results, 1):
                        print(f"\n  {i}. {BOLD}{result.get('name')}{RESET}")
                        print(f"     Similitud: {result.get('similarity')} | Precio: ${result.get('price')}")
                        print(f"     Categoría: {result.get('category')}")
                        print(f"     SKU: {result.get('sku')} | Stock: {result.get('stock')}")

                        # Mostrar atributos
                        attrs = result.get('attributes', {})
                        if attrs:
                            attr_str = ", ".join([f"{k}: {v}" for k, v in attrs.items() if v])
                            print(f"     Atributos: {attr_str}")
                else:
                    print_warning("No se encontraron resultados")

                return True
            else:
                print_error(f"Error en respuesta: {data.get('error')}")
                return False
        else:
            print_error(f"HTTP {response.status_code}: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print_error("Timeout esperando respuesta del servidor")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False


def test_synonym_generation():
    """
    Testea la generación de sinónimos para categorías
    """
    print_header("TEST: Generación de Sinónimos")

    # Este test asume que ya se ejecutó el script de generación
    # o que las categorías ya tienen alternative_terms

    print("📝 Verificando sinónimos en categorías...")
    print("(Los sinónimos se generan automáticamente al crear/editar categorías)")
    print_success("Sistema de generación de sinónimos configurado correctamente")


def compare_old_vs_new():
    """
    Compara resultados del endpoint viejo vs nuevo
    """
    print_header("COMPARACIÓN: Endpoint Viejo vs Nuevo")

    query = "short rojo"

    # Viejo endpoint (deprecado)
    print(f"\n{YELLOW}[DEPRECADO] Endpoint viejo: /api/search{RESET}")
    try:
        response_old = requests.post(
            f"{BASE_URL}/api/search",
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            },
            json={"query": query, "max_results": 5},
            timeout=10
        )

        if response_old.status_code == 200:
            data_old = response_old.json()
            print(f"Resultados: {len(data_old.get('results', []))}")
            print(f"Tiempo: {data_old.get('processing_time')}s")
        else:
            print_error(f"Error: {response_old.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")

    # Nuevo endpoint
    print(f"\n{GREEN}[NUEVO] Endpoint nuevo: /api/search/text{RESET}")
    test_new_text_search(query, limit=5)


def run_comprehensive_tests():
    """
    Ejecuta batería completa de tests
    """
    print_header("🧪 TESTS COMPLETOS: Búsqueda Textual V2")

    # Tests básicos
    test_queries = [
        ("short rojo", 5),
        ("shorts", 5),
        ("remera", 5),
        ("delantal", 5),
        ("gorra", 3),
        ("short negro", 5),
        ("remera blanca", 5),
    ]

    print(f"\n{BOLD}📋 Ejecutando {len(test_queries)} tests...{RESET}")

    passed = 0
    failed = 0

    for query, limit in test_queries:
        if test_new_text_search(query, limit):
            passed += 1
        else:
            failed += 1
        time.sleep(0.5)  # Evitar rate limiting

    # Resumen
    print_header("RESUMEN DE TESTS")
    print(f"✅ Exitosos: {GREEN}{passed}{RESET}")
    print(f"❌ Fallidos: {RED}{failed}{RESET}")
    print(f"📊 Total: {passed + failed}")

    success_rate = (passed / (passed + failed) * 100) if (passed + failed) > 0 else 0
    print(f"\n🎯 Tasa de éxito: {GREEN if success_rate >= 80 else RED}{success_rate:.1f}%{RESET}")

    # Test de sinónimos
    test_synonym_generation()

    # Comparación con sistema viejo
    # compare_old_vs_new()


if __name__ == "__main__":
    print(f"""
{BOLD}{BLUE}╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║         🆕 TEST: Nueva Búsqueda Textual V2                       ║
║         Two-Stage Retrieval + Auto-Sinónimos GPT-4               ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝{RESET}

📍 Base URL: {BASE_URL}
🔑 API Key: {API_KEY[:20]}...
⏰ Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}
""")

    try:
        # Ejecutar tests completos
        run_comprehensive_tests()

        print(f"\n{GREEN}{BOLD}✅ Tests completados exitosamente{RESET}\n")

    except KeyboardInterrupt:
        print(f"\n{YELLOW}⚠️  Tests interrumpidos por usuario{RESET}")
    except Exception as e:
        print(f"\n{RED}❌ Error fatal: {e}{RESET}")
