"""
Script de Ejemplo: Cómo Migrar Logs al Nuevo Sistema

Este archivo muestra patrones de migración de código antiguo a nuevo sistema de logging.
NO ejecutar este archivo, solo usarlo como referencia.
"""

# ============================================================================
# PATRÓN 1: Reemplazar print() por logging categorizado
# ============================================================================

# ❌ ANTES (código antiguo)
print(f"✅ spaCy modelo '{model_name}' cargado exitosamente", flush=True)
print(f"⚠️ No se pudo cargar sistema: {e}")
print(f"[DEBUG] Procesando {len(tokens)} tokens")

# ✅ DESPUÉS (código nuevo)
from app.utils.logging_config import log_nlp, log_error, log_verbose, LogCategory

log_nlp(f"spaCy modelo '{model_name}' cargado exitosamente")
log_error(f"No se pudo cargar sistema: {e}")
log_verbose(LogCategory.NLP, f"Procesando {len(tokens)} tokens")


# ============================================================================
# PATRÓN 2: Reemplazar logger.debug/info/warning/error
# ============================================================================

# ❌ ANTES
import logging
logger = logging.getLogger(__name__)

logger.debug("Token procesado: ...")  # Solo debug
logger.info("Búsqueda iniciada")      # Info general
logger.warning("Cache miss")          # Warning
logger.error("Error conectando BD")   # Error

# ✅ DESPUÉS
from app.utils.logging_config import (
    log_verbose, log_search, log_error, LogCategory
)

log_verbose(LogCategory.NLP, "Token procesado: ...")  # Solo VERBOSE
log_search("Búsqueda iniciada")                       # MAIN_PROCESSES+
log_verbose(LogCategory.CACHE, "Cache miss")          # Solo VERBOSE
log_error("Error conectando BD")                      # Siempre


# ============================================================================
# PATRÓN 3: Logs condicionales basados en nivel
# ============================================================================

# ❌ ANTES
import os
if os.getenv("DEBUG") == "True":
    print(f"Debug: {message}")

# ✅ DESPUÉS
from app.utils.logging_config import log_verbose, LogCategory

# Se muestra automáticamente solo en nivel VERBOSE
log_verbose(LogCategory.SYSTEM, f"Debug: {message}")


# ============================================================================
# PATRÓN 4: Railway logs (stderr con flush)
# ============================================================================

# ❌ ANTES
import sys
print(f"[RAILWAY] {message}", file=sys.stderr, flush=True)

# ✅ DESPUÉS
from app.utils.logging_config import railway_log

railway_log(message)  # Automáticamente categoriza como REQUEST o SYSTEM


# ============================================================================
# PATRÓN 5: Logs de operaciones largas con tiempo
# ============================================================================

# ❌ ANTES
import time
start = time.time()
print(f"Iniciando procesamiento...")
# ... operación ...
duration = (time.time() - start) * 1000
print(f"Completado en {duration:.0f}ms")

# ✅ DESPUÉS
from app.utils.logging_config import timed_operation, LogCategory

@timed_operation(LogCategory.SEARCH, "procesamiento de búsqueda")
def process_search(query):
    # ... operación ...
    return results

# Output automático (en MAIN_PROCESSES+):
# [SEARCH] ⏱️ Iniciando: procesamiento de búsqueda
# [SEARCH] ✅ Completado: procesamiento de búsqueda (342ms)


# ============================================================================
# PATRÓN 6: Logs de requests HTTP
# ============================================================================

# ❌ ANTES
@app.before_request
def log_request():
    print(f"🌐 REQUEST: {request.method} {request.path}")

@app.after_request
def log_response(response):
    print(f"🌐 RESPONSE: {response.status_code}")
    return response

# ✅ DESPUÉS
from app.utils.logging_config import log_request
import time

@app.before_request
def before_request():
    request._start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(request, '_start_time'):
        duration = (time.time() - request._start_time) * 1000
        log_request(request.method, request.path, duration, response.status_code)
    return response

# Output (en REQUEST_LIFECYCLE+):
# [REQUEST] POST /api/search - 200 (342ms)


# ============================================================================
# PATRÓN 7: Categorías específicas por contexto
# ============================================================================

# Según el contexto, usar la categoría apropiada:

# Búsquedas
from app.utils.logging_config import log_search
log_search(f"Buscando {len(results)} productos para '{query}'")

# Embeddings/CLIP
from app.utils.logging_config import log_embedding
log_embedding(f"Generando embedding para imagen {image_id}")

# Detección de categorías
from app.utils.logging_config import log_category_detection
log_category_detection(f"Categoría detectada: {category.name} (score={score:.3f})")

# Colores
from app.utils.logging_config import log_color
log_color(f"Color '{raw}' normalizado a '{normalized}'")

# NLP/Tokenización
from app.utils.logging_config import log_nlp
log_nlp(f"Tokens extraídos: {tokens}")

# Cache
from app.utils.logging_config import log_cache
log_cache(f"Cache hit para key: {cache_key}")

# Base de datos
from app.utils.logging_config import log_database
log_database(f"Query ejecutada: SELECT ... (rows={count})")

# Sistema general
from app.utils.logging_config import log_system
log_system(f"Modelo CLIP cargado en memoria")


# ============================================================================
# PATRÓN 8: Manejo de errores con traceback
# ============================================================================

# ❌ ANTES
import traceback
try:
    # ... código ...
    pass
except Exception as e:
    print(f"❌ Error: {e}")
    print(traceback.format_exc())

# ✅ DESPUÉS
from app.utils.logging_config import log_error

try:
    # ... código ...
    pass
except Exception as e:
    log_error(f"Error procesando búsqueda: {str(e)}", exc_info=e)
    # Automáticamente incluye traceback


# ============================================================================
# PATRÓN 9: Logs condicionales según feature flags
# ============================================================================

# ❌ ANTES
if enable_debug_mode:
    print(f"Debug info: {data}")

# ✅ DESPUÉS
from app.utils.logging_config import should_log, log, LogCategory

if should_log(LogCategory.SEARCH):
    log(LogCategory.SEARCH, f"Debug info: {data}")

# O más simple con log_verbose:
from app.utils.logging_config import log_verbose, LogCategory
log_verbose(LogCategory.SEARCH, f"Debug info: {data}")


# ============================================================================
# EJEMPLO COMPLETO: Migración de un archivo
# ============================================================================

# ❌ ANTES: app/services/example_service.py
"""
import logging

logger = logging.getLogger(__name__)

class ExampleService:
    def process(self, data):
        logger.info("Procesando datos...")

        try:
            logger.debug(f"Entrada: {data}")
            result = self._do_work(data)
            logger.debug(f"Resultado: {result}")
            logger.info("Procesamiento exitoso")
            return result
        except Exception as e:
            logger.error(f"Error: {e}")
            raise
"""

# ✅ DESPUÉS: app/services/example_service.py
"""
from app.utils.logging_config import (
    log_search, log_verbose, log_error,
    LogCategory, timed_operation
)

class ExampleService:
    @timed_operation(LogCategory.SEARCH, "procesamiento de datos")
    def process(self, data):
        log_search("Procesando datos...")

        try:
            log_verbose(LogCategory.SEARCH, f"Entrada: {data}")
            result = self._do_work(data)
            log_verbose(LogCategory.SEARCH, f"Resultado: {result}")
            log_search("Procesamiento exitoso")
            return result
        except Exception as e:
            log_error(f"Error en procesamiento: {str(e)}", exc_info=e)
            raise
"""


# ============================================================================
# RECORDATORIOS
# ============================================================================

"""
1. ERROR_ONLY: Solo log_error() - siempre se muestra
2. REQUEST_LIFECYCLE: + log_request(), log_system() - inicio/fin requests
3. MAIN_PROCESSES: + log_search(), log_embedding(), log_category_detection()
4. VERBOSE: + log_verbose(), log_color(), log_nlp(), log_cache()

Usar log_verbose() para TODO lo que antes era logger.debug() o print() condicional.
"""
