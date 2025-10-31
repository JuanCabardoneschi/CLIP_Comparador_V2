"""Color utilities: normalization and helpers.

Minimal, dependency-light helpers to keep API routes slim.
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
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _normalize_color_hardcoded(s: str) -> Optional[str]:
    """
    Normalización rápida por mapeo hardcoded de colores comunes.
    Devuelve color canónico en MAYÚSCULAS o None si no reconoce.
    """
    # Mapeos por substrings (orden importa: más específicos primero)
    # AZUL
    if any(k in s for k in ["azul", "celeste", "marino", "jean", "denim"]):
        return "AZUL"

    # NEGRO / BLANCO / GRIS
    if "negro" in s:
        return "NEGRO"
    if "blanco" in s:
        return "BLANCO"
    if "gris" in s:
        return "GRIS"

    # VERDE / ROJO / AMARILLO
    if "verde" in s:
        return "VERDE"
    if "rojo" in s:
        return "ROJO"
    if "amarillo" in s or "mostaza" in s:
        return "AMARILLO"

    # MARRON/HABANO/BEIGE/NARANJA (agrupados suavemente)
    if any(k in s for k in ["marron", "habano", "chocolate", "castano"]):
        return "MARRON"
    if "beige" in s or "crema" in s:
        return "BEIGE"
    if "naranja" in s:
        return "NARANJA"

    # MORADO/VIOLETA/ROSA
    if any(k in s for k in ["morado", "violeta", "purpura", "lila"]):
        return "MORADO"
    if "rosa" in s or "fucsia" in s:
        return "ROSA"

    # Más colores comunes
    if "turquesa" in s or "petroleo" in s or "cyan" in s:
        return "TURQUESA"
    if "dorado" in s or "oro" in s:
        return "DORADO"
    if "plateado" in s or "plata" in s:
        return "PLATEADO"

    return None


def _normalize_color_llm(color_str: str) -> Optional[str]:
    """
    Fallback: usa el LLM normalizer para extraer el color canónico.
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

        # Normalizar a MAYÚSCULAS si existe
        normalized = detected.upper() if detected else None

        # Cachear resultado
        _llm_color_cache[cache_key] = normalized
        return normalized

    except Exception as e:
        print(f"⚠️ normalize_color LLM fallback error: {e}")
        _llm_color_cache[cache_key] = None
        return None


def normalize_color(color_str: Optional[str]) -> Optional[str]:
    """
    Normaliza nombres de colores a una forma canónica en MAYÚSCULAS.

    Estrategia híbrida:
    1. Mapping hardcoded para colores comunes (instantáneo)
    2. Fallback LLM para colores no reconocidos (con caché)

    Ejemplos:
    - "Azul marino" → "AZUL"
    - "Jean" → "AZUL"
    - "Fucsia vibrante" → "ROSA"
    - "Coral" → (LLM) → cached result

    Returns:
        Color canónico en MAYÚSCULAS o None si no puede normalizar.
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

    # PASO 1: Intentar mapeo hardcoded (rápido)
    hardcoded = _normalize_color_hardcoded(s)
    if hardcoded:
        return hardcoded

    # PASO 2: Fallback con LLM (para colores raros/nuevos)
    # Solo si el color tiene contenido significativo
    if len(s) >= 3:
        return _normalize_color_llm(s)

    return None


# Grupos de colores similares (tonos que se perciben como "el mismo" color)
SIMILAR_COLOR_GROUPS = [
    {'BEIGE', 'MARRON'},  # Tonos tierra/café
    {'AZUL', 'TURQUESA'},  # Azules
    {'ROSA', 'MORADO'},  # Rosas/Violetas
    {'GRIS', 'PLATEADO'},  # Grises
    {'AMARILLO', 'DORADO'},  # Amarillos/Dorados
]


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
        print(f"⚠️ _get_color_embedding error: {e}")

    return None


def colors_are_similar(color1: str, color2: str, threshold: float = 0.85) -> bool:
    """
    Determina si dos colores son semánticamente similares.

    Estrategia híbrida (en orden de prioridad):
    1. Comparación exacta (normalizada)
    2. Grupos de colores similares (hardcoded, basado en percepción visual)
    3. Fallback: LLM embeddings con threshold MUY alto (solo para casos edge)

    Args:
        color1: Primer color (ej: "beige", "BEIGE")
        color2: Segundo color (ej: "marrón chocolate", "MARRON")
        threshold: Umbral de similitud coseno para LLM fallback (0.85 = muy estricto)

    Returns:
        True si los colores son similares

    Ejemplos:
        colors_are_similar("beige", "marrón chocolate") → True (grupo BEIGE-MARRON)
        colors_are_similar("coral", "salmón") → True (LLM fallback si >0.85)
        colors_are_similar("beige", "negro") → False (LLM: 0.765 < 0.85)
    """
    if not color1 or not color2:
        return False

    # Si son exactamente iguales (case-insensitive), son similares
    c1_lower = color1.lower().strip()
    c2_lower = color2.lower().strip()
    if c1_lower == c2_lower:
        return True

    # Normalizar ambos colores
    c1_norm = normalize_color(color1)
    c2_norm = normalize_color(color2)

    # Si son exactamente iguales normalizados, son similares
    if c1_norm and c2_norm and c1_norm == c2_norm:
        return True

    # Revisar grupos de colores similares (prioridad: rápido y confiable)
    if c1_norm and c2_norm:
        for group in SIMILAR_COLOR_GROUPS:
            if c1_norm in group and c2_norm in group:
                print(f"  ✅ Grupo similar: '{c1_norm}' y '{c2_norm}' en {group}")
                return True

    # Fallback: LLM embeddings (solo para colores raros con threshold MUY alto)
    # Esto maneja casos como "coral" vs "salmón" que no están en los grupos hardcoded
    emb1 = _get_color_embedding(color1)
    emb2 = _get_color_embedding(color2)

    if emb1 is not None and emb2 is not None:
        similarity = float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
        result = similarity >= threshold

        # Log solo cuando el LLM realmente decide (no cuando los grupos ya decidieron)
        if result:
            print(f"  🔬 LLM Match: '{color1}' vs '{color2}' = {similarity:.3f} (>={threshold})")

        return result

    return False
