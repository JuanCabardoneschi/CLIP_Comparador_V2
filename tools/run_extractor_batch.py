"""
Ejecutor batch del extractor spaCy con 30 queries variadas.
Muestra diagnóstico detallado: Éxito, Respuesta, Motivo.

Uso:
  python tools/run_extractor_batch.py
"""
import sys
import os
from datetime import datetime

# Asegurar import del backend
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'clip_admin_backend')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.blueprints.search_text import _get_nlp_es


def diagnose_extraction(query: str) -> dict:
    """
    Diagnostica por qué una query falla o tiene éxito en la extracción.

    🆕 Incluye AttributeRuler con lista hardcoded de categorías de moda.

    Returns:
        dict con keys: success (bool), extracted (str), reason (str), details (dict)
    """
    nlp = _get_nlp_es()
    if nlp is None:
        return {
            'success': False,
            'extracted': '',
            'reason': 'spaCy no disponible',
            'details': {}
        }

    # 🆕 Agregar AttributeRuler si no existe (solo primera vez)
    if "attribute_ruler_fashion" not in nlp.pipe_names:
        ruler = nlp.add_pipe("attribute_ruler", name="attribute_ruler_fashion", before="parser")

        # Lista hardcoded de categorías de moda (forzar POS=NOUN)
        FASHION_CATEGORIES = [
            # Prendas superiores
            'remera', 'remeras', 'camiseta', 'camisetas',
            'camisa', 'camisas', 'blusa', 'blusas',
            'buzo', 'buzos', 'sweater', 'sweaters',
            'campera', 'camperas', 'chaqueta', 'chaquetas',
            'saco', 'sacos', 'blazer', 'blazers',
            'chaleco', 'chalecos',
            'top', 'tops',

            # Prendas inferiores
            'pantalón', 'pantalones', 'jean', 'jeans',
            'short', 'shorts',
            'pollera', 'polleras', 'falda', 'faldas',
            'calza', 'calzas', 'leggins', 'leggings',
            'jogger', 'joggers',

            # Vestidos y enteritos
            'vestido', 'vestidos',
            'enterito', 'enteritos', 'overall', 'overalls',
            'mono', 'monos', 'jumpsuit', 'jumpsuits',

            # Accesorios
            'gorra', 'gorras', 'gorro', 'gorros',
            'bufanda', 'bufandas',
            'guante', 'guantes',
            'medias', 'soquete', 'soquetes',
            'cinturón', 'cinturones',

            # Trabajo/uniformes
            'delantal', 'delantales',
            'ambo', 'ambos',
            'uniforme', 'uniformes',

            # Calzado
            'zapatilla', 'zapatillas',
            'zapato', 'zapatos',
            'sandalia', 'sandalias',
            'bota', 'botas',
        ]

        patterns = [{"patterns": [[{"LOWER": term}]], "attrs": {"POS": "NOUN"}}
                    for term in FASHION_CATEGORIES]
        ruler.add_patterns(patterns)
        print(f"🔧 [TEST] AttributeRuler agregado con {len(FASHION_CATEGORIES)} términos de moda")

    doc = nlp(query)
    FASHION_TERMS = {'short', 'shorts', 'top', 'crop', 'leggins', 'jeggings', 'blazer'}

    # Analizar estructura
    tokens_info = []
    principal_candidates = []
    all_nouns = []
    all_adjs = []
    unknown_tokens = []
    dependency_tree = []  # 🆕 Para debug de árbol

    for token in doc:
        info = {
            'text': token.text,
            'lemma': token.lemma_,
            'pos': token.pos_,
            'dep': token.dep_,
            'is_alpha': token.is_alpha,
            'is_stop': token.is_stop
        }
        tokens_info.append(info)

        # 🆕 Construir árbol de dependencias
        dependency_tree.append({
            'text': token.text,
            'pos': token.pos_,
            'dep': token.dep_,
            'head': token.head.text,
            'children': [c.text for c in token.children]
        })

        # Detectar sustantivos
        if token.pos_ in ('NOUN', 'PROPN') and token.is_alpha and not token.is_stop:
            all_nouns.append(token.text)

        # Detectar adjetivos
        if token.pos_ == 'ADJ' and token.is_alpha and not token.is_stop:
            all_adjs.append(token.text)

        # Detectar candidatos a principal
        if token.dep_ in ('ROOT', 'obj', 'nsubj') and token.is_alpha and not token.is_stop:
            if token.pos_ in ('NOUN', 'PROPN') or token.text.lower() in FASHION_TERMS:
                principal_candidates.append({
                    'text': token.text,
                    'lemma': token.lemma_,
                    'pos': token.pos_,
                    'dep': token.dep_
                })

        # Detectar tokens desconocidos (ni NOUN, ni ADJ, ni VERB, ni stop)
        if token.is_alpha and not token.is_stop and token.pos_ not in ('NOUN', 'PROPN', 'ADJ', 'VERB', 'ADP', 'DET', 'PRON', 'AUX'):
            unknown_tokens.append({
                'text': token.text,
                'pos': token.pos_,
                'dep': token.dep_
            })

    # Intentar extracción (replicando lógica del extractor)
    elementos_extraidos = set()
    principal = None
    capture_details = []  # 🆕 Detalles de qué se capturó y por qué

    for token in doc:
        if not token.is_alpha or token.is_stop or token.pos_ == 'VERB':
            continue
        if token.dep_ in ('ROOT', 'obj', 'nsubj'):
            if token.pos_ in ('NOUN', 'PROPN') or token.text.lower() in FASHION_TERMS:
                term = token.text.lower() if token.text.lower() in FASHION_TERMS else token.lemma_.lower()
                if term and len(term) >= 3:
                    principal = token
                    elementos_extraidos.add(term)
                    capture_details.append(f"PRINCIPAL: '{term}' (head={token.head.text}, dep={token.dep_})")
                    break

    # Si hay principal, buscar modificadores nivel 1
    nivel2_discarded = set()  # 🆕 Términos descartados por ser nivel 2

    if principal:
        for child in principal.children:
            if not child.is_alpha or child.is_stop or child.pos_ == 'VERB':
                continue

            if child.dep_ == 'amod' and child.pos_ == 'ADJ':
                term = child.lemma_.lower()
                if term and len(term) >= 3:
                    elementos_extraidos.add(term)
                    capture_details.append(f"NIVEL1-ADJ: '{term}' (amod de '{principal.text}')")

            elif child.dep_ in ('nmod', 'pobj', 'compound') and child.pos_ in ('NOUN', 'PROPN'):
                term = child.text.lower() if child.text.lower() in FASHION_TERMS else child.lemma_.lower()
                if term and len(term) >= 3:
                    elementos_extraidos.add(term)
                    capture_details.append(f"NIVEL1-NOUN: '{term}' (dep={child.dep_} de '{principal.text}')")

                    # 🆕 Detectar y reportar hijos (nivel 2) - NO capturar
                    nivel2_children = [c for c in child.children if c.is_alpha and not c.is_stop]
                    for gc in nivel2_children:
                        nivel2_term = gc.text.lower() if gc.text.lower() in FASHION_TERMS else gc.lemma_.lower()
                        nivel2_discarded.add(nivel2_term)  # 🆕 Marcar como descartado
                        capture_details.append(f"  ⛔ NIVEL2 descartado: '{gc.text}' (dep={gc.dep_} de '{child.text}')")

            elif child.dep_ == 'prep':
                for prep_child in child.children:
                    if not prep_child.is_alpha or prep_child.is_stop or prep_child.pos_ == 'VERB':
                        continue
                    if prep_child.dep_ == 'pobj' and prep_child.pos_ in ('NOUN', 'PROPN'):
                        term = prep_child.text.lower() if prep_child.text.lower() in FASHION_TERMS else prep_child.lemma_.lower()
                        if term and len(term) >= 3:
                            elementos_extraidos.add(term)
                            capture_details.append(f"NIVEL1-NOUN: '{term}' (pobj via prep '{child.text}' de '{principal.text}')")

                            # 🆕 Detectar y reportar hijos (nivel 2) - NO capturar
                            nivel2_children = [c for c in prep_child.children if c.is_alpha and not c.is_stop]
                            for gc in nivel2_children:
                                nivel2_term = gc.text.lower() if gc.text.lower() in FASHION_TERMS else gc.lemma_.lower()
                                nivel2_discarded.add(nivel2_term)  # 🆕 Marcar como descartado
                                capture_details.append(f"  ⛔ NIVEL2 descartado: '{gc.text}' (dep={gc.dep_} de '{prep_child.text}')")

        # Fallback para términos mal etiquetados
        processed_lemmas = {e.lower() for e in elementos_extraidos}
        processed_lemmas.update(nivel2_discarded)  # 🆕 Excluir términos nivel 2 del fallback
        fallback_added = []
        for token in doc:
            if not token.is_alpha or token.is_stop or token.pos_ == 'VERB':
                continue
            if token.pos_ not in ('NOUN', 'PROPN') and token.text.lower() not in FASHION_TERMS:
                continue
            term = token.text.lower() if token.text.lower() in FASHION_TERMS else token.lemma_.lower()
            if term and len(term) >= 3 and term not in processed_lemmas:
                elementos_extraidos.add(term)
                fallback_added.append(term)

        if fallback_added:
            capture_details.append(f"FALLBACK: {fallback_added}")    # Construir resultado
    extracted_str = " ".join(sorted(list(elementos_extraidos)))
    success = len(elementos_extraidos) > 0

    # Generar motivo detallado
    if not success:
        if not principal_candidates:
            # No hay sustantivo principal
            if all_nouns:
                reason = f"Falta categoría (sustantivo principal). Hay sustantivos pero no en posición ROOT/obj/nsubj: {', '.join(all_nouns)}"
            else:
                reason = "Falta categoría (no se detectó ningún sustantivo en la query)"
        else:
            # Hay candidato pero no se eligió (por longitud o filtros)
            reason = f"Sustantivo principal detectado pero filtrado: {principal_candidates[0]['text']} (len<3 o stop word)"
    else:
        # Éxito - describir qué se capturó
        parts = []
        if principal:
            parts.append(f"categoría '{principal.lemma_.lower()}'")
        if len(elementos_extraidos) > 1:
            modifiers = [e for e in elementos_extraidos if principal and e != principal.lemma_.lower()]
            if modifiers:
                parts.append(f"{len(modifiers)} modificador(es): {', '.join(modifiers)}")
        reason = "Extracción exitosa: " + "; ".join(parts)

    return {
        'success': success,
        'extracted': extracted_str,
        'reason': reason,
        'details': {
            'tokens': tokens_info,
            'principal_candidates': principal_candidates,
            'all_nouns': all_nouns,
            'all_adjs': all_adjs,
            'unknown_tokens': unknown_tokens,
            'dependency_tree': dependency_tree,  # 🆕
            'capture_details': capture_details  # 🆕
        }
    }


QUERIES = [
    # Éxito directo
    "delantal verde",
    "short rojo",
    "remera negra",
    "gorra blanca",
    "pantalón azul",
    "campera beige",
    "vestido fucsia",
    "buzo gris",
    # Anglicismos / sinónimos
    "top negro",
    "short denim azul",
    "leggins verdes",
    "jogger bordo",
    "blazer gris",
    # Borde: modificadores nivel 2
    "delantal con cierre al costado",
    "delantal con bolsillos grandes",
    "short con cierre largo",
    "remera con bolsillos al frente",
    "gorra con logo lateral",
    "pantalón con botón trasero",
    "camisa con cuello mao angosto",
    # Typos
    "short grices",
    "delantal cieerre negro",
    "remera berrde",
    "gorra celestee",
    "campera amariyo",
    # Errores (sin categoría)
    "con cierre al costado",
    "quiero uno rojo",
    "mostrame con bolsillos",
    "al frente lateral",
    # Borde semántico adicional
    "delantal goody negro",
]


def run():
    print("\n" + "#"*80)
    print("DIAGNÓSTICO DETALLADO DEL EXTRACTOR (30 queries)")
    print("#"*80 + "\n")

    success_count = 0
    fail_count = 0
    results = []

    for i, q in enumerate(QUERIES, 1):
        print("-"*80)
        print(f"{i:02d}. Query: '{q}'")
        print("-"*80)

        diag = diagnose_extraction(q)

        # Formato solicitado
        exito = "SÍ" if diag['success'] else "NO"
        respuesta = f"'{diag['extracted']}'" if diag['extracted'] else "(vacío)"
        motivo = diag['reason']

        print(f"  Éxito:     {exito}")
        print(f"  Respuesta: {respuesta}")
        print(f"  Motivo:    {motivo}")

        # 🆕 Mostrar detalles de captura para debug
        if diag['details']['capture_details']:
            print(f"\n  📊 Captura detallada:")
            for detail in diag['details']['capture_details']:
                print(f"     {detail}")

        # 🆕 Mostrar árbol de dependencias para casos problemáticos
        if diag['success'] and len(diag['extracted'].split()) > 2:
            print(f"\n  🌳 Árbol sintáctico:")
            for node in diag['details']['dependency_tree']:
                if node['text'] not in ['con', 'al', 'de', 'en']:  # Skip preposiciones
                    print(f"     {node['text']} (POS={node['pos']}, DEP={node['dep']}, head={node['head']})")

        # Información adicional de estructura si hay tokens desconocidos o casos especiales
        details = diag['details']
        if details['unknown_tokens']:
            print(f"  ⚠️  Tokens desconocidos: {[t['text'] + '(' + t['pos'] + ')' for t in details['unknown_tokens']]}")

        if not diag['success'] and details['all_nouns']:
            print(f"  ℹ️  Sustantivos detectados (no principales): {details['all_nouns']}")

        if not diag['success'] and details['all_adjs']:
            print(f"  ℹ️  Adjetivos detectados: {details['all_adjs']}")

        print()

        if diag['success']:
            success_count += 1
        else:
            fail_count += 1

        results.append((q, diag))

    print("\n" + "="*80)
    print("RESUMEN")
    print("="*80)
    print(f"Total queries:  {len(QUERIES)}")
    print(f"Éxito (SÍ):     {success_count}")
    print(f"Fallo (NO):     {fail_count}")
    print(f"Tasa de éxito:  {success_count/len(QUERIES)*100:.1f}%")
    print("="*80 + "\n")

    return results


if __name__ == "__main__":
    run()
