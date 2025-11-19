"""
Modo interactivo del extractor spaCy.
Ejecuta queries en bucle hasta que escribas 'exit'.

Uso:
  python tools/test_extractor_interactive.py
"""
import sys
import os

# Asegurar import del backend
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'clip_admin_backend')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.blueprints.search_text import _extract_key_terms_with_dependency_parsing


def main():
    """
    Bucle interactivo para probar queries.
    """
    print("="*80)
    print("🔍 EXTRACTOR INTERACTIVO")
    print("="*80)
    print("Escribe una query para extraer términos.")
    print("Escribe 'exit' o 'quit' para salir.\n")

    while True:
        try:
            query = input("Query >>> ").strip()

            if not query:
                continue

            if query.lower() in ['exit', 'quit', 'salir', 'q']:
                print("\n👋 Saliendo...")
                break

            print(f"\n🔄 Procesando: '{query}'")
            print("-" * 80)

            # Ejecutar extractor
            result = _extract_key_terms_with_dependency_parsing(query)

            print("-" * 80)
            print(f"📊 Resultado: '{result}'")

            if result and result.strip():
                print("✅ Éxito\n")
            else:
                print("❌ No se extrajeron términos\n")

        except KeyboardInterrupt:
            print("\n\n👋 Interrumpido por usuario. Saliendo...")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    main()
