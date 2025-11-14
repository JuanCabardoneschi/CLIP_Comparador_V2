"""Prueba directa SOLO con LLM embeddings para clasificación de categoría.

Uso:
    python test_llm_category_match.py "short rojo"
Si no se pasa argumento, prueba lote de casos.

Clasificación:
- literal: similitud >= 0.92 o match normalizado exacto
- similar: similitud >= 0.78
- ninguna: por debajo de 0.78

Cliente: Goody Store (UUID conocido)
No usa CLIP ni heurísticas previas.
"""
import os
import sys
import math
from dataclasses import dataclass
from typing import List, Tuple
from sentence_transformers import util
from dotenv import load_dotenv
import psycopg2

# Ajustes de umbrales (se pueden mover a config luego)
SIMILAR_THRESHOLD = 0.65  # Bajado para captar similitudes moderadas (camisa blanca → CAMISAS)
LITERAL_THRESHOLD = 0.92
GOODY_CLIENT_ID = "60231500-ca6f-4c46-a960-2e17298fcdb0"

def norm_text(s: str) -> str:
    import re, unicodedata
    s = ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s

@dataclass
class CatSim:
    name: str
    similarity: float
    literal: bool


def load_categories():
    load_dotenv('.env.local')
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise RuntimeError("DATABASE_URL no definido en .env.local")
    # Conectar directamente usando la URL (maneja passwords con caracteres especiales)
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT name FROM categories
            WHERE client_id = %s AND is_active = TRUE
        """, (GOODY_CLIENT_ID,))
        rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

# Reutilizar modelo del normalizer
from clip_admin_backend.app.utils.llm_query_normalizer import get_model


def classify_query(query: str, categories: List[str]) -> Tuple[str, List[CatSim]]:
    model = get_model()
    q_emb = model.encode(query.lower())
    sims: List[CatSim] = []
    for cat in categories:
        cat_emb = model.encode(cat.lower())
        sim = float(util.cos_sim(q_emb, cat_emb)[0][0])
        literal = norm_text(cat) == norm_text(query)
        sims.append(CatSim(cat, sim, literal))
    sims.sort(key=lambda x: x.similarity, reverse=True)
    best = sims[0] if sims else None
    if not best:
        return ("ninguna", sims)
    if best.literal or best.similarity >= LITERAL_THRESHOLD:
        return ("literal", sims)
    if best.similarity >= SIMILAR_THRESHOLD:
        return ("similar", sims)
    return ("ninguna", sims)


def run_tests(queries: List[str]):
    cats = load_categories()
    print(f"Categorías Goody ({len(cats)}): {cats}\n")
    for q in queries:
        status, sims = classify_query(q, cats)
        print(f"Query: '{q}' => clasificación: {status.upper()}")
        print("Top similitudes:")
        for s in sims[:5]:
            bar = '█' * int(max(1, math.floor(s.similarity * 10)))
            print(f"  - {s.name:<25} sim={s.similarity:.3f} {'(literal)' if s.literal else ''} {bar}")
        print()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        run_tests([' '.join(sys.argv[1:])])
    else:
        run_tests([
            'camisas hombre dama',         # idéntica
            'camisa blanca',               # similar
            'delantal completo',           # idéntica
            'delantalito negro',           # diminutivo similar
            'buzo frizado',                # similar a BUZOS
            'short rojo',                  # fuera de catálogo
            'auto verde'                   # ridícula
        ])
