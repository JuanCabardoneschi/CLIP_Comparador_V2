# Sistema de Perfiles de Búsqueda por Industria

## Descripción

Reemplazo escalable del sistema de módulos personalizados por cliente. Permite definir y gestionar reglas de búsqueda (normalización, sinónimos, detección de categorías) por **industria** en lugar de por cliente individual.

**Objetivo:** Soportar cientos de clientes TiendaNube sin escribir código personalizado por cada uno.

---

## Arquitectura

### Componentes

1. **SearchProfilesService** (`app/services/search_profiles_service.py`)
   - Carga perfiles predefinidos por industria
   - Soporta overrides por cliente (almacenados en `Client.integration_config.search_rules`)
   - Caché con Redis (TTL 1 hora)
   - Métodos: `normalize_tokens()`, `expand_query()`, `detect_category_filter()`

2. **Admin UI** (`app/blueprints/search_profiles_admin.py` + templates)
   - Vista de lista de clientes y sus perfiles
   - Editor de reglas (variantes, sinónimos, colores, estrategia)
   - Preview de búsqueda en tiempo real
   - Reset a valores base

3. **Integración en Pipeline** (`app/blueprints/search_text.py`)
   - Usa `SearchProfilesService` por defecto en Stage 1 (detección de categoría y expansión)
   - Fallback a módulos custom (Eve/Demo) si existen
   - Fallback genérico como último recurso

4. **Auto-inicialización** (`app/services/tiendanube_sync_service.py`)
   - Al sincronizar una tienda TiendaNube, infiere `industry='fashion'` si ≥3 categorías coinciden con vocabulario de moda
   - Carga y cachea el perfil `fashion` automáticamente

---

## Perfiles Predefinidos

### Fashion (Moda)
- **Variantes:** shores→short, remeras→remera, pantalones→pantalon, etc.
- **Sinónimos:** remera↔camiseta↔polera, jean↔pantalón, etc.
- **Estrategia:** `root-unique` (filtra solo si un único término de categoría detectado)
- **Colores:** rojo, azul, verde, negro, blanco, etc. (se excluyen de detección)

### Uniforms (Uniformes)
- **Variantes:** delantales↔mandiles, ambos↔uniformes, chaqueta↔casaca, etc.
- **Sinónimos:** delantal↔mandil, etc.
- **Estrategia:** `root-unique`

### Generic (Genérico)
- Variantes y sinónimos vacíos (heredan de `alternative_terms` de BD)
- Estrategia: `broad` (menos restrictivo)

---

## Uso

### Como Admin: Listar y editar perfiles

```bash
GET  /search-profiles-admin/profiles              # Listar clientes
GET  /search-profiles-admin/client/<id>/edit      # Editar perfil
POST /search-profiles-admin/client/<id>/edit      # Guardar cambios
POST /search-profiles-admin/client/<id>/preview   # Preview de query
POST /search-profiles-admin/client/<id>/reset-overrides  # Reset
```

### Como Desarrollador: Usar el servicio

```python
from app.services.search_profiles_service import SearchProfilesService

# Obtener perfil (con caché)
profile = SearchProfilesService.get_profile(client_id, client_industry='fashion')

# Normalizar tokens
tokens = SearchProfilesService.normalize_tokens("short rojo", profile)
# → ["short", "rojo"]

# Expandir query con sinónimos
expanded = SearchProfilesService.expand_query("remera azul", categories, profile)
# → ["remera", "azul", "camiseta", "polera", "top", ...]

# Detectar categoría para filtrado
cat_ids, metadata = SearchProfilesService.detect_category_filter(tokens, categories, profile)
# Si "root-unique" y solo "short" detectado: retorna IDs de categorías con "short"
# Si múltiples raíces: retorna None (búsqueda amplia)
```

### Agregar override por cliente

```python
overrides = {
    "variants_map": {"bermuda": "bermuda"},  # Agregar variante
    "category_synonyms": {"bermuda": ["bermudas"]},  # Agregar sinónimo
    "filter_strategy": "root-unique"  # O cambiar a "broad"
}
SearchProfilesService.save_client_overrides(client_id, overrides)
```

---

## Flujo de Búsqueda Textual (Nueva)

1. **Ingestión:** Query "short rojo" en cliente fashion
2. **Obtener perfil:** `fashion` (industria detectada/inferida)
3. **Normalizar:** "short rojo" → ["short", "rojo"]
4. **Expandir:** ["short", "rojo"] + sinónimos → ["short", "rojo", "shore", "shores"]
5. **Detectar categoría:** Filtrar por "short" (si estrategia es `root-unique`)
6. **Stage 1 (SQL):** Query `SIMILAR TO` con términos expandidos en categoría filtrada
7. **Stage 2 (CLIP):** Reranking por similitud visual
8. **Respuesta:** Productos ordenados por relevancia

---

## Compatibilidad con Módulos Custom

Los módulos Eve y Demo siguen siendo soportados como fallback:

1. Primero intenta usar el perfil por industria (prioritario)
2. Si falla, intenta módulo custom (Eve/Demo)
3. Si no existe, usa fallback genérico

Esto permite una migración gradual sin romper código existente.

---

## Migración desde Módulos Custom

### Paso 1: Definir perfil base
Analizar un módulo custom (ej: Eve) y extraer:
- `variants_map` → perfil['variants_map']
- `category_synonyms` → perfil['category_synonyms']
- `color_tokens` → perfil['color_tokens']
- `filter_strategy` → perfil['filter_strategy']

### Paso 2: Crear perfil en `DEFAULT_PROFILES`
```python
DEFAULT_PROFILES["custom_rubro"] = {
    "name": "Mi Rubro",
    "description": "Descripción",
    "variants_map": {...},
    "category_synonyms": {...},
    ...
}
```

### Paso 3: Asignar industria a cliente
```python
client.industry = "custom_rubro"
db.session.commit()
```

### Paso 4: Verificar en /search-profiles-admin
El cliente debe listar con el nuevo perfil.

---

## Testing

### Test Unitario (sin BD)
```bash
cd clip_admin_backend
python test_profiles_unit.py
```

### Test Integrado (con BD)
1. Iniciar servidor: `python app.py`
2. Navegar a `/search-profiles-admin/profiles`
3. Seleccionar un cliente
4. Usar el campo "Preview de Búsqueda" para probar queries

---

## Performance

- **Caché:** Perfil cacheado en Redis (TTL 1h) por cliente_id
- **Invalidación:** Al guardar overrides, se limpia el caché
- **Lookup:** O(1) en memoria (dict lookups para variants_map, category_synonyms)
- **Normalización:** ~5ms para típico query de 3-5 palabras

---

## Roadmap

- [ ] UI para editar diccionarios por industria (no solo por cliente)
- [ ] Telemetría: Registrar queries sin resultados y términos sin configurar
- [ ] Machine learning: Auto-generar variantes/sinónimos desde logs
- [ ] Multi-idioma: Perfiles en EN/ES/PT
- [ ] Sincronización con Tiendanube de cambios en `name_en` (feedback loop)

---

## FAQ

**P: ¿Qué pasa si un cliente de moda necesita una variante custom?**
R: Guardar override en `Client.integration_config.search_rules.variants_map`. No requiere código.

**P: ¿Se pueden cambiar perfiles sin redeploy?**
R: Sí, via UI admin. Los cambios se guardan en BD inmediatamente.

**P: ¿Eve y Demo dejan de funcionar?**
R: No, siguen soportados como fallback. Pero se recomienda migrar a perfiles.

**P: ¿Cómo acelerar la migración de múltiples clientes?**
R: Script en batch para actualizar `client.industry` basado en catálogo existente.

---

## Contacto / Issues

Para problemas o mejoras, abrir issue en GitHub.
