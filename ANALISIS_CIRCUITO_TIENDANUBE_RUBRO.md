# Análisis: Captura de Rubro en Alta Automática TiendaNube

## 🔴 Problema Identificado

Cuando un cliente se da de alta automáticamente via TiendaNube, **NO se captura el rubro real de la tienda**. El sistema siempre asigna `industry='ecommerce'` (genérico), lo que impide:

1. Usar templates de atributos específicos (ej: "Talla", "Material" para moda)
2. Generar `alternative_terms` de calidad con vocabulario del rubro
3. Asociar correctamente las categorías con prompts CLIP orientados al negocio

---

## 📍 Circuito Actual

### Paso 1: OAuth Callback → Crear Cliente
**Archivo:** `clip_admin_backend/app/blueprints/tiendanube_oauth.py:108`

```python
# 4. Crear nuevo Cliente
client = Client(
    name=store_name,
    email=store_email or f'{user_id}@tiendanube.com',
    industry='ecommerce',  # ← PROBLEMA: SIEMPRE 'ecommerce', NUNCA captura el rubro real
    integration_type='tiendanube',
    is_read_only=True,
    integration_config={...}
)
```

**Qué sucede:**
- ✅ Se obtiene `store_info` desde API de Tiendanube (`get_store_info()`)
- ✅ Se extrae: nombre, email, dominio
- ❌ Se IGNORA el rubro/industria real de la tienda
- ❌ Se usa hardcode `industry='ecommerce'` (genérico)

---

### Paso 2: Sincronización de Categorías
**Archivo:** `clip_admin_backend/app/services/tiendanube_sync_service.py:191-245`

Cuando se sincroniza una categoría nueva:

```python
def _sync_category(self, cat_data: Dict):
    # ...
    client_industry = self.client.industry  # ← Aquí obtiene 'ecommerce' siempre

    # Auto-traducir nombre a inglés
    name_en = Category.auto_translate_to_english(name, client_industry)

    # Auto-generar CLIP prompt usando el rubro
    clip_prompt = Category.generate_clip_prompt(name_en)

    # Auto-generar alternative_terms (NLP del rubro)
    alternative_terms = generate_alternative_terms(name)
```

**Problema en cascada:**
1. `client_industry='ecommerce'` (genérico)
2. El prompt CLIP se genera sin orientación de rubro específico
3. El vocabulario NLP para `alternative_terms` es genérico, no optimizado para moda/electrónica/etc

---

### Paso 3: Generación de Alternative Terms (NLP)
**Archivos:**
- `clip_admin_backend/app/services/alternative_terms_generator.py`
- `clip_admin_backend/app/utils/llm_query_normalizer.py`

#### Cómo funciona:

```python
def generate_alternative_terms(category_name: str) -> Optional[str]:
    """Genera términos alternativos para una categoría usando MiniLM + semántica"""

    # 1. Usar categoría para inferir grupo (tops, bottoms, swimwear)
    group = infer_category_group(category_name)

    # 2. Obtener vocabulario base (HARDCODED por ahora)
    vocab = FASHION_VOCABULARY.get(group, [])

    # 3. Filtrar por similitud semántica
    similar = [v for v in vocab if semantic_similarity(category_name, v) > threshold]

    # 4. Generar respuesta NLP
    return generate_with_llm(category_name, similar)
```

**Observación:**
- ✅ Usa MiniLM para similitud semántica (bueno)
- ✅ Filtra por grupos de categoría (tops, bottoms, etc)
- ❌ El vocabulario base es HARDCODED y asume moda
- ❌ Si es cliente electrónica, seguiría usando vocabulario de ropa

---

### Paso 4: Vocabulario NLP Cacheado
**Archivo:** `clip_admin_backend/app/utils/llm_query_normalizer.py`

Se almacena en tabla `client_vocabulary_cache`:

```python
def get_client_vocabulary(client_id: str):
    """Lee vocabulario específico del cliente desde caché"""

    # Tabla: client_vocabulary_cache
    # Columnas: client_id, vocabulary (JSON), updated_at

    # Si no existe caché, genera desde productos del cliente
    # Si productos vacíos, usa fallback genérico
```

**Problema:**
- Si el cliente es nuevo, no hay productos aún
- El fallback es genérico
- No se inicializa con vocabulario de RUBRO al crear cliente

---

## 🎯 Solución Propuesta

### 1. Capturar rubro real de Tiendanube

Tiendanube API devuelve `store_info` con campo `category` o similar. Ejemplos:
```json
{
  "id": 123456,
  "name": {"es": "Mi Tienda de Moda"},
  "category": "fashion",  // ← AQUÍ
  "email": "admin@...",
  "main_domain": "..."
}
```

O alternativas:
- `/store` endpoint puede tener `industry` field
- `/products` puede incluir categorías raíz que infieran rubro

### 2. Mapear a `industry` del sistema

Mapping TiendaNube → CLIP Comparador:
```python
TIENDANUBE_INDUSTRY_MAPPING = {
    'moda': 'fashion',
    'fashion': 'fashion',
    'electrónica': 'electronics',
    'electronics': 'electronics',
    'automoción': 'automotive',
    'automotive': 'automotive',
    'hogar': 'home',
    'home': 'home',
    'generic': 'generic',
}
```

### 3. Extraer rubro en OAuth Callback

```python
def oauth_callback():
    # ... obtener store_info

    # ✅ NUEVO: Extraer rubro de Tiendanube
    store_category = store_info.get('category', 'generic')
    client_industry = TIENDANUBE_INDUSTRY_MAPPING.get(store_category, 'generic')

    # Crear Cliente con rubro correcto
    client = Client(
        name=store_name,
        email=store_email,
        industry=client_industry,  # ← Ahora es el rubro real
        integration_type='tiendanube',
        is_read_only=True,
        integration_config={
            'store_id': str(user_id),
            'store_domain': store_domain,
            'tiendanube_category': store_category,  # Guardar original
            'installed_at': str(db.func.now())
        }
    )
```

### 4. Inicializar vocabulary cache al crear cliente

```python
def oauth_callback():
    # ... crear cliente con industry correcto

    # ✅ NUEVO: Inicializar vocabulary cache con templates del rubro
    from app.utils.industry_templates import get_industry_template

    template = get_industry_template(client_industry)
    init_vocabulary_cache(client.id, template)
```

### 5. Usar templates de atributos por rubro

```python
def oauth_callback():
    # ... crear cliente

    # ✅ NUEVO: Crear atributos del template del rubro
    from app.utils.attribute_seeder import seed_attributes

    seed_attributes(client.id, client_industry)
```

---

## 📊 Matriz de Impacto

| Rubro | Sin Fix (genérico) | Con Fix (específico) |
|-------|-------------------|---------------------|
| **Moda** | Attributes: color, marca | Attributes: color, marca, material, talla (correcto) |
| | Alternative terms: moda + electrónica | Alternative terms: solo moda ✓ |
| | Vocab: genérico | Vocab: fashion específico ✓ |
| **Electrónica** | Attributes: color, marca | Attributes: voltaje, compatibilidad, conectores (correcto) |
| | Alternative terms: moda + electrónica | Alternative terms: solo electrónica ✓ |
| | Vocab: genérico | Vocab: electronics específico ✓ |

---

## 🔍 Cómo Verificar el Rubro en Tiendanube API

```bash
# 1. Obtener info de tienda
curl -X GET "https://api.tiendanube.com/v1/{store_id}/store" \
  -H "Authentication: bearer {access_token}"

# 2. Buscar campo "category" o similar en respuesta
# Ejemplo de respuesta:
{
  "id": 123456,
  "name": {"es": "Mi Tienda de Moda"},
  "category": "fashion",
  "country": "AR",
  "email": "admin@tienda.com",
  ...
}
```

---

## 🚀 Próximos Pasos

1. **Verificar API Tiendanube** → Confirmar si `/store` devuelve `category` field
   - Si NO → Usar `/products` para inferir (buscar categorías raíz)
   - Si SÍ → Implementar mapping directo

2. **Implementar captura de rubro** en `tiendanube_oauth.py`

3. **Crear migration** para backfill clientes TiendaNube existentes:
   ```python
   # Para cada cliente TiendaNube:
   # 1. Obtener categorías
   # 2. Inferir rubro
   # 3. Actualizar client.industry
   # 4. Reinicializar attributes y vocabulary cache
   ```

4. **Validar alternative_terms** generados con rubro correcto

5. **Test end-to-end** con tienda de cada rubro (moda, electrónica, etc)

---

## 📝 Archivos Afectados

- `clip_admin_backend/app/blueprints/tiendanube_oauth.py` (Captura rubro)
- `clip_admin_backend/app/services/tiendanube_sync_service.py` (Ya usa `client.industry`)
- `clip_admin_backend/app/utils/industry_templates.py` (Templates por rubro)
- `clip_admin_backend/app/utils/attribute_seeder.py` (Crear atributos)
- `clip_admin_backend/app/utils/llm_query_normalizer.py` (Vocabulary cache)

