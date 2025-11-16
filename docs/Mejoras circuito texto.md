# Mejoras Circuito de Búsqueda Textual - Vocabulario Dinámico por Cliente

## 🎯 Objetivo

Eliminar hardcodeos de tipos/colores en la búsqueda y reemplazarlos por **vocabulario dinámico generado por cliente** persistido en base de datos.

---

## ❌ Problema Actual (Noviembre 2025)

### Fast-path con listas hardcodeadas

En `api.py` función `_is_simple_query()`:

```python
SIMPLE_TYPES = {
    'camisa','camisas','delantal','delantales','remera','remeras','blusa','blusas',
    'pantalon','pantalones','vestido','vestidos','pollera','polleras'
}

SIMPLE_COLORS = {
    'blanco','blanca','negro','negra','rojo','roja','azul','verde','gris',
    'beige','marron','rosa','amarillo','celeste','naranja','morado','violeta'
}
```

### Consecuencias:

1. **No escalable**: Cada cliente tiene categorías distintas (ej: "short" no está → cae a full pipeline de 11s)
2. **Inconsistencia UX**: Fast-path no genera `partial_match_info` (sin banners de "color no disponible")
3. **Mantenimiento manual**: Cada vez que un cliente agrega categoría nueva, hay que actualizar código
4. **SaaS inviable**: Lista genérica que nunca cubre todos los casos

### Ejemplo del problema real:

**Cliente Eve's Store** busca `"short negro"`:
```
[SEARCH_CLASSIFY] query='short negro' -> NO SIMPLE (colors=['negro'], types=[], tokens=['short', 'negro'])
→ Cae a FULL pipeline: 11.5 segundos
```

**Cliente Goody Store** busca `"camisa roja"`:
```
[SEARCH_CLASSIFY] query='camisa roja' -> SIMPLE color=roja tipo=camisa
→ Fast-path: 0.033 segundos
→ PERO sin partial_match_info (resultados sin rojas, sin banner explicativo)
```

---

## ✅ Solución Propuesta: Vocabulario Dinámico por Cliente

### Arquitectura

#### 1. Persistencia: Campo JSONB en tabla `clients`

```sql
ALTER TABLE clients ADD COLUMN search_vocabulary JSONB;
```

**Estructura del JSON**:
```json
{
  "types": ["camisa", "short", "jean", "remera", "vestido", "delantal"],
  "colors": ["rojo", "azul", "negro", "beige", "celeste", "verde"],
  "complex_hints": ["veraniega", "playa", "elegante", "casual"],
  "generated_at": "2025-11-16T10:30:00Z",
  "categories_hash": "a3f5b2c1d4e5f6..."
}
```

**Ventajas de JSONB en `clients` vs tabla separada**:
- Sin joins adicionales (cliente ya se carga en cada request)
- Más simple de mantener
- Acceso directo vía `client.search_vocabulary`

---

#### 2. Generación Automática del Vocabulario

**Función generadora** (`app/services/vocabulary_generator.py`):

```python
def regenerate_client_vocabulary(client_id: str):
    """
    Genera vocabulario de búsqueda usando las categorías del cliente.
    Se ejecuta al crear/editar/eliminar categorías.
    """
    from app.models.category import Category
    from app.models.client import Client
    from app.models.product import Product
    import hashlib

    client = Client.query.get(client_id)
    categories = Category.query.filter_by(
        client_id=client_id,
        is_active=True
    ).all()

    # === TIPOS: Extraer de categorías ===
    types = set()
    category_names_for_hash = []

    for cat in categories:
        category_names_for_hash.append(cat.name)

        # Tokenizar nombre de categoría
        types.update(_tokenize_and_normalize(cat.name))

        # Tokenizar name_en si existe
        if cat.name_en:
            types.update(_tokenize_and_normalize(cat.name_en))

        # Tokenizar alternative_terms si existe
        if cat.alternative_terms:
            for term in cat.alternative_terms.split(','):
                types.update(_tokenize_and_normalize(term.strip()))

    # === COLORES: Combinar base + específicos del cliente ===
    BASE_COLORS = {
        'blanco','negro','rojo','azul','verde','gris','beige',
        'marron','rosa','amarillo','celeste','naranja','morado','violeta'
    }

    # Opcional: Extraer colores de productos (atributos JSONB)
    # (por ahora mantener base, optimizar después)
    colors = BASE_COLORS

    # === COMPLEX HINTS: Mantener lista base ===
    COMPLEX_HINTS = {
        'veraniega','playa','quiero','usar','tengo','llevar','evento',
        'oficina','resistente','fresco','fresca','confortable','comoda',
        'verano','bambula','elegante','casual','formal','deportiva','trabajo'
    }

    # === Hash de categorías para invalidar cache ===
    categories_hash = hashlib.md5(
        "".join(sorted(category_names_for_hash)).encode()
    ).hexdigest()

    # === Persistir ===
    vocabulary = {
        "types": sorted(list(types)),
        "colors": sorted(list(colors)),
        "complex_hints": sorted(list(COMPLEX_HINTS)),
        "generated_at": datetime.utcnow().isoformat(),
        "categories_hash": categories_hash
    }

    client.search_vocabulary = vocabulary
    db.session.commit()

    logger.info(f"✅ Vocabulario regenerado para {client.name}: {len(types)} tipos, {len(colors)} colores")
    return vocabulary


def _tokenize_and_normalize(text: str) -> set:
    """Tokeniza y normaliza texto a tokens básicos."""
    import re
    import unicodedata

    # Normalizar y remover acentos
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text.lower())
        if unicodedata.category(c) != 'Mn'
    )

    # Extraer palabras
    tokens = re.findall(r"[a-z0-9]+", text)

    # Singularizar naive (quitar 's' final si tiene >3 chars)
    normalized = set()
    for token in tokens:
        normalized.add(token)
        if len(token) > 3 and token.endswith('s'):
            normalized.add(token[:-1])

    return normalized
```

---

#### 3. Triggers de Regeneración

**Al crear/editar/eliminar categoría** (`app/blueprints/categories.py`):

```python
@bp.route("/categories", methods=["POST"])
@login_required
def create_category():
    # ... lógica de creación ...

    db.session.commit()

    # Regenerar vocabulario del cliente
    from app.services.vocabulary_generator import regenerate_client_vocabulary
    try:
        regenerate_client_vocabulary(category.client_id)
    except Exception as e:
        logger.warning(f"Error regenerando vocabulario: {e}")

    return success_response(category)


@bp.route("/categories/<id>", methods=["PUT"])
@login_required
def update_category(id):
    # ... lógica de actualización ...

    db.session.commit()

    # Regenerar vocabulario del cliente
    from app.services.vocabulary_generator import regenerate_client_vocabulary
    try:
        regenerate_client_vocabulary(category.client_id)
    except Exception as e:
        logger.warning(f"Error regenerando vocabulario: {e}")

    return success_response(category)


@bp.route("/categories/<id>", methods=["DELETE"])
@login_required
def delete_category(id):
    # ... lógica de borrado ...

    db.session.commit()

    # Regenerar vocabulario del cliente
    from app.services.vocabulary_generator import regenerate_client_vocabulary
    try:
        regenerate_client_vocabulary(category.client_id)
    except Exception as e:
        logger.warning(f"Error regenerando vocabulario: {e}")

    return success_response()
```

---

#### 4. Uso en Búsqueda (Futuro Fast-Path Mejorado)

**Nota**: Por ahora eliminamos fast-path completamente. Este código es para cuando se reimplemente con vocabulario dinámico.

```python
def _is_simple_query(q: str, client_id: str = None):
    """Clasifica query usando vocabulario dinámico del cliente."""

    # === Vocabulario base (fallback) ===
    BASE_COLORS = {'negro','blanco','rojo','azul','verde','gris'}
    BASE_TYPES = {'camisa','pantalon','remera','vestido'}
    BASE_HINTS = {'veraniega','playa','elegante','casual'}

    # === Cargar vocabulario del cliente ===
    if client_id:
        client = Client.query.get(client_id)
        if client and client.search_vocabulary:
            vocab = client.search_vocabulary
            SIMPLE_COLORS = set(vocab.get('colors', [])) | BASE_COLORS
            SIMPLE_TYPES = set(vocab.get('types', [])) | BASE_TYPES
            COMPLEX_HINTS = set(vocab.get('complex_hints', [])) | BASE_HINTS
        else:
            # Cliente sin vocabulario → usar base
            SIMPLE_COLORS = BASE_COLORS
            SIMPLE_TYPES = BASE_TYPES
            COMPLEX_HINTS = BASE_HINTS
    else:
        SIMPLE_COLORS = BASE_COLORS
        SIMPLE_TYPES = BASE_TYPES
        COMPLEX_HINTS = BASE_HINTS

    # ... resto de lógica de clasificación (sin cambios) ...
```

---

## 🚀 Plan de Implementación

### Fase 0: Simplificación (ACTUAL - Noviembre 2025)

**Acción**: Eliminar fast-path completamente
- Remover función `_is_simple_query()`
- Remover todas las listas hardcodeadas (`SIMPLE_TYPES`, `SIMPLE_COLORS`, etc.)
- Dejar solo el pipeline FULL con LLM + `partial_match_info`

**Razón**:
- Fast-path con hardcodeos no es aceptable para SaaS
- Mejor un solo circuito consistente (aunque más lento) que dos inconsistentes
- UX predecible: siempre con banners informativos

**Resultado**:
- Todas las búsquedas: 6-12 segundos
- Pero SIEMPRE con `partial_match_info` cuando aplica
- Sin sorpresas ni hardcodeos

---

### Fase 1: Vocabulario Dinámico (FUTURO - Prioridad ALTA)

**Duración estimada**: 4-6 horas

**Tareas**:
1. ✅ Migración BD: Agregar columna `search_vocabulary` JSONB a `clients`
2. ✅ Crear `app/services/vocabulary_generator.py`
3. ✅ Script de población inicial: Generar vocabulario para todos los clientes existentes
4. ✅ Integrar triggers en endpoints de categorías (create/update/delete)
5. ✅ Testing: Verificar regeneración automática

**Resultado**:
- Cada cliente tiene su vocabulario específico en BD
- Se actualiza automáticamente al modificar categorías
- Sin hardcodeos en código

---

### Fase 2: Reimplementar Fast-Path Mejorado (FUTURO - Prioridad MEDIA)

**Duración estimada**: 3-4 horas

**Requisito**: Fase 1 completada

**Tareas**:
1. ✅ Reimplementar `_is_simple_query()` usando vocabulario de BD
2. ✅ Agregar generación de `partial_match_info` en fast-path
3. ✅ Implementar fallback estricto: fast solo si tiene match exact/near
4. ✅ Testing exhaustivo: Verificar consistencia UX entre fast y full

**Resultado**:
- Fast-path funciona para TODOS los clientes (sin hardcodeos)
- Siempre genera `partial_match_info` cuando no hay exact/near match
- Fallback automático a full cuando fast no puede garantizar calidad
- Performance óptima: 0.03s cuando hay match, 8s cuando no

---

### Fase 3: Optimizaciones (FUTURO - Prioridad BAJA)

**Duración estimada**: 2-3 horas

**Tareas**:
1. ✅ Extraer colores desde productos (scan de JSONB attributes)
2. ✅ Cache en memoria de vocabularios (opcional, solo si hay cuello de botella)
3. ✅ Background job para mantener vocabularios actualizados
4. ✅ (Opcional) Enriquecer vocabulario con LLM para sinónimos

---

## 📊 Comparativa de Soluciones

| Aspecto | Fast-path Hardcoded (Actual) | Solo Full (Fase 0) | Vocabulario Dinámico (Fase 1+2) |
|---------|------------------------------|--------------------|---------------------------------|
| **Escalabilidad** | ❌ No escala | ✅ Universal | ✅✅ Se adapta por cliente |
| **Mantenimiento** | ❌ Código a editar | ✅ Cero | ✅✅ Auto-mantenimiento |
| **Performance** | ⚡ 0.03s (cuando aplica) | 🐌 8-12s siempre | ⚡ 0.03s (cuando aplica) |
| **Precisión** | ⚠️ Lista genérica | ✅ LLM completo | ✅✅ Específica + LLM |
| **UX Consistencia** | ❌ Sin banners en fast | ✅✅ Siempre con banners | ✅✅ Siempre con banners |
| **Setup inicial** | ✅ Ya funciona | ✅ Ya funciona | ⚠️ Migración una vez |
| **Complejidad** | ⚠️ Hardcodeos | ✅ Simple | ⚠️ Más componentes |

---

## 🎯 Recomendaciones

### Inmediato (Hoy):
- ✅ **Eliminar fast-path**: Dejar solo pipeline full
- ✅ **Documentar propuesta**: Este archivo

### Corto plazo (1-2 semanas):
- 🔄 **Implementar Fase 1**: Vocabulario dinámico en BD
- 🔄 **Script de migración**: Poblar vocabularios de clientes existentes

### Mediano plazo (3-4 semanas):
- 📅 **Implementar Fase 2**: Reimplementar fast-path mejorado
- 📅 **Testing exhaustivo**: Verificar consistencia UX

### Largo plazo (opcional):
- 💡 **Fase 3**: Optimizaciones y enriquecimiento con LLM

---

## 🔧 Scripts de Migración

### Script 1: Crear columna en BD

```sql
-- Ejecutar en Railway DB
ALTER TABLE clients ADD COLUMN IF NOT EXISTS search_vocabulary JSONB;
```

### Script 2: Poblar vocabularios iniciales

```python
# populate_vocabularies.py
"""
Script para generar vocabulario inicial de todos los clientes.
Ejecutar UNA VEZ después de agregar la columna.
"""

from app import create_app, db
from app.models.client import Client
from app.services.vocabulary_generator import regenerate_client_vocabulary

def main():
    app = create_app()
    with app.app_context():
        clients = Client.query.filter_by(is_active=True).all()
        print(f"📊 Generando vocabularios para {len(clients)} clientes...")

        for client in clients:
            try:
                vocab = regenerate_client_vocabulary(client.id)
                print(f"✅ {client.name}: {len(vocab['types'])} tipos")
            except Exception as e:
                print(f"❌ {client.name}: ERROR {e}")

        print("✅ Proceso completado")

if __name__ == "__main__":
    main()
```

---

## 📝 Notas Técnicas

### Performance del vocabulario en BD:
- JSONB es eficiente en PostgreSQL
- Cliente ya se carga en cada request (no hay overhead)
- Acceso: `client.search_vocabulary['types']` es O(1)

### Invalidación de cache:
- `categories_hash` permite detectar cambios
- Si hash cambió → regenerar vocabulario
- Background job opcional para mantener sincronizado

### Fallbacks robustos:
1. Si cliente no tiene vocabulario → usar base
2. Si vocabulario está vacío → usar base
3. Combinar siempre base + específico del cliente (union)

---

## 🔗 Referencias

- Issue original: Logs de Railway muestran "short negro" → full (11s) vs "camisa roja" → fast (0.03s)
- Análisis completo: Chat del 15-16 Nov 2025
- Código afectado: `clip_admin_backend/app/blueprints/api.py` líneas 2408-2500 (función `_is_simple_query`)

---

**Fecha**: 16 de Noviembre, 2025
**Estado**: Propuesta documentada - Fase 0 en progreso
**Próximo paso**: Eliminar fast-path y dejar solo pipeline full
