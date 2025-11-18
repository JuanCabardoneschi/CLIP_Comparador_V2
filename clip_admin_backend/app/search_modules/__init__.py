"""
Módulos de Búsqueda Personalizados por Cliente

Cada cliente tiene su propio módulo con:
- Normalización de tokens específica
- Mapeo de sinónimos
- Filtros de categoría personalizados
- Lógica de expansión de query

Estructura:
    search_client_{slug}.py - Módulo específico del cliente

    Cada módulo debe implementar:
    - normalize_tokens(text: str) -> List[str]
    - expand_query(query: str) -> List[str]
    - detect_category_filter(query_tokens: List[str], categories: List[Category]) -> Optional[List[str]]
"""

from typing import Optional, List, Callable
from app.models.category import Category

# Registry de módulos por client slug
_CLIENT_MODULES = {}


def register_client_module(client_slug: str, module):
    """Registra un módulo personalizado para un cliente"""
    _CLIENT_MODULES[client_slug] = module
    print(f"✅ Módulo personalizado registrado: {client_slug}")


def get_client_module(client_slug: str):
    """Obtiene el módulo personalizado de un cliente o None si no existe"""
    return _CLIENT_MODULES.get(client_slug)


def has_custom_module(client_slug: str) -> bool:
    """Verifica si existe módulo personalizado para el cliente"""
    return client_slug in _CLIENT_MODULES


# ============================================================================
# AUTOLOAD DE MÓDULOS PERSONALIZADOS
# ============================================================================

def _autoload_client_modules():
    """
    Auto-registra todos los módulos search_client_*.py encontrados en este directorio.
    """
    import os
    import importlib

    current_dir = os.path.dirname(__file__)

    for filename in os.listdir(current_dir):
        if filename.startswith('search_client_') and filename.endswith('.py'):
            # Extraer slug del nombre del archivo
            # search_client_eve_s_store.py → eve_s_store
            client_slug = filename.replace('search_client_', '').replace('.py', '')

            # Importar dinámicamente
            try:
                module_name = f'app.search_modules.{filename[:-3]}'  # Sin .py
                module = importlib.import_module(module_name)
                register_client_module(client_slug, module)
                print(f"✅ Autoload: Módulo '{client_slug}' registrado")
            except Exception as e:
                print(f"⚠️ Error cargando módulo '{client_slug}': {e}")


# Ejecutar autoload al importar este paquete
_autoload_client_modules()
