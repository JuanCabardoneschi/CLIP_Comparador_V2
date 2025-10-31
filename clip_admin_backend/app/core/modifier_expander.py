"""Color modifier expansion logic (deprecated).

Con la introducción del normalizador LLM, dejamos de expandir manualmente
los modificadores de color. Esta función queda como no-op por compatibilidad.
"""
from __future__ import annotations

from typing import Optional


def expand_color_modifiers(query: str, client_id: Optional[str] = None) -> str:
    """No-op: mantenemos la query original. La interpretación la hace el LLM."""
    return query
