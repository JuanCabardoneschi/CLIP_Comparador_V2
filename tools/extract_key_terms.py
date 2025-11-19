import sys
from typing import Set

try:
    import spacy
    from spacy.cli import download as spacy_download
except Exception as e:
    print("[ERROR] spaCy no está instalado. Agrega 'spacy' a requirements.txt e instala dependencias.")
    raise

_nlp = None

def get_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp
    try:
        _nlp = spacy.load("es_core_news_sm")
    except OSError:
        # Intentar descargar el modelo automáticamente
        try:
            print("[INFO] Descargando modelo 'es_core_news_sm'...")
            spacy_download("es_core_news_sm")
            _nlp = spacy.load("es_core_news_sm")
        except Exception as e:
            print("[ERROR] No se pudo cargar/descargar el modelo 'es_core_news_sm'.")
            print("        Instálalo manualmente con: python -m spacy download es_core_news_sm")
            raise
    return _nlp


def extract_key_terms_with_dependency_parsing(text: str) -> str:
    """
    Extrae sustantivos, nombres propios y sus modificadores adjetivales directos
    de una frase, utilizando el análisis de dependencias de spaCy.
    Maneja casos específicos como 'de color verde' y filtra modificadores de modificadores.

    Args:
        text (str): La frase de entrada a analizar.

    Returns:
        str: Una cadena de texto con los términos clave únicos, ordenados y separados por espacio.
    """
    # 🆕 Lista blanca de términos de moda (anglicismos y términos especiales)
    # que spaCy español puede etiquetar mal pero son productos clave
    FASHION_TERMS_WHITELIST = {
        'top', 'tops', 'short', 'shorts', 'jean', 'jeans', 'jogger', 'joggers',
        'legging', 'leggings', 'bodysuit', 'crop', 'sweater', 'hoodie', 'cardigan'
    }

    nlp = get_nlp()
    doc = nlp(text.lower())  # Convertir a minúsculas
    elementos_extraidos: Set[str] = set()

    # Keep track of tokens that have been explicitly added or skipped
    processed_tokens = set()

    for token in doc:
        # 🆕 PRIORIDAD MÁXIMA: Lista blanca de términos de moda
        if token.text in FASHION_TERMS_WHITELIST:
            elementos_extraidos.add(token.text)
            processed_tokens.add(token)
            continue

        # Ignorar stopwords universalmente para mantener la lógica concisa
        if token.is_stop:
            continue

        # Lógica para Sustantivos (NOUN) y Nombres Propios (PROPN)
        if token.pos_ in ["NOUN", "PROPN"]:
            # 1. Sustantivos que son foco principal (ROOT, dobj, nsubj, obj)
            if token.dep_ in ["ROOT", "dobj", "nsubj", "obj"]:
                elementos_extraidos.add(token.text)
                processed_tokens.add(token)

            # 2. Manejo de 'pobj' (objeto de preposición)
            elif token.dep_ == "pobj":
                # Evitar 'modificadores de modificadores' anidados.
                # Si el pobj es 'frente' y su cabeza es 'botones' (que es un nmod/pobj), excluimos 'frente'.
                # Check if the head of the pobj is also a nominal modifier
                head_of_pobj = token.head
                if head_of_pobj and head_of_pobj.pos_ in ["NOUN", "PROPN"] and head_of_pobj.dep_ in ["nmod", "pobj"]:
                    # This pobj is modifying another nominal modifier, so skip it.
                    pass # Do not add 'frente' in 'con botones al frente' if 'botones' is already a modifier
                else:
                    elementos_extraidos.add(token.text)
                    processed_tokens.add(token)

            # 2b. Manejo de 'obl' (oblique - complemento oblicuo como "con botones")
            elif token.dep_ == "obl":
                # Similar a pobj: evitar modificadores de modificadores
                head_of_obl = token.head
                # Agregar si el head es ROOT o un verbo principal
                if head_of_obl and head_of_obl.dep_ == "ROOT":
                    elementos_extraidos.add(token.text)
                    processed_tokens.add(token)

            # 3. Manejo de 'nmod' (modificador nominal)
            elif token.dep_ == "nmod":
                # Incluir nmod siempre que no sea un modificador de modificador anidado
                head_of_nmod = token.head
                if head_of_nmod and head_of_nmod.pos_ in ["NOUN", "PROPN"]:
                    # Verificar si el head_of_nmod está en una posición válida (no es un modificador profundo)
                    if head_of_nmod.dep_ in ["ROOT", "dobj", "nsubj", "obj"]:
                        elementos_extraidos.add(token.text)
                        processed_tokens.add(token)
                    elif head_of_nmod.dep_ in ["nmod", "pobj"]:
                        # Solo incluir si el head ya fue incluido (no es un modificador de modificador)
                        if head_of_nmod.text in elementos_extraidos or head_of_nmod in processed_tokens:
                            elementos_extraidos.add(token.text)
                            processed_tokens.add(token)
                # Caso especial: nmod con head que es PROPN/NOUN ROOT (ej: "Muestrame" con "bolsillos")
                elif head_of_nmod and head_of_nmod.dep_ == "ROOT":
                    elementos_extraidos.add(token.text)
                    processed_tokens.add(token)            # Ajuste para 'color' como intermediario: si 'color' es un nmod y tiene un amod child,
            # solo añadir el amod child (ej., 'verde') y no 'color' mismo.
            # This rule needs to be checked carefully to ensure it doesn't conflict with the above 'nmod' rules
            if token.text == "color" and token.dep_ == "nmod":
                found_amod_child = False
                for child in token.children:
                    if child.dep_ == "amod" and not child.is_stop:
                        elementos_extraidos.add(child.text)
                        found_amod_child = True
                if found_amod_child:
                    # If 'color' acted as an intermediary for an adjective, ensure 'color' itself is not added as a key term
                    # if it was mistakenly added by a broader rule earlier.
                    # This can be handled by ensuring 'color' is removed if 'verde' was found.
                    if token.text in elementos_extraidos: # If 'color' was added by a previous rule
                        elementos_extraidos.remove(token.text)
                    continue # Skip 'color' as it's an intermediary here


        # Lógica para Adjetivos (ADJ)
        elif token.pos_ == "ADJ" and token.dep_ == "amod":
            # Caso especial: Ignorar modificadores de modificadores
            # e.g., 'amplios' para 'bolsillos' cuando 'bolsillos' es parte de una cláusula relativa/adverbial.
            head_token = token.head
            # Comprobar si la cabeza del adjetivo es un dobj, pobj, nsubj o obj
            # y si su propia cabeza es una cláusula relativa/adverbial ('acl:relcl', 'advcl', 'acl').
            if head_token.dep_ in ["dobj", "pobj", "nsubj", "obj"] and head_token.head:
                # Ampliamos la condición para incluir 'advcl' y 'acl' como tipos de cláusulas que contienen modificadores de modificadores
                if head_token.head.dep_ in ["acl:relcl", "advcl", "acl"]:
                    continue  # Ignorar este adjetivo (modificador de modificador)

            # En otros casos, añadir el adjetivo
            elementos_extraidos.add(token.text)

    # 🆘 FALLBACK MEJORADO: Capturar TODOS los NOUN/PROPN/ADJ que no estén en processed_tokens
    # Esto asegura captar términos mal etiquetados (ej: "grices" con DEP=punct)
    fallback_added = []
    for token in doc:
        if token.is_stop or token in processed_tokens:
            continue
        if token.pos_ in ["NOUN", "PROPN", "ADJ"]:
            if token.text not in elementos_extraidos:
                elementos_extraidos.add(token.text)
                fallback_added.append(token.text)

    # Devolver los términos únicos, ordenados y separados por espacio
    resultado = " ".join(sorted(list(elementos_extraidos)))
    return resultado


def _demo():
    frase1 = "Muestrame delantales verdes con bolsillos"
    frase2 = "que tienes en delantales de color verde, que tengan bolsillos amplios"
    nueva_frase = "quiero una blusa blanca con botones al frente"

    print("--- USO DE LA FUNCIÓN extract_key_terms_with_dependency_parsing REFINADA ---")

    resultado_final1 = extract_key_terms_with_dependency_parsing(frase1)
    print(f"Frase de entrada 1: '{frase1}'")
    print(f"Términos clave extraídos 1: **{resultado_final1}**\n")

    resultado_final2 = extract_key_terms_with_dependency_parsing(frase2)
    print(f"Frase de entrada 2: '{frase2}'")
    print(f"Términos clave extraídos 2: **{resultado_final2}**\n")

    resultado_nueva_frase = extract_key_terms_with_dependency_parsing(nueva_frase)
    print(f"Frase de entrada: '{nueva_frase}'")
    print(f"Términos clave extraídos: **{resultado_nueva_frase}**")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        print(extract_key_terms_with_dependency_parsing(text))
    else:
        _demo()
