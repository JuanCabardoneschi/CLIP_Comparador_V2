# Módulos de Búsqueda Personalizados

## 📋 Descripción

Sistema de módulos personalizados por cliente para búsqueda textual. Cada cliente tiene su propio módulo Python con lógica específica:

- ✅ Normalización de tokens adaptada al vocabulario del cliente
- ✅ Mapeo de sinónimos y variantes ortográficas
- ✅ Filtros de categoría personalizados
- ✅ Sin lógica genérica frágil

## 🗂️ Estructura

```
search_modules/
├── __init__.py                           # Registry de módulos
├── README.md                             # Esta documentación
├── search_client_eve_s_store.py         # Módulo de Eve's Store
└── search_client_{slug}.py              # Futuros módulos
```

## 🔧 Crear Módulo para Nuevo Cliente

### 1. Crear archivo `search_client_{slug}.py`

```python
"""
Módulo de Búsqueda Personalizado: {Nombre Cliente}

Cliente: {Nombre}
Slug: {slug}
Industria: {industria}
"""

from typing import List, Optional
from app.models.category import Category

# Configuración específica
VARIANTS_MAP = {
    # Mapeo de variantes y plurales
    "singular": "forma_normalizada",
    "plural": "forma_normalizada",
}

COLOR_TOKENS = {
    "rojo", "verde", "azul", # etc
}

def normalize_tokens(text: str) -> List[str]:
    """Normaliza tokens del cliente"""
    # Implementar lógica específica
    pass

def expand_query(query: str, categories: List[Category]) -> List[str]:
    """Expande query con sinónimos"""
    # Implementar lógica específica
    pass

def detect_category_filter(query_tokens: List[str], categories: List[Category]) -> Optional[List[str]]:
    """Detecta si debe filtrar por categoría"""
    # Implementar lógica específica
    pass

MODULE_INFO = {
    "client_name": "{Nombre}",
    "client_slug": "{slug}",
    "version": "1.0.0",
}
```

### 2. Registrar módulo en `app.py`

```python
# En app.py, después de crear la app:
from app.search_modules import register_client_module
import app.search_modules.search_client_{slug} as module_{slug}

register_client_module("{slug}", module_{slug})
```

## 📊 Módulos Existentes

### ✅ Eve's Store (`eve-s-store`)

**Problema resuelto:**
- "short verde" traía remeras porque "shores" no normalizaba a "short"

**Características:**
- Mapeo `shores/shore/shorts → short`
- Filtro de categoría por raíz única
- Exclusión de colores en detección
- Sinónimos específicos de ropa femenina

**Categorías:**
- shores tiro alto/bajo
- remeras manga corta/larga
- pantalones

## 🚀 Uso en Runtime

El sistema detecta automáticamente si existe módulo personalizado en el flujo visual GPT-4V:

```python
# En api.py
if has_custom_module(client_slug):
    # Usar módulo personalizado
    module = get_client_module(client_slug)
    tokens = module.normalize_tokens(query)
else:
    # Fallback genérico
    tokens = generic_normalize(query)
```

## 🧪 Testing

Para validar un módulo:

```bash
# 1. Arrancar servidor
cd clip_admin_backend
python app.py

# 2. Probar búsqueda visual unificada (terminal separada)
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/search/gpt4v-unified `
    -Method POST `
    -Headers @{ 'X-API-Key' = 'clip_xxx' } `
    -Form @{ image = Get-Item .\test-image.jpg } | ConvertTo-Json -Depth 8
```

Verificar en la respuesta:
- `"search_module": "custom"` (confirma uso del módulo)
- Categorías correctas en resultados
- Log `✅ [Módulo Custom]` en consola

## 📝 Ventajas del Sistema

1. **Mantenimiento Simple**: Un archivo = Un cliente
2. **Sin Side Effects**: Cambios en un cliente no afectan otros
3. **Debugging Fácil**: Logs claros por módulo
4. **Migración Incremental**: Clientes sin módulo usan fallback
5. **Escalabilidad**: Agregar cliente = Crear un archivo

## 🔄 Migración Futura a SaaS

Cuando se necesite generalizar:
1. Identificar patrones comunes entre módulos
2. Extraer configuración a BD (JSON fields)
3. Mantener override por módulo custom
4. Sistema híbrido: Config DB + Custom overrides
