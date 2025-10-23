# BACKLOG DE MEJORAS Y PENDIENTES
**Fecha de Creación**: 22 Octubre 2025
**Última Actualización**: 23 Octubre 2025

---

## 🔥 URGENTE - FASE 5 (Sistema en Producción)

### 1. Admin Panel de Atributos
**Estado**: ⏳ Pendiente
**Complejidad**: Media
**Impacto**: Alto (actualmente se editan a mano en BD)
**Fecha agregada**: 23 Octubre 2025

**Problema**:
- Los atributos (color, marca, talla, etc.) se crean desde el formulario de productos
- `expose_in_search` queda en `false` por defecto → atributos NO aparecen en API
- No hay forma de gestionar atributos centralizadamente
- Cambiar `expose_in_search` requiere UPDATE manual en BD

**Solución Necesaria**:
1. **Blueprint `/attributes/`** con vistas:
   - `GET /attributes/` → Lista todos los atributos del cliente
   - `GET /attributes/create` → Formulario crear atributo
   - `POST /attributes/create` → Guardar nuevo atributo
   - `GET /attributes/edit/<key>` → Formulario editar
   - `POST /attributes/edit/<key>` → Guardar cambios
   - `POST /attributes/delete/<key>` → Eliminar atributo

2. **Formulario debe incluir**:
   - Key (identificador único)
   - Label (nombre visible)
   - Type (text, select, list, url, etc.)
   - ☑️ **Expose in Search** (default: `True`) ← CRÍTICO
   - Description (opcional)
   - Options (para select/list)

3. **Cambiar default en modelo**:
   ```python
   # En ProductAttributeConfig
   expose_in_search = Column(Boolean, default=True, nullable=False)  # Cambiar a True
   ```

4. **Migración para datos existentes**:
   ```sql
   UPDATE product_attribute_config
   SET expose_in_search = true
   WHERE key IN ('color', 'marca', 'talla', 'material');
   ```

**Archivos a crear/modificar**:
- Nuevo: `app/blueprints/attributes.py`
- Nuevo: `app/templates/attributes/index.html`
- Nuevo: `app/templates/attributes/form.html`
- Modificar: `app/models/product_attribute_config.py` (default=True)
- Migración: `migrations/versions/xxx_set_expose_default_true.py`

**Estimación**: 2-3 días

---

## 🎯 PRIORIDAD ALTA

### 1. Sistema de Aprendizaje Adaptativo por Cliente
**Estado**: 💡 Propuesto
**Complejidad**: Alta
**Impacto**: Crítico para calidad de resultados

**Problema Identificado**:
- Sistema actual prioriza similitud visual/compositiva sobre contenido semántico
- Ejemplo: Imagen de león matchea mejor con remera verde (sin león) que con remera del Rey León
- Cada cliente/tienda necesita ponderaciones diferentes según su catálogo

**Solución Propuesta - Opción 1 (MVP Rápido)**:
- Tabla `client_search_config` con 2 pesos configurables:
  - `semantic_weight`: Peso del contenido semántico (0.0-1.0)
  - `visual_weight`: Peso de composición visual (0.0-1.0)
- Interface en admin con sliders para ajustar manualmente
- Modificar función de similitud para usar pesos ponderados
- Valores default: semantic=0.6, visual=0.4

**Solución Propuesta - Opción 2 (Sistema Completo)**:
- Embeddings descomponibles: semantic, visual, color, style
- Sistema de feedback implícito (clicks, conversiones) y explícito (thumbs up/down)
- Algoritmo de optimización automática que ajusta pesos basándose en feedback
- A/B testing framework
- Dashboard de métricas de calidad

**Archivos a Modificar**:
- Nuevo: `app/models/client_search_config.py`
- Modificar: `app/blueprints/api.py` (función de similitud)
- Modificar: `app/blueprints/embeddings.py` (generación de embeddings múltiples)
- Nuevo: `app/blueprints/search_optimization.py` (admin interface)
- Nuevo tabla DB: `client_search_weights`
- Opcional: `search_feedback_log` para tracking

**Estimación**: 2-4 semanas (MVP) / 6-8 semanas (completo)

### 2. Validación Zero‑Shot Dinámica contra Catálogo (CLIP sin hardcode)
**Estado**: 💡 Propuesto (Alta prioridad)
**Complejidad**: Media
**Impacto**: Alto (reduce falsos positivos como "pantalón" en tienda que vende "remeras")

**Idea**:
- Usar CLIP en modo open‑vocabulary (zero‑shot) para describir la imagen sin forzar categorías.
- Generar términos dinámicos del catálogo del cliente: nombres/aliases de categorías, nombres de productos, tags y keywords de descripciones.
- Construir prompts a partir de esos términos y validar si la imagen matchea algún término del catálogo por encima de un umbral configurable por cliente.

**Contrato mínimo**:
- Input: imagen subida por el widget; client_id.
- Proceso: `get_client_searchable_terms(client) → prompts → similitud CLIP`.
- Output: `matches_catalog: bool`, `best_term`, `similarity`.
- Umbral: `catalog_match_threshold` en tabla/config del cliente.

**Criterios de aceptación**:
- Si la imagen no corresponde al catálogo, el endpoint devuelve 400 con error `content_not_in_catalog` y lista de familias que sí comercializa.
- Si corresponde, continúa el flujo normal (detección de categoría + ranking de productos).
- Sin hardcode de categorías globales; todo surge del catálogo del cliente.

**Dependencias**:
- Posible cache de embeddings de términos por cliente (Redis, TTL 24h).

**Estimación**: 1 semana (incluye prueba A/B en 1 cliente)

---

### 3. Búsqueda Híbrida Texto + Imagen (hints en la búsqueda)
**Estado**: 💡 Propuesto (Alta prioridad)
**Complejidad**: Media
**Impacto**: Alto (permite guiar la intención: "con león", "sin estampado", "color verde")

**Idea**:
- El widget permite un campo de texto opcional (hints) junto a la imagen.
- Se genera un embedding híbrido combinando `image_embedding` + `text_embedding` de CLIP con pesos configurables por cliente.

**Contrato**:
- Input: `image`, `query_text` (opcional), `client_id`.
- Proceso: `hybrid = α*image + (1-α)*text` (α configurable, ej. 0.7).
- Output: ranking de productos usando el embedding híbrido.

**Criterios de aceptación**:
- Si `query_text` está vacío, comportamiento actual (solo imagen).
- Con `query_text`, los resultados reflejan restricciones/señas del texto (ej.: prioriza "león" o "verde").
- Nuevo parámetro en API: `query_text` (opcional) y soporte en widget.

**Dependencias**:
- Posible reuso de `client_search_config` para peso α del híbrido.

**Estimación**: 1 semana (MVP)

---

## 🔧 PENDIENTES TÉCNICOS

### 1. Migrar Templates de Atributos por Industria a Base de Datos
**Estado**: 📋 Backlog (Fase 2)
**Complejidad**: Media
**Impacto**: Alto para escalabilidad
**Relacionado con**: Sistema de atributos dinámicos + SearchOptimizer metadata scoring

**Contexto**:
- Actualmente los templates de atributos por industria están hardcoded en `app/utils/industry_templates.py`
- Funcionan bien para MVP pero limitan la flexibilidad de super_admin
- Cada industria (fashion, automotive, home, electronics, generic) tiene atributos diferentes con pesos de optimizer específicos

**Problema Actual**:
- Agregar nueva industria requiere modificar código y redesplegar
- Super admin no puede editar templates desde UI
- No hay historial de cambios en templates (solo Git)
- Testing requiere modificar diccionario Python

**Solución Propuesta**:
```sql
CREATE TABLE attribute_templates (
   id SERIAL PRIMARY KEY,
   industry VARCHAR(100) NOT NULL,     -- 'fashion', 'automotive', etc.
   key VARCHAR(100) NOT NULL,          -- 'color', 'marca', etc.
   label VARCHAR(200) NOT NULL,
   type VARCHAR(20) NOT NULL,          -- 'text', 'list', etc.
   is_system BOOLEAN DEFAULT TRUE,
   is_deletable BOOLEAN DEFAULT FALSE,
   optimizer_weight FLOAT,             -- Peso en SearchOptimizer
   description TEXT,
   options JSON,
   field_order INT DEFAULT 0,
   expose_in_search BOOLEAN DEFAULT TRUE,
   required BOOLEAN DEFAULT FALSE,
   created_at TIMESTAMP DEFAULT NOW(),
   updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_attr_templates_industry_key
ON attribute_templates(industry, key);
```

**Cambios Requeridos**:
1. **Migración Alembic**: Crear tabla `attribute_templates`
2. **Seed Script**: `python scripts/migrate_templates_to_db.py`
  - Lee `INDUSTRY_TEMPLATES` de `industry_templates.py`
  - Inserta todos los templates en BD
  - Verifica integridad de datos
3. **Modelo SQLAlchemy**: `app/models/attribute_template.py`
4. **Blueprint Admin**: `app/blueprints/attribute_templates.py`
  - CRUD para templates (solo super_admin)
  - UI para agregar/editar industrias
  - Validación de cambios (no romper configs existentes)
5. **Actualizar `seed_industry_attributes()`**:
  - Cambiar de leer dict a query DB
  ```python
  templates = AttributeTemplate.query.filter_by(industry=industry).all()
  ```

**Beneficios**:
- ✅ Super admin puede crear nuevas industrias desde UI
- ✅ Editar templates sin redesplegar
- ✅ Historial en DB con timestamps
- ✅ Testing más robusto (seed test DB)
- ✅ Multi-tenant escalable (diferentes templates por región?)

**Riesgos**:
- ⚠️ Migración de datos existentes (clientes con templates hardcoded)
- ⚠️ Validación compleja (cambios en templates no deben romper productos existentes)
- ⚠️ Caché necesario para performance (Redis?)

**Estimación**: 1-2 semanas
**Prioridad**: Baja (MVP funciona con hardcoded), Alta para multi-cliente/regiones

---

### 2. Eliminar Métodos Deprecados de Image Managers
**Estado**: ⏳ Programado para 10 Nov 2025
**Complejidad**: Baja
**Impacto**: Medio (limpieza de código)

**Tareas**:
- [ ] Verificar que no hay nuevos usos de `image_manager.get_image_url()`
- [ ] Verificar que no hay nuevos usos de `cloudinary_manager.get_image_url()`
- [ ] Confirmar que todo usa `image.display_url` / `image.thumbnail_url`
- [ ] Eliminar métodos deprecados de `app/services/image_manager.py`
- [ ] Eliminar métodos deprecados de `app/services/cloudinary_manager.py`
- [ ] Actualizar tests si existen

**Deadline**: 10 Noviembre 2025
**Estimación**: 2 horas

---

### 3. Fix Duplicación de Paths en Cloudinary
**Estado**: ✅ Código modificado, pendiente de deploy
**Complejidad**: Baja
**Impacto**: Medio (organización)

**Problema**:
- Estructura actual: `clip_v2/eve-s-store/products/eve-s-store/products/...` (duplicado)
- Estructura deseada: `clip_v2/eve-s-store/products/{product_id}/...`

**Solución Implementada**:
- Modificado `cloudinary_manager._generate_public_id()` para retornar solo path relativo
- Cambio de: `f"clip_v2/{client_slug}/{product_id}/..."`
- A: `f"products/{product_id}/..."`

**Archivos Modificados**:
- `clip_admin_backend/app/services/cloudinary_manager.py`

**Pendiente**:
- [ ] Commit y push
- [ ] Deploy a Railway
- [ ] Verificar que nuevas subidas usan estructura correcta
- [ ] Opcional: Script de migración para reorganizar imágenes existentes

**Estimación**: 30 minutos (deploy + verificación)

---

### 4. Implementar SearchLog para Analytics
**Estado**: 🚧 Modelo creado, sin uso
**Complejidad**: Media
**Impacto**: Alto (métricas de negocio)

**Problema**:
- Modelo `SearchLog` existe pero no se está usando
- No hay tracking de búsquedas, clicks, conversiones
- Imposible medir calidad de resultados o ROI

**Tareas**:
- [ ] Activar logging en endpoint `/api/search`
- [ ] Guardar: client_id, image_hash, query_embedding, results, timestamp
- [ ] Implementar endpoint para tracking de clicks: `/api/search/click`
- [ ] Implementar endpoint para tracking de conversiones: `/api/search/convert`
- [ ] Dashboard en admin para ver métricas:
  - Búsquedas por día/semana
  - CTR (click-through rate)
  - Conversion rate
  - Productos más clickeados desde búsqueda
  - Búsquedas sin clicks (0 relevancia)

**Archivos a Crear/Modificar**:
- Modificar: `app/blueprints/api.py` (agregar logging)
- Nuevo: `app/blueprints/search_analytics.py`
- Modificar: Widget JS para enviar eventos de click/conversión

**Estimación**: 1 semana

---

## 🎨 MEJORAS DE UX/UI

### 5. Panel de "Entrenamiento" de Búsqueda (Admin)
**Estado**: 💡 Propuesto
**Complejidad**: Media
**Impacto**: Alto (relacionado con item #1)

**Funcionalidad Propuesta**:

**5.1. Modo Comparación**:
- Upload imagen de prueba desde admin
- Sistema muestra top 10 resultados actuales
- Admin puede arrastrar para reordenar como "debería ser"
- Sistema aprende preferencias y ajusta pesos

**5.2. Galería de Validación**:
- Muestra búsquedas reales de usuarios
- Admin valida con ✓ (buenos) / ✗ (malos)
- Acumula feedback para optimización automática

**5.3. Configuración Manual**:
- Sliders visuales para ajustar pesos:
  ```
  Prioridad en búsquedas:
  Contenido semántico (qué es):  ████████░░ 80%
  Apariencia visual (cómo se ve): ███░░░░░░░ 30%
  Color predominante:             █████░░░░░ 50%
  ```

**5.4. A/B Testing Automático**:
- Sistema prueba configuraciones alternativas
- Mide CTR y conversión
- Recomienda mejor config

**Dependencia**: Requiere implementar primero items #1 y #4

**Estimación**: 2 semanas (después de #1 y #4)

---

## 📊 MEJORAS DE DATOS

### 6. Enriquecer Metadata de Productos
**Estado**: 💡 Propuesto
**Complejidad**: Baja (técnica) / Alta (operativa - requiere trabajo manual)
**Impacto**: Alto para calidad de búsqueda

**Problema**:
- Productos tienen metadata mínima (nombre, SKU, precio)
- Sin tags semánticos: "león", "animal", "personaje"
- Sin descripciones detalladas para CLIP

**Soluciones**:

**6.1. Auto-Tagging con CLIP** (corto plazo):
- Usar CLIP para detectar objetos/conceptos en imágenes
- Generar tags automáticos: "animal", "león", "ropa deportiva", etc.
- Guardar en campo `auto_tags` (JSONB)
- Usar tags en generación de embeddings contextuales

**6.2. Interface de Tagging Manual** (mediano plazo):
- Campo "Tags" en formulario de producto
- Autocompletado de tags comunes
- Sugerencias basadas en detección automática

**6.3. Descripción Estructurada** (largo plazo):
- Template de descripción con campos específicos:
  - Tipo de prenda
  - Estilo (casual, formal, deportivo)
  - Elementos visuales (estampado, liso, rayas)
  - Temática/personajes (si aplica)
  - Público objetivo

**Archivos a Modificar**:
- `app/models/product.py` (agregar campo auto_tags)
- `app/blueprints/products.py` (form con tags)
- `app/blueprints/embeddings.py` (usar tags en contexto)
- Nueva función: `generate_auto_tags_with_clip()`

**Estimación**: 1 semana (auto-tagging) + 1 semana (UI manual)

---

## 🔐 SEGURIDAD Y PERFORMANCE

### 7. Rate Limiting Granular por Cliente
**Estado**: ⚠️ Básico implementado, mejorable
**Complejidad**: Media
**Impacto**: Medio

**Mejoras Propuestas**:
- Rate limiting diferenciado por plan (Free/Pro/Enterprise)
- Rate limiting por endpoint (search vs upload vs admin)
- Dashboard de uso en tiempo real
- Alertas cuando cliente se acerca al límite
- Upgrade automático de plan

**Estimación**: 1 semana

---

### 8. Caching de Embeddings de Búsqueda
**Estado**: 💡 Propuesto
**Complejidad**: Baja
**Impacto**: Medio (performance)

**Problema**:
- Cada búsqueda genera embedding desde cero
- Si dos usuarios buscan misma imagen → cálculo duplicado

**Solución**:
- Cache en Redis con key = hash de imagen
- TTL de 1 hora
- Invalidar si se actualizan pesos del cliente

**Estimación**: 2-3 días

---

## 🧪 TESTING Y CALIDAD

### 9. Suite de Tests
**Estado**: ❌ No existe
**Complejidad**: Alta
**Impacto**: Alto (calidad y confianza)

**Tests Prioritarios**:
- Unit tests para funciones de similitud
- Integration tests para pipeline de embeddings
- E2E tests para widget de búsqueda
- Tests de regresión para casos conocidos (león vs no-león)

**Estimación**: 2 semanas

---

### 10. Monitoring y Alertas
**Estado**: ⚠️ Logs básicos
**Complejidad**: Media
**Impacto**: Alto (operaciones)

**Mejoras**:
- Dashboard de salud del sistema
- Alertas por Slack/Email:
  - Errores en generación de embeddings
  - Búsquedas fallidas (400/500)
  - Alta latencia en API
  - Cliente excediendo rate limit
- Métricas en Railway dashboard

**Estimación**: 1 semana

---

## 📝 DOCUMENTACIÓN

### 11. Documentación de API Externa
**Estado**: ❌ Falta
**Complejidad**: Baja
**Impacto**: Alto (para clientes/integradores)

**Contenido Necesario**:
- Swagger/OpenAPI spec para `/api/search`
- Ejemplos de integración (JS, Python, cURL)
- Guía de troubleshooting
- Changelog de versiones

**Estimación**: 3 días

---

## 🚀 FEATURES NUEVAS

### 12. Búsqueda por Texto + Imagen Híbrida
**Estado**: 💡 Idea
**Complejidad**: Media
**Impacto**: Alto

**Descripción**:
- Usuario puede combinar texto + imagen: "remera roja de león"
- Sistema genera embedding híbrido CLIP text+image
- Resultados más precisos

**Estimación**: 1 semana

---

### 13. Búsqueda por Región de Interés (ROI)
**Estado**: 💡 Idea
**Complejidad**: Alta
**Impacto**: Medio

**Descripción**:
- Usuario dibuja recuadro en imagen para enfocarse en región específica
- Sistema genera embedding solo de esa región
- Útil para imágenes con múltiples objetos

**Estimación**: 2 semanas

---

### 14. Recomendaciones "También te puede interesar"
**Estado**: 💡 Idea
**Complejidad**: Baja
**Impacto**: Alto (ventas)

**Descripción**:
- Dado un producto, encontrar N productos similares
- Usar embeddings existentes
- Widget embebible para página de producto

**Estimación**: 1 semana

---

## 📋 RESUMEN DE PRIORIZACIÓN

### Sprint 1 (2 semanas)
1. 🧠 Validación Zero‑Shot Dinámica contra Catálogo (#2 Prioridad Alta)
2. 📝 Búsqueda Híbrida Texto + Imagen (MVP) (#3 Prioridad Alta)
3. ✅ Fix Cloudinary paths (30min)
4. 🔧 Eliminar métodos deprecados (#2 Pendientes Técnicos)

### Sprint 2 (2 semanas)
5. 🎯 MVP Sistema de Ponderación Adaptativa (#1 opción 1)
6. 📊 Implementar SearchLog y analytics básicas (#4)

### Sprint 3 (2 semanas)
6. 🎨 Panel de entrenamiento - Modo Comparación (#5.1)
7. 🎨 Interface de tagging manual (#6.2)

### Sprint 4 (2 semanas)
8. 🧪 Suite de tests básica (#9)
9. 🔐 Caching de embeddings (#8)

### Backlog (priorizar según feedback de clientes)
- Sistema completo de ponderación multi-factor (#1 opción 2)
- Panel completo de entrenamiento (#5 completo)
- Rate limiting granular (#7)
- Monitoring avanzado (#10)
- Documentación API (#11)
- Features nuevas (#12, #13, #14)

---

## 🔄 CHANGELOG

**22 Oct 2025**:
- Documento creado
- Agregado item #1: Sistema de Aprendizaje Adaptativo (prioridad alta)
- Agregado item #2: Validación Zero‑Shot Dinámica contra Catálogo (prioridad alta)
- Agregado item #3: Búsqueda Híbrida Texto + Imagen (prioridad alta)
- Agregado item #3: Fix duplicación Cloudinary paths (pendiente push)
- Agregados items #2-#14 recopilados de TODOs y discusiones

---

## 📎 REFERENCIAS

- `docs/IMAGE_HANDLING_GUIDE.md` - Métodos deprecados (#2)
- `docs/CENTROID_MIGRATION.md` - Optimización de centroides
- `app/models/search_log.py` - Modelo para analytics (#4)
- `REFACTOR_COMPLETE_20OCT2025.md` - Refactor reciente completado
