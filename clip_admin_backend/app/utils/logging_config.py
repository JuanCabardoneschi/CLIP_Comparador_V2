"""
Sistema de Logging Centralizado con 4 Niveles Configurables
Permite controlar la verbosidad desde el panel de super-admin
"""

import sys
from enum import Enum
from typing import Any, Optional
from functools import wraps


class LogLevel(Enum):
    """Niveles de logging del sistema"""
    ERROR_ONLY = 1           # Solo errores críticos
    REQUEST_LIFECYCLE = 2    # + Inicio/fin de requests y métricas
    MAIN_PROCESSES = 3       # + Procesos principales (detección, embeddings, búsquedas)
    VERBOSE = 4              # Todo (máximo detalle)


class LogCategory(Enum):
    """Categorías de logs para organizar la salida"""
    ERROR = "ERROR"
    REQUEST = "REQUEST"
    SEARCH = "SEARCH"
    EMBEDDING = "EMBEDDING"
    CATEGORY_DETECTION = "CATEGORY"
    COLOR = "COLOR"
    NLP = "NLP"
    CACHE = "CACHE"
    DATABASE = "DATABASE"
    SYSTEM = "SYSTEM"


# Mapeo de categorías a niveles mínimos requeridos
CATEGORY_MIN_LEVEL = {
    LogCategory.ERROR: LogLevel.ERROR_ONLY,
    LogCategory.REQUEST: LogLevel.REQUEST_LIFECYCLE,
    LogCategory.SEARCH: LogLevel.MAIN_PROCESSES,
    LogCategory.EMBEDDING: LogLevel.MAIN_PROCESSES,
    LogCategory.CATEGORY_DETECTION: LogLevel.MAIN_PROCESSES,
    LogCategory.COLOR: LogLevel.VERBOSE,
    LogCategory.NLP: LogLevel.VERBOSE,
    LogCategory.CACHE: LogLevel.VERBOSE,
    LogCategory.DATABASE: LogLevel.VERBOSE,
    LogCategory.SYSTEM: LogLevel.REQUEST_LIFECYCLE,
}


def get_current_log_level() -> LogLevel:
    """
    Obtiene el nivel de log configurado actualmente

    Returns:
        LogLevel configurado o REQUEST_LIFECYCLE por defecto
    """
    try:
        from app.utils.system_config import system_config
        level_name = system_config.get('system', 'log_level', default='ERROR_ONLY')
        return LogLevel[level_name]
    except Exception:
        # Fallback si hay error leyendo config
        return LogLevel.ERROR_ONLY


def should_log(category: LogCategory) -> bool:
    """
    Determina si se debe registrar un log de esta categoría

    Args:
        category: Categoría del log

    Returns:
        True si el nivel actual permite logs de esta categoría
    """
    current_level = get_current_log_level()
    required_level = CATEGORY_MIN_LEVEL.get(category, LogLevel.VERBOSE)
    return current_level.value >= required_level.value


def log(category: LogCategory, message: str, force: bool = False):
    """
    Registra un mensaje si el nivel de log lo permite

    Args:
        category: Categoría del log
        message: Mensaje a registrar
        force: Si True, registra sin importar el nivel (usar solo para errores críticos)
    """
    if force or should_log(category):
        prefix = f"[{category.value}]"
        print(f"{prefix} {message}", file=sys.stderr, flush=True)


def log_error(message: str, exc_info: Optional[Exception] = None):
    """
    Registra un error (siempre se muestra)

    Args:
        message: Mensaje de error
        exc_info: Excepción opcional para incluir traceback
    """
    print(f"[ERROR] {message}", file=sys.stderr, flush=True)
    if exc_info:
        import traceback
        print(traceback.format_exc(), file=sys.stderr, flush=True)


def log_request(method: str, path: str, duration_ms: Optional[float] = None, status: Optional[int] = None):
    """
    Registra información de request/response

    Args:
        method: Método HTTP
        path: Ruta del request
        duration_ms: Duración en milisegundos (opcional)
        status: Código de estado HTTP (opcional)
    """
    if should_log(LogCategory.REQUEST):
        if duration_ms is not None and status is not None:
            log(LogCategory.REQUEST, f"{method} {path} - {status} ({duration_ms:.0f}ms)")
        else:
            log(LogCategory.REQUEST, f"{method} {path}")


def log_search(message: str):
    """Registra operación de búsqueda"""
    log(LogCategory.SEARCH, message)


def log_embedding(message: str):
    """Registra operación de embedding"""
    log(LogCategory.EMBEDDING, message)


def log_category_detection(message: str):
    """Registra detección de categoría"""
    log(LogCategory.CATEGORY_DETECTION, message)


def log_color(message: str):
    """Registra operación de color"""
    log(LogCategory.COLOR, message)


def log_nlp(message: str):
    """Registra operación NLP"""
    log(LogCategory.NLP, message)


def log_cache(message: str):
    """Registra operación de cache"""
    log(LogCategory.CACHE, message)


def log_database(message: str):
    """Registra operación de base de datos"""
    log(LogCategory.DATABASE, message)


def log_system(message: str):
    """Registra información del sistema"""
    log(LogCategory.SYSTEM, message)


def log_verbose(category: LogCategory, message: str):
    """
    Registra mensaje verbose (solo en nivel VERBOSE)

    Args:
        category: Categoría del mensaje
        message: Contenido del mensaje
    """
    if get_current_log_level() == LogLevel.VERBOSE:
        log(category, message)


def timed_operation(category: LogCategory, operation_name: str):
    """
    Decorador para medir tiempo de operaciones

    Args:
        category: Categoría de la operación
        operation_name: Nombre descriptivo

    Usage:
        @timed_operation(LogCategory.SEARCH, "búsqueda textual")
        def search_products(query):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if should_log(category):
                import time
                start = time.time()
                log(category, f"⏱️ Iniciando: {operation_name}")

            try:
                result = func(*args, **kwargs)

                if should_log(category):
                    duration = (time.time() - start) * 1000
                    log(category, f"✅ Completado: {operation_name} ({duration:.0f}ms)")

                return result
            except Exception as e:
                log_error(f"❌ Error en {operation_name}: {str(e)}", exc_info=e)
                raise

        return wrapper
    return decorator


# Funciones de compatibilidad con código existente
def railway_log(message: str):
    """
    Compatibilidad con railway_log existente
    Automáticamente categoriza como REQUEST o SYSTEM
    """
    if "REQUEST" in message or "RESPONSE" in message:
        log(LogCategory.REQUEST, message)
    else:
        log(LogCategory.SYSTEM, message)


def clip_log(message: str):
    """Log específico para operaciones CLIP"""
    log(LogCategory.EMBEDDING, message)


def print_if_verbose(message: str):
    """
    Compatibilidad con print() condicionados existentes
    Solo imprime en nivel VERBOSE
    """
    if get_current_log_level() == LogLevel.VERBOSE:
        print(message, file=sys.stderr, flush=True)
