"""
Prueba rápida del extractor spaCy con UNA query específica.
Muestra diagnóstico detallado.

Uso:
  python tools/test_extractor_single.py "delantal con cierre al costado"
  python tools/test_extractor_single.py "remera negra"
"""
import sys
import os

# Asegurar import del backend
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'clip_admin_backend')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.blueprints.search_text import _extract_key_terms_with_dependency_parsing


def test_single_query(query: str):
    """
    Ejecuta el extractor para una query y muestra el resultado.
    """
    print("="*80)
    print(f"🔍 Testing Extractor con query: '{query}'")
    print("="*80 + "\n")

    # Ejecutar extractor (mismo que usa el endpoint)
    result = _extract_key_terms_with_dependency_parsing(query)

    print("\n" + "="*80)
    print("📊 RESULTADO FINAL")
    print("="*80)
    print(f"Query original: '{query}'")

    if isinstance(result, dict):
        print(f"Términos extraídos: '{result.get('text', '')}'")
        print(f"📦 Categoría: '{result.get('category')}'")
        print(f"🏷️  Modificadores: {result.get('modifiers', [])}")
        if result.get('success'):
            print("✅ Éxito: Extracción completada")
        else:
            print("❌ Fallo: No se pudo extraer categoría")
    else:
        # Backward compatibility (por si acaso)
        print(f"Términos extraídos: '{result}'")
        if result and result.strip():
            print("✅ Éxito: Extracción completada")
        else:
            print("❌ Fallo: No se extrajeron términos")

    print("="*80 + "\n")

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Error: Falta el argumento de query")
        print("\nUso:")
        print('  python tools/test_extractor_single.py "tu query aquí"')
        print("\nEjemplos:")
        print('  python tools/test_extractor_single.py "delantal con cierre"')
        print('  python tools/test_extractor_single.py "remera negra"')
        print('  python tools/test_extractor_single.py "gorra con logo lateral"')
        sys.exit(1)

    query_text = " ".join(sys.argv[1:])
    test_single_query(query_text)
