"""
Muestra el árbol de dependencias completo de spaCy para depurar extracciones.

Uso:
  python tools/debug_dependency_tree.py "tu query aquí"
"""
import sys
import os

# Asegurar import del backend
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'clip_admin_backend')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.blueprints.search_text import _get_nlp_es


def show_dependency_tree(query: str):
    """
    Muestra el árbol de dependencias completo de spaCy.
    """
    nlp = _get_nlp_es()
    if nlp is None:
        print("❌ spaCy no disponible")
        return

    doc = nlp(query)

    print("="*80)
    print(f"🌳 ÁRBOL DE DEPENDENCIAS: '{query}'")
    print("="*80 + "\n")

    # Tabla de tokens
    print(f"{'TOKEN':<15} {'POS':<8} {'DEP':<12} {'HEAD':<15} {'CHILDREN'}")
    print("-"*80)

    for token in doc:
        children = [child.text for child in token.children]
        children_str = ", ".join(children) if children else "-"
        print(f"{token.text:<15} {token.pos_:<8} {token.dep_:<12} {token.head.text:<15} {children_str}")

    print("\n" + "="*80)
    print("🔍 ANÁLISIS DE RELACIONES")
    print("="*80 + "\n")

    # Encontrar el sustantivo principal
    principal = None
    for token in doc:
        if token.pos_ in ('NOUN', 'PROPN'):
            if token.dep_ in ('ROOT', 'dobj', 'nsubj', 'obj', 'nmod', 'pobj'):
                principal = token
                break

    if principal:
        print(f"✅ PRINCIPAL: '{principal.text}' (POS={principal.pos_}, DEP={principal.dep_})\n")

        print("📊 HIJOS DIRECTOS (Nivel 1):")
        for child in principal.children:
            print(f"  → {child.text} (POS={child.pos_}, DEP={child.dep_})")

            # Mostrar nietos (Nivel 2)
            grandchildren = list(child.children)
            if grandchildren:
                print(f"     ↳ HIJOS DE '{child.text}' (Nivel 2):")
                for gc in grandchildren:
                    print(f"        → {gc.text} (POS={gc.pos_}, DEP={gc.dep_})")
    else:
        print("❌ No se detectó sustantivo principal\n")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Error: Falta el argumento de query")
        print("\nUso:")
        print('  python tools/debug_dependency_tree.py "tu query aquí"')
        sys.exit(1)

    query_text = " ".join(sys.argv[1:])
    show_dependency_tree(query_text)
