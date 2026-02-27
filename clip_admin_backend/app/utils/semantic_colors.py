#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Utilidad de mapeo semántico de adjetivos sistémicos de color.
No modifica atributos del cliente; solo propone colores existentes
según similitud de embeddings.
"""
import json, os, unicodedata, math
from typing import List, Dict, Tuple
from pathlib import Path

# Cache en memoria
_SYSTEM_COLOR_DATA = None
_SYSTEM_COLOR_SET = None
_COLOR_EMB_CACHE: Dict[str, List[float]] = {}
_ADJ_EMB_CACHE: Dict[str, List[float]] = {}
_MODEL = None

# Intentamos usar sentence-transformers, si no, fallback spaCy
def _load_embedding_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    # Reutilizar MiniLM singleton ya gestionado por llm_query_normalizer
    # para evitar doble carga de modelo y picos de memoria.
    try:
        from app.utils.llm_query_normalizer import get_model as _get_shared_minilm
        _MODEL = _get_shared_minilm()
        if _MODEL is not None:
            print("[SEMANTIC_COLORS] Reutilizando modelo MiniLM compartido (llm_query_normalizer)")
            return _MODEL
    except Exception as e_shared:
        print(f"[SEMANTIC_COLORS] ⚠️ No se pudo reutilizar MiniLM compartido ({e_shared})")

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        model_name = os.getenv(
            "SEMANTIC_COLOR_ST_MODEL",
            os.getenv("MINILM_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        )
        _MODEL = SentenceTransformer(model_name)
        print(f"[SEMANTIC_COLORS] Modelo SentenceTransformer cargado: {model_name}")
    except Exception as e:
        print(f"[SEMANTIC_COLORS] ⚠️ No se pudo cargar SentenceTransformer ({e}), usando spaCy fallback")
        try:
            import spacy  # type: ignore
            nlp = spacy.load(os.getenv("SPACY_MODEL", "es_core_news_md"), disable=["ner","textcat"])
            _MODEL = nlp
        except Exception as ee:
            print(f"[SEMANTIC_COLORS] ❌ Fallback spaCy también falló: {ee}")
            _MODEL = None
    return _MODEL


def _normalize(text: str) -> str:
    txt = text.strip().lower()
    txt = ''.join(ch for ch in unicodedata.normalize('NFD', txt) if unicodedata.category(ch) != 'Mn')
    return txt


def _load_system_colors():
    global _SYSTEM_COLOR_DATA, _SYSTEM_COLOR_SET
    if _SYSTEM_COLOR_DATA is not None:
        return _SYSTEM_COLOR_DATA
    json_path = Path(__file__).resolve().parents[3] / "shared" / "system_semantic_colors.json"
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            _SYSTEM_COLOR_DATA = json.load(f)
        _SYSTEM_COLOR_SET = {_normalize(item['token']) for item in _SYSTEM_COLOR_DATA.get('colors', [])}
        print(f"[SEMANTIC_COLORS] Vocabulario sistémico cargado: {_SYSTEM_COLOR_SET}")
    except Exception as e:
        print(f"[SEMANTIC_COLORS] ⚠️ No se pudo cargar JSON de colores sistémicos ({e})")
        _SYSTEM_COLOR_DATA = {"colors": [], "config": {}}
        _SYSTEM_COLOR_SET = set()
    return _SYSTEM_COLOR_DATA


def get_system_color_adjectives() -> List[str]:
    _load_system_colors()
    return sorted(list(_SYSTEM_COLOR_SET))


def _embed(text: str) -> List[float]:
    model = _load_embedding_model()
    if model is None:
        return []
    if hasattr(model, 'encode'):
        return list(map(float, model.encode([text])[0]))
    # spaCy fallback
    return list(map(float, model(text).vector))


def _embed_many(texts: List[str]) -> Dict[str, List[float]]:
    model = _load_embedding_model()
    if model is None:
        return {t: [] for t in texts}

    unique_texts = []
    seen = set()
    for text in texts:
        if text and text not in seen:
            unique_texts.append(text)
            seen.add(text)

    if not unique_texts:
        return {}

    if hasattr(model, 'encode'):
        vectors = model.encode(unique_texts)
        return {
            text: list(map(float, vectors[idx]))
            for idx, text in enumerate(unique_texts)
        }

    # spaCy fallback
    return {
        text: list(map(float, model(text).vector))
        for text in unique_texts
    }


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    import numpy as np
    va = np.array(a)
    vb = np.array(b)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def map_semantic_colors(adjectives: List[str], client_color_values: List[str]) -> Dict[str, List[Tuple[str, float]]]:
    """Devuelve para cada adjetivo sistémico una lista de (color_cliente, similitud) ordenada.
    Sólo incluye colores sobre umbrales definidos en config.
    """
    data = _load_system_colors()
    cfg = data.get('config', {})
    thr = float(cfg.get('similarity_threshold', 0.55))
    thr_fb = float(cfg.get('fallback_threshold', 0.48))
    top_k = int(cfg.get('top_k', 3))
    max_final = int(cfg.get('max_final_colors', 2))

    client_colors_norm = [_normalize(c) for c in client_color_values]
    results: Dict[str, List[Tuple[str, float]]] = {}

    color_entries = {
        _normalize(item.get('token', '')): item
        for item in data.get('colors', [])
        if item.get('token')
    }

    # Embeddings colores cliente cacheados (batch para reducir latencia)
    missing_colors = [
        norm_color
        for norm_color in client_colors_norm
        if norm_color not in _COLOR_EMB_CACHE
    ]
    if missing_colors:
        color_batch = _embed_many(missing_colors)
        for norm_color in missing_colors:
            _COLOR_EMB_CACHE[norm_color] = color_batch.get(norm_color, [])

    # Embeddings de adjetivos faltantes (batch)
    missing_adjs = []
    for adj in adjectives:
        adj_norm = _normalize(adj)
        if adj_norm and adj_norm not in _ADJ_EMB_CACHE:
            missing_adjs.append(adj_norm)
    if missing_adjs:
        adj_batch = _embed_many(missing_adjs)
        for adj_norm in missing_adjs:
            _ADJ_EMB_CACHE[adj_norm] = adj_batch.get(adj_norm, [])

    for adj in adjectives:
        adj_norm = _normalize(adj)
        if adj_norm in results:
            continue

        # Prioridad 1: fallback léxico por configuración (ej: chocolate -> familia marrón)
        # Se aplica ANTES de embeddings para evitar desvíos semánticos (ej: chocolate -> gris).
        entry = color_entries.get(adj_norm, {})
        preferred_matches = [
            _normalize(v) for v in entry.get('preferred_matches', [])
            if isinstance(v, str) and v.strip()
        ]
        if preferred_matches:
            lexical = []
            for raw_color, norm_color in zip(client_color_values, client_colors_norm):
                if any(pref in norm_color for pref in preferred_matches):
                    lexical.append((raw_color, 1.0))
            if lexical:
                results[adj_norm] = lexical[:max_final]
                continue

        emb_adj = _ADJ_EMB_CACHE[adj_norm]
        sims = []
        for raw_color, norm_color in zip(client_color_values, client_colors_norm):
            emb_col = _COLOR_EMB_CACHE.get(norm_color, [])
            score = _cosine(emb_adj, emb_col)
            sims.append((raw_color, score))
        sims.sort(key=lambda x: x[1], reverse=True)

        # Selección por umbrales
        filtered = [p for p in sims if p[1] >= thr]
        if not filtered and sims and sims[0][1] >= thr_fb:
            filtered = [sims[0]]  # Fallback top1

        filtered = filtered[:top_k]

        # Recorte final
        filtered = filtered[:max_final]
        results[adj_norm] = filtered

    return results


SYSTEM_COLOR_ADJECTIVES = get_system_color_adjectives()

__all__ = [
    'SYSTEM_COLOR_ADJECTIVES',
    'map_semantic_colors',
    'get_system_color_adjectives'
]
