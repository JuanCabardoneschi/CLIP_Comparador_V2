# 🎨 Sistema de Aprendizaje de Colores - Plan de Implementación

## Resumen

Sistema que permite que cada cliente tenga su propia paleta de colores **aprendida automáticamente**, sin necesidad de hardcodear colores nuevos para cada cliente.

## Problema que resuelve

**Antes:**
- Colores hardcoded en `SIMILAR_COLOR_GROUPS` (global para todos)
- Si un cliente usa "fucsia eléctrico", hay que modificar código
- No escalable para 100+ clientes con paletas diferentes

**Después:**
- Cada cliente tiene su paleta aprendida en `color_mappings`
- "Fucsia eléctrico" se aprende automáticamente la primera vez que se usa
- Sistema detecta similitudes y agrupa automáticamente
- Escalable a miles de clientes sin tocar código

---

## Implementación por fases

### ✅ Fase 1: Base de datos (COMPLETADO)

**Archivos creados:**
- `app/models/color_mapping.py` - Modelo SQLAlchemy
- `migrations/2025-10-30_color_learning_system.sql` - Schema SQL
- `migrations/create_color_learning.py` - Script de migración

**Para aplicar:**
```powershell
# Opción 1: Migración con aprendizaje de colores existentes
python migrations/create_color_learning.py

# Opción 2: Solo crear tabla (sin aprender colores existentes)
psql -U postgres -d clip_comparador_v2 -f migrations/2025-10-30_color_learning_system.sql
```

**Resultado:**
- Tabla `color_mappings` creada
- Colores de productos existentes aprendidos automáticamente
- Estadísticas de grupos por cliente

---

### 🔄 Fase 2: Integración con búsqueda (EN PROGRESO)

**Objetivo:** Usar `ColorMapping` en lugar de `SIMILAR_COLOR_GROUPS` hardcoded.

#### 2.1. Modificar `colors_are_similar()`

**Archivo:** `app/utils/colors.py`

**Cambio:**
```python
def colors_are_similar(color1: str, color2: str, threshold: float = 0.85, client_id=None) -> bool:
    """
    NUEVO PARÁMETRO: client_id (opcional)

    Si client_id se proporciona:
    1. Buscar en color_mappings del cliente
    2. Si ambos colores están en el mismo similarity_group → True
    3. Fallback a SIMILAR_COLOR_GROUPS hardcoded
    4. Fallback a LLM

    Si no se proporciona client_id:
    1. Solo usa SIMILAR_COLOR_GROUPS + LLM (comportamiento actual)
    """
    # ... implementación
```

#### 2.2. Modificar búsqueda visual

**Archivo:** `app/blueprints/api.py`

**Cambio en `visual_search()`:**
```python
# Antes:
is_similar = colors_are_similar(detected_color, product_color)

# Después:
is_similar = colors_are_similar(
    detected_color,
    product_color,
    client_id=client_id  # ← NUEVO
)
```

#### 2.3. Modificar búsqueda textual

**Archivo:** `app/blueprints/api.py`

**Cambio en `_calculate_attribute_match()`:**
```python
# Antes:
if colors_are_similar(detected_color, product_color_value):
    ...

# Después:
if colors_are_similar(detected_color, product_color_value, client_id=client_id):
    ...
```

#### 2.4. Auto-aprendizaje al crear/editar productos

**Archivo:** `app/blueprints/products.py`

**Agregar en `create_product()` y `update_product()`:**
```python
from app.services.color_learning_service import ColorLearningService

# Después de guardar producto
if 'color' in product.attributes:
    ColorLearningService.process_color(
        client_id=product.client_id,
        raw_color=product.attributes['color'],
        auto_group=True
    )
```

---

### 📊 Fase 3: Panel de administración (FUTURO)

**Endpoints a crear:**

#### 3.1. Ver colores del cliente
```
GET /api/clients/{client_id}/colors

Response:
{
  "total_colors": 23,
  "total_groups": 8,
  "groups": [
    {
      "name": "AZUL",
      "colors": [
        {"raw": "azul marino", "count": 45, "normalized": "AZUL"},
        {"raw": "jean", "count": 18, "normalized": "AZUL"},
        ...
      ]
    },
    ...
  ],
  "ungrouped": [
    {
      "raw": "fucsia eléctrico",
      "count": 1,
      "normalized": "FUCSIA",
      "suggested_group": "ROSA",
      "confidence": 0.78
    }
  ],
  "suggestions": [
    {
      "colors": ["coral", "salmón"],
      "suggested_group": "NARANJA",
      "confidence": 0.87
    }
  ]
}
```

#### 3.2. Agrupar colores manualmente
```
POST /api/clients/{client_id}/colors/group
Body:
{
  "raw_colors": ["coral vibrante", "salmón", "durazno"],
  "group_name": "NARANJA"
}
```

#### 3.3. Renombrar grupo
```
PUT /api/clients/{client_id}/colors/groups/{group_name}
Body:
{
  "new_name": "ROSA_PASTEL"
}
```

**Frontend:**
- Página en `/clients/{id}/colors`
- Muestra grupos con drag-and-drop para reorganizar
- Sugerencias automáticas destacadas
- Estadísticas de uso

---

### 🚀 Fase 4: Mejoras avanzadas (OPCIONAL)

#### 4.1. Detección de colores hex
- Extraer códigos hex de imágenes con CLIP
- Guardar en `metadata.hex`
- Usar para agrupación más precisa

#### 4.2. Sugerencias proactivas
- "Detectamos que usás 'coral' (12 productos) y 'salmón' (8 productos). ¿Querés agruparlos?"
- Mostrar en dashboard del cliente

#### 4.3. Import/Export de paletas
- Exportar paleta de un cliente
- Importar en otro cliente (ej: mismo dueño, múltiples tiendas)

#### 4.4. API pública
```
GET /api/v1/colors/suggest-group?color=coral&client_id=xxx
Response:
{
  "color": "coral",
  "normalized": "CORAL",
  "suggested_group": "NARANJA",
  "similar_colors": ["salmón", "durazno", "melocotón"]
}
```

---

## Migración de clientes existentes

### Estrategia de transición

1. **Mantener `SIMILAR_COLOR_GROUPS` como fallback**
   - No eliminar el código actual
   - Si no hay datos en `color_mappings`, usar hardcoded
   - Transición gradual sin romper nada

2. **Aprender de productos existentes**
   - Script `create_color_learning.py` ya lo hace
   - Ejecutar una vez para cada base de datos

3. **Auto-población en uso normal**
   - Cada vez que se crea/edita producto → aprender color
   - En 1-2 semanas, el sistema ya tiene la paleta completa

---

## Testing

### Test 1: Aprendizaje básico
```python
# Crear producto con color nuevo
product = Product(
    client_id=client_id,
    attributes={'color': 'coral vibrante', ...}
)
db.session.add(product)
db.session.commit()

# Verificar que se aprendió
mapping = ColorMapping.query.filter_by(
    client_id=client_id,
    raw_color='coral vibrante'
).first()

assert mapping.normalized_color == 'CORAL'
assert mapping.usage_count == 1
```

### Test 2: Agrupación automática
```python
# Cliente ya tiene "salmón" → grupo "NARANJA"
# Agregar "coral" → debería detectar similitud y agrupar

ColorLearningService.process_color(
    client_id=client_id,
    raw_color='coral',
    auto_group=True
)

mapping = ColorMapping.query.filter_by(
    client_id=client_id,
    raw_color='coral'
).first()

assert mapping.similarity_group == 'NARANJA'
```

### Test 3: Búsqueda con colores aprendidos
```python
# Búsqueda visual detecta "CORAL"
# Producto tiene "salmón"
# Deben matchear porque ambos están en grupo "NARANJA"

is_similar = colors_are_similar(
    'CORAL',
    'salmón',
    client_id=client_id
)

assert is_similar == True
```

---

## Roadmap

| Fase | Tareas | Status | ETA |
|------|--------|--------|-----|
| **1** | Base de datos | ✅ Completado | - |
| **2.1** | Modificar `colors_are_similar()` | ⏳ Pendiente | 1 hora |
| **2.2** | Integrar en búsqueda visual | ⏳ Pendiente | 30 min |
| **2.3** | Integrar en búsqueda textual | ⏳ Pendiente | 30 min |
| **2.4** | Auto-aprendizaje en CRUD | ⏳ Pendiente | 1 hora |
| **3.1** | API endpoints | 📋 Planeado | 3 horas |
| **3.2** | Frontend panel | 📋 Planeado | 4 horas |
| **4** | Mejoras avanzadas | 💡 Opcional | - |

---

## Ventajas del sistema

✅ **Escalable:** Funciona con 10 o 10,000 clientes sin modificar código
✅ **Auto-adaptable:** Aprende automáticamente los colores de cada cliente
✅ **Sin mantenimiento:** No requiere updates cuando clientes agregan colores
✅ **Performante:** Colores frecuentes son instantáneos (lookup en BD)
✅ **Flexible:** Clientes pueden afinar agrupaciones manualmente
✅ **Backward compatible:** Funciona con datos existentes sin romper nada

---

## FAQ

**P: ¿Qué pasa con los colores hardcoded actuales?**
R: Se mantienen como fallback. El sistema primero busca en `color_mappings`, luego en `SIMILAR_COLOR_GROUPS`, finalmente LLM.

**P: ¿Cuándo se aprenden los colores?**
R: Automáticamente al crear/editar productos. También se pueden aprender masivamente con el script de migración.

**P: ¿Qué pasa si el LLM normaliza mal un color?**
R: El cliente puede corregirlo manualmente en el panel de administración (Fase 3).

**P: ¿Necesito ejecutar la migración en producción?**
R: Sí, pero es segura. Solo crea la tabla, no modifica datos existentes. Puedes ejecutar el script de aprendizaje después.

**P: ¿Afecta el performance?**
R: No. Lookup en `color_mappings` es una query simple con índices. Más rápido que llamar al LLM cada vez.

---

## Siguiente paso

**Ejecutar migración:**
```powershell
python migrations/create_color_learning.py
```

Esto creará la tabla y aprenderá de todos los productos existentes.
