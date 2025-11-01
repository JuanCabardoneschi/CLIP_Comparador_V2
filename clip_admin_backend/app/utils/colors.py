"""
Color utilities: normalization and helpers.

Sistema 100% genérico basado en LLM (sin hardcodeo de colores).
"""

from __future__ import annotations

from typing import Optional
import re
import unicodedata
import numpy as np

# Caché en memoria para colores ya normalizados por LLM (evita llamadas repetidas)
_llm_color_cache: dict[str, Optional[str]] = {}

# Caché para embeddings de colores (para comparación semántica)
_color_embedding_cache: dict[str, np.ndarray] = {}


def _strip_accents(s: str) -> str:
    """Elimina acentos de un string."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _normalize_color_hardcoded(s: str) -> Optional[str]:
    """
    DEPRECATED: No usar mapeo hardcoded.

    Retorna None siempre para forzar el uso del LLM.
    Esta función existe solo para evitar errores de importación legacy.
    """
    return None


def _normalize_color_llm(color_str: str) -> Optional[str]:
    """
    Usa el LLM normalizer para extraer el color canónico.
    Cachea resultados para evitar llamadas repetidas.
    """
    # Revisar caché primero
    cache_key = color_str.lower().strip()
    if cache_key in _llm_color_cache:
        return _llm_color_cache[cache_key]

    try:
        from app.utils.llm_query_normalizer import normalize_query

        # El LLM normalizer devuelve {'color': ..., 'tipo': ..., ...}
        result = normalize_query(color_str)
        detected = result.get('color')

        # Normalizar a lowercase para comparaciones case-insensitive
        normalized = detected.lower() if detected else None

        # Cachear resultado
        _llm_color_cache[cache_key] = normalized
        return normalized

    except Exception as e:
        print(f"Error normalize_color LLM: {e}")
        _llm_color_cache[cache_key] = None
        return None


def normalize_color(color_str: Optional[str]) -> Optional[str]:
    """
    Normaliza nombres de colores usando SOLO el LLM (100% genérico, sin hardcodeo).

    Estrategia:
    - Usa el LLM normalizer para extraer el color base
    - Cachea resultados para performance
    - Totalmente independiente del dominio del cliente

    Ejemplos:
    - "Azul marino" -> LLM -> "azul"
    - "Jean" -> LLM -> "azul"
    - "Beige" -> LLM -> "beige"
    - "Marrón chocolate" -> LLM -> "marrón"
    - "Habano" -> LLM -> contexto del cliente

    Returns:
        Color normalizado por LLM (lowercase) o None si no puede normalizar.
    """
    if not color_str:
        return None

    # Pre-procesamiento básico: minúsculas, quitar acentos y ruido
    s = str(color_str).strip().lower()
    s = _strip_accents(s)
    # Quitar paréntesis y contenido accesorio
    s = re.sub(r"\(.*?\)", "", s)
    # Mantener letras y espacios
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # Usar LLM para normalización (con caché)
    if len(s) >= 3:
        return _normalize_color_llm(s)

    return None


def _get_color_embedding(color_str: str) -> Optional[np.ndarray]:
    """
    Obtiene el embedding semántico de un color usando el LLM normalizer.
    Cachea resultados para evitar recálculos.
    """
    if not color_str:
        return None

    cache_key = color_str.lower().strip()
    if cache_key in _color_embedding_cache:
        return _color_embedding_cache[cache_key]

    try:
        from app.utils.llm_query_normalizer import normalize_query

        # El LLM normalizer devuelve embedding en result['embedding']
        result = normalize_query(color_str)
        embedding = result.get('embedding')

        if embedding:
            emb_array = np.array(embedding, dtype=np.float32)
            _color_embedding_cache[cache_key] = emb_array
            return emb_array
    except Exception as e:
        print(f"Error _get_color_embedding: {e}")

    return None


def colors_are_similar(color1: str, color2: str, threshold: float = 0.75) -> bool:
    """
    Determina si dos colores son semánticamente similares usando SOLO LLM embeddings.

    Estrategia 100% genérica (sin hardcodeo):
    1. Normaliza ambos colores con LLM
    2. Si son iguales normalizados -> match exacto
    3. Si no, compara embeddings semánticos con threshold configurable
    4. Threshold 0.75 permite capturar similitudes como beige~chocolate, habano~marrón

    Args:
        color1: Primer color (ej: "beige", "Beige claro")
        color2: Segundo color (ej: "marrón chocolate", "chocolate")
        threshold: Umbral de similitud coseno (default 0.75 = flexible para tonos similares)

    Returns:
        True si los colores son similares semánticamente

    Ejemplos:
        colors_are_similar("beige", "chocolate") -> True si embedding sim >= 0.75
        colors_are_similar("habano", "marrón") -> True si LLM los considera similares
        colors_are_similar("azul", "negro") -> False (embeddings muy diferentes)
    """
    if not color1 or not color2:
        return False

    # Normalizar ambos colores con LLM
    c1_norm = normalize_color(color1)
    c2_norm = normalize_color(color2)

    # Si son exactamente iguales normalizados, son similares
    if c1_norm and c2_norm and c1_norm.lower() == c2_norm.lower():
        print(f"  Exact Match (LLM): '{c1_norm}' == '{c2_norm}'")
        return True

    # Usar embeddings semánticos del LLM para comparación
    emb1 = _get_color_embedding(color1)
    emb2 = _get_color_embedding(color2)

    if emb1 is not None and emb2 is not None:
        similarity = float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
        result = similarity >= threshold

        if result:
            print(f"  Semantic Match: '{color1}' <-> '{color2}' = {similarity:.3f} (>={threshold})")
        else:
            print(f"  No Match: '{color1}' <-> '{color2}' = {similarity:.3f} (<{threshold})")

        return result

    print(f"  No embeddings available for '{color1}' or '{color2}'")
    return False
