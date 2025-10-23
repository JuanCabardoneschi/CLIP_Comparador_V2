# Plan de Implementación: Search Optimizers
**Fecha de Inicio**: 23 Octubre 2025  
**Tag de Referencia**: `v2.0.0-pre-search-optimizer`  
**Duración Estimada**: 3-4 semanas  
**Responsable**: Equipo de Desarrollo

---

## 🎯 Objetivo General

Implementar un sistema de optimizadores de búsqueda configurable por tienda que permita ponderar diferentes factores en el ranking de resultados: similitud visual CLIP, coincidencias de metadatos, y lógica de negocio.

---

## 📋 Arquitectura de Solución

### Sistema de 3 Capas de Optimización

```
┌─────────────────────────────────────────────────────────┐
│           FINAL SCORE = Σ (layer_weight × layer_score) │
└─────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐          ┌────▼────┐          ┌────▼────┐
   │ VISUAL  │          │METADATA │          │BUSINESS │
   │ LAYER   │          │  LAYER  │          │  LAYER  │
   └─────────┘          └─────────┘          └─────────┘
        │                     │                     │
   ┌────▼────────┐      ┌────▼─────────┐     ┌────▼─────────┐
   │• CLIP Score │      │• Color match │     │• Stock > 0   │
   │• Category   │      │• Brand match │     │• Featured    │
   │  boost (15%)│      │• Pattern     │     │• Discount    │
   │• Color boost│      │  match       │     │• Popularity  │
   │  (12%)      │      │• Atributos   │     │              │
   └─────────────┘      │  JSONB       │     └──────────────┘
                        └──────────────┘
```

### Modelo de Datos

```python
# Tabla: store_search_config
{
    store_id: String(36) PK FK(clients.id)
    visual_weight: Float (0.0-1.0) default=0.6
    metadata_weight: Float (0.0-1.0) default=0.3
    business_weight: Float (0.0-1.0) default=0.1
    metadata_config: JSONB {
        'color': {'enabled': True, 'weight': 0.3},
        'brand': {'enabled': True, 'weight': 0.3},
        'pattern': {'enabled': False, 'weight': 0.2},
        'custom': {...}  # Atributos adicionales desde ProductAttributeConfig
    }
    updated_at: DateTime
}
```

---

## 📅 PLAN DE TRABAJO DETALLADO

---

## **FASE 1: FUNDAMENTOS (Semana 1)**
**Objetivo**: Crear modelo de datos y migración  
**Duración**: 5 días laborales  
**Prioridad**: 🔴 CRÍTICA

### Task 1.1: Crear modelo StoreSearchConfig
**Archivo**: `clip_admin_backend/app/models/store_search_config.py`  
**Estimación**: 2 horas

**Checklist**:
- [ ] Crear archivo del modelo con SQLAlchemy
- [ ] Definir campos (store_id, visual_weight, metadata_weight, business_weight)
- [ ] Configurar campo JSONB para metadata_config
- [ ] Agregar validación: suma de pesos debe ser 1.0 ± 0.01
- [ ] Crear métodos helper: `get_or_create_default()`, `validate_weights()`
- [ ] Documentar docstrings con ejemplos

**Criterios de Aceptación**:
```python
# Debe poder instanciarse
config = StoreSearchConfig(store_id='uuid-123')
assert config.visual_weight == 0.6
assert config.metadata_weight == 0.3
assert config.business_weight == 0.1
assert sum([config.visual_weight, config.metadata_weight, config.business_weight]) == 1.0
```

**Archivos a Crear**:
- `clip_admin_backend/app/models/store_search_config.py`

**Archivos a Modificar**:
- `clip_admin_backend/app/models/__init__.py` (importar nuevo modelo)

---

### Task 1.2: Migración Alembic
**Estimación**: 1 hora

**Checklist**:
- [ ] Generar migración: `flask db migrate -m "Add store_search_config table"`
- [ ] Revisar SQL generado para PostgreSQL
- [ ] Verificar constraints (FK a clients.id, checks de pesos)
- [ ] Aplicar localmente: `flask db upgrade`
- [ ] Validar que tabla existe en PostgreSQL local
- [ ] Commit de migración

**Criterios de Aceptación**:
```sql
-- Debe existir la tabla
SELECT * FROM store_search_config;

-- Debe tener constraint de FK
SELECT constraint_name FROM information_schema.table_constraints 
WHERE table_name = 'store_search_config' AND constraint_type = 'FOREIGN KEY';
```

**Archivos a Crear**:
- `clip_admin_backend/migrations/versions/xxxx_add_store_search_config.py`

---

### Task 1.3: Seed de datos default
**Estimación**: 1 hora

**Checklist**:
- [ ] Crear script `seed_search_config.py`
- [ ] Para cada cliente existente, insertar configuración default
- [ ] Validar que no existan duplicados
- [ ] Logging de clientes procesados
- [ ] Ejecutar localmente y validar

**Criterios de Aceptación**:
```python
# Todos los clientes tienen config
clients_count = Client.query.count()
configs_count = StoreSearchConfig.query.count()
assert clients_count == configs_count
```

**Archivos a Crear**:
- `clip_admin_backend/seed_search_config.py`

---

### Task 1.4: Tests unitarios del modelo
**Estimación**: 2 horas

**Checklist**:
- [ ] Test de creación de configuración
- [ ] Test de validación de pesos (suma != 1.0 debe fallar)
- [ ] Test de metadata_config JSONB
- [ ] Test de relación FK con Client
- [ ] Test de valores por defecto

**Archivos a Crear**:
- `clip_admin_backend/tests/test_store_search_config.py`

---

## **FASE 2: CLASE SEARCHOPTIMIZER (Semana 2)**
**Objetivo**: Crear lógica de optimización modular  
**Duración**: 5 días laborales  
**Prioridad**: 🔴 CRÍTICA

### Task 2.1: Crear directorio core y estructura
**Estimación**: 30 minutos

**Checklist**:
- [ ] Crear directorio `clip_admin_backend/app/core/`
- [ ] Crear `__init__.py` con exports
- [ ] Documentar propósito del módulo core

**Archivos a Crear**:
- `clip_admin_backend/app/core/__init__.py`

---

### Task 2.2: Implementar SearchResult dataclass
**Estimación**: 1 hora

**Checklist**:
- [ ] Crear dataclass con campos: product_id, visual_score, metadata_score, business_score, final_score, product
- [ ] Agregar método `to_dict()` para serialización
- [ ] Documentar cada campo

**Archivos a Crear**:
- `clip_admin_backend/app/core/search_optimizer.py` (parte 1)

---

### Task 2.3: Implementar SearchOptimizer.calculate_metadata_score()
**Estimación**: 3 horas

**Checklist**:
- [ ] Método que recibe Product y detected_attributes dict
- [ ] Scoring para color matching (0.3 por defecto)
- [ ] Scoring para brand matching (0.3 por defecto)
- [ ] Scoring para pattern matching desde JSONB (0.2 por defecto)
- [ ] Soporte para atributos custom desde metadata_config
- [ ] Cap de score a 1.0
- [ ] Logging detallado de cada match
- [ ] Type hints estrictos

**Criterios de Aceptación**:
```python
optimizer = SearchOptimizer(store_config)
product = Product(color='BLANCO', brand='Nike')
detected = {'color': 'BLANCO', 'brand': 'Nike'}
score = optimizer.calculate_metadata_score(product, detected)
assert score == 0.6  # color (0.3) + brand (0.3)
```

---

### Task 2.4: Implementar SearchOptimizer.calculate_business_score()
**Estimación**: 2 horas

**Checklist**:
- [ ] Scoring para stock > 0 (0.4)
- [ ] Scoring para is_featured (0.3) - requiere nueva columna
- [ ] Scoring para discount > 0 (0.3) - requiere nueva columna
- [ ] Manejo de atributos opcionales con hasattr
- [ ] Cap de score a 1.0
- [ ] Logging detallado

**Nota**: is_featured y discount son opcionales en esta fase. Si no existen, business_score solo considera stock.

---

### Task 2.5: Implementar SearchOptimizer.rank_results()
**Estimación**: 3 horas

**Checklist**:
- [ ] Método que recibe lista de raw_results y detected_attributes
- [ ] Iterar sobre cada resultado
- [ ] Calcular metadata_score y business_score para cada producto
- [ ] Aplicar fórmula de ponderación con pesos configurados
- [ ] Crear SearchResult objects
- [ ] Ordenar por final_score descendente
- [ ] Logging de scores por capa para debugging
- [ ] Type hints estrictos
- [ ] Documentación completa con ejemplos

**Criterios de Aceptación**:
```python
raw_results = [
    {'product': product1, 'similarity': 0.8},
    {'product': product2, 'similarity': 0.9}
]
detected_attrs = {'color': 'BLANCO'}
ranked = optimizer.rank_results(raw_results, detected_attrs)
assert len(ranked) == 2
assert ranked[0].final_score >= ranked[1].final_score
assert hasattr(ranked[0], 'visual_score')
assert hasattr(ranked[0], 'metadata_score')
```

**Archivos a Crear/Modificar**:
- `clip_admin_backend/app/core/search_optimizer.py` (completar)

---

### Task 2.6: Tests unitarios de SearchOptimizer
**Estimación**: 4 horas

**Checklist**:
- [ ] Test de calculate_metadata_score con diferentes matches
- [ ] Test de calculate_business_score con stock/sin stock
- [ ] Test de rank_results con diferentes pesos
- [ ] Test de rank_results con metadata_config custom
- [ ] Test de edge cases (lista vacía, scores extremos)
- [ ] Test de performance con 100+ productos

**Archivos a Crear**:
- `clip_admin_backend/tests/test_search_optimizer.py`

---

## **FASE 3: INTEGRACIÓN EN API (Semana 3 - Días 1-3)**
**Objetivo**: Integrar SearchOptimizer en flujo de búsqueda  
**Duración**: 3 días laborales  
**Prioridad**: 🔴 CRÍTICA

### Task 3.1: Modificar _find_similar_products()
**Archivo**: `clip_admin_backend/app/blueprints/api.py`  
**Estimación**: 4 horas

**Checklist**:
- [ ] Importar SearchOptimizer y StoreSearchConfig
- [ ] Después de línea ~980, cargar store_config
- [ ] Si no existe config, crear default en memoria (no persistir aún)
- [ ] Convertir product_best_match a formato raw_results
- [ ] Preparar detected_attributes dict con color detectado
- [ ] Instanciar SearchOptimizer(store_config)
- [ ] Llamar a optimizer.rank_results()
- [ ] Convertir SearchResult objects de vuelta a formato original
- [ ] Agregar campos adicionales: visual_score, metadata_score, business_score
- [ ] Logging detallado de scores por capa
- [ ] Mantener backward compatibility (si optimizer falla, usar scores originales)

**Criterios de Aceptación**:
```python
# La búsqueda debe funcionar con optimizer
response = client.post('/api/search', files={'image': image_file})
assert response.status_code == 200
results = response.json['results']
assert 'visual_score' in results[0]
assert 'metadata_score' in results[0]
assert 'final_score' in results[0]['similarity']
```

**Cambios Esperados**:
```python
# ANTES (línea ~980)
return product_best_match

# DESPUÉS
# ✅ Cargar configuración de tienda
store_config = StoreSearchConfig.query.get(client.id)
if not store_config:
    store_config = StoreSearchConfig(
        store_id=client.id,
        visual_weight=0.6,
        metadata_weight=0.3,
        business_weight=0.1
    )

# ✅ Preparar para optimizer
raw_results = [
    {'product': match['product'], 'similarity': match['similarity']}
    for match in product_best_match.values()
]

# ✅ Aplicar optimizer
optimizer = SearchOptimizer(store_config)
detected_attrs = {'color': detected_color}
ranked_results = optimizer.rank_results(raw_results, detected_attrs)

# ✅ Convertir de vuelta
product_best_match = {
    r.product_id: {
        'product': r.product,
        'similarity': r.final_score,
        'visual_score': r.visual_score,
        'metadata_score': r.metadata_score,
        'business_score': r.business_score,
        'category': match['category'],
        'category_boost': match.get('category_boost', False),
        'color_boost': match.get('color_boost', False)
    }
    for r in ranked_results
}

return product_best_match
```

---

### Task 3.2: Actualizar _build_search_results()
**Estimación**: 2 horas

**Checklist**:
- [ ] Incluir visual_score, metadata_score, business_score en respuesta JSON
- [ ] Mantener campos existentes (similarity como final_score)
- [ ] Agregar campo `optimization_applied: true/false`
- [ ] Documentar nuevos campos en comentarios

**Criterios de Aceptación**:
```json
{
  "results": [
    {
      "product_id": "...",
      "similarity": 0.87,
      "visual_score": 0.82,
      "metadata_score": 0.6,
      "business_score": 0.4,
      "optimization_applied": true,
      ...
    }
  ]
}
```

---

### Task 3.3: Tests de integración de búsqueda
**Estimación**: 3 horas

**Checklist**:
- [ ] Test de búsqueda con optimizer enabled
- [ ] Test de búsqueda con diferentes pesos
- [ ] Test de búsqueda sin configuración (usa defaults)
- [ ] Test de comparación: con/sin optimizer para misma imagen
- [ ] Test de performance: medir tiempo de respuesta

**Archivos a Crear**:
- `clip_admin_backend/tests/test_search_with_optimizer.py`

---

### Task 3.4: Cacheo de configuraciones en Redis
**Estimación**: 2 horas

**Checklist**:
- [ ] Implementar cache de store_config en Redis
- [ ] TTL de 1 hora
- [ ] Invalidación al actualizar config
- [ ] Fallback a DB si Redis falla
- [ ] Logging de cache hits/misses

**Criterios de Aceptación**:
```python
# Primera búsqueda: cache miss, carga de DB
# Búsquedas siguientes: cache hit, sin DB query
```

---

## **FASE 4: PANEL DE ADMINISTRACIÓN (Semana 3-4)**
**Objetivo**: Interface para configurar optimizadores  
**Duración**: 5 días laborales  
**Prioridad**: 🟡 ALTA

### Task 4.1: Blueprint de configuración
**Archivo**: `clip_admin_backend/app/blueprints/search_config.py`  
**Estimación**: 3 horas

**Checklist**:
- [ ] Crear blueprint `search_config`
- [ ] Ruta GET `/clients/<client_id>/search-config` para vista
- [ ] Ruta POST `/clients/<client_id>/search-config` para guardar
- [ ] Validación: pesos deben sumar 1.0 ± 0.01
- [ ] Validación: cada peso entre 0.0 y 1.0
- [ ] Respuestas JSON con success/error
- [ ] Logging de cambios de configuración
- [ ] Decorador @login_required

**Archivos a Crear**:
- `clip_admin_backend/app/blueprints/search_config.py`

**Archivos a Modificar**:
- `clip_admin_backend/app/__init__.py` (registrar blueprint)

---

### Task 4.2: Template con sliders
**Archivo**: `clip_admin_backend/app/templates/search_config/edit.html`  
**Estimación**: 4 horas

**Checklist**:
- [ ] Layout con card de Bootstrap 5
- [ ] 3 sliders para visual_weight, metadata_weight, business_weight
- [ ] Display dinámico del valor al lado de cada slider
- [ ] Indicador de suma total (debe ser 1.0)
- [ ] Validación en tiempo real con JavaScript
- [ ] Sección expandible para metadata_config
- [ ] Checkboxes para habilitar/deshabilitar color, brand, pattern
- [ ] Botón "Guardar" con loading state
- [ ] Botón "Resetear a defaults"
- [ ] Toast notifications para success/error
- [ ] Responsive design

**Archivos a Crear**:
- `clip_admin_backend/app/templates/search_config/edit.html`
- `clip_admin_backend/app/static/js/search_config.js`
- `clip_admin_backend/app/static/css/search_config.css`

---

### Task 4.3: Agregar enlace en dashboard de cliente
**Estimación**: 1 hora

**Checklist**:
- [ ] En template de detalle de cliente, agregar botón "Configurar Búsqueda"
- [ ] Icono apropiado (⚙️ o similar)
- [ ] Tooltip explicativo
- [ ] Link a `/clients/<id>/search-config`

**Archivos a Modificar**:
- `clip_admin_backend/app/templates/clients/detail.html`

---

### Task 4.4: Presets de configuración
**Estimación**: 2 horas

**Checklist**:
- [ ] Botones para 3 presets:
  - "Priorizar Visual" (0.8, 0.1, 0.1)
  - "Priorizar Exactitud" (0.3, 0.6, 0.1)
  - "Balanceado" (0.6, 0.3, 0.1)
- [ ] Aplicar preset al hacer click
- [ ] Descripción de cada preset
- [ ] Confirmación antes de aplicar

**Archivos a Modificar**:
- `clip_admin_backend/app/templates/search_config/edit.html`
- `clip_admin_backend/app/static/js/search_config.js`

---

## **FASE 5: VALIDACIÓN EN RAILWAY (Semana 4)**
**Objetivo**: Deploy y validación en producción  
**Duración**: 3 días laborales  
**Prioridad**: 🔴 CRÍTICA

### Task 5.1: Deploy a Railway
**Estimación**: 2 horas

**Checklist**:
- [ ] Commit de todo el código
- [ ] Push a main (Railway auto-deploys)
- [ ] Verificar que build completa exitosamente
- [ ] Verificar logs de Railway sin errores
- [ ] Aplicar migración en Railway: `flask db upgrade`
- [ ] Ejecutar seed_search_config.py en Railway
- [ ] Validar que tabla existe y tiene datos

**Comandos**:
```bash
git add .
git commit -m "feat: Implement search optimizers system"
git push origin main

# En Railway CLI o dashboard
flask db upgrade
python seed_search_config.py
```

---

### Task 5.2: Pruebas de memoria y CPU
**Estimación**: 3 horas

**Checklist**:
- [ ] Monitorear RAM usage durante búsquedas (target: < 400MB)
- [ ] Monitorear CPU usage (target: < 80%)
- [ ] Realizar 50 búsquedas consecutivas
- [ ] Verificar que no hay memory leaks
- [ ] Verificar tiempos de respuesta (target: < 3s)

**Métricas a Registrar**:
```
- RAM baseline: ___ MB
- RAM durante búsqueda: ___ MB
- RAM después de 50 búsquedas: ___ MB
- Tiempo respuesta promedio: ___ ms
- Tiempo respuesta p95: ___ ms
```

---

### Task 5.3: A/B Testing setup
**Estimación**: 4 horas

**Checklist**:
- [ ] Implementar flag `enable_optimizer` en StoreSearchConfig
- [ ] 50% de búsquedas con optimizer, 50% sin optimizer
- [ ] Logging de ambos flows con identificador
- [ ] Registrar métricas: CTR, tiempo de respuesta, similarity scores
- [ ] Dashboard simple para comparar métricas

---

### Task 5.4: Testing con cliente real (Eve's Store)
**Estimación**: 2 horas

**Checklist**:
- [ ] Configurar optimizer para Eve's Store
- [ ] Probar diferentes combinaciones de pesos
- [ ] Documentar resultados cualitativos
- [ ] Ajustar configuración óptima
- [ ] Feedback del usuario final

---

### Task 5.5: Documentación final
**Estimación**: 2 horas

**Checklist**:
- [ ] Actualizar README.md con sección de optimizers
- [ ] Crear SEARCH_OPTIMIZER_GUIDE.md para usuarios
- [ ] Documentar API endpoints nuevos
- [ ] Crear video tutorial (opcional)
- [ ] Actualizar BACKLOG_MEJORAS.md

**Archivos a Crear/Modificar**:
- `README.md`
- `docs/SEARCH_OPTIMIZER_GUIDE.md`
- `docs/API_REFERENCE.md`
- `BACKLOG_MEJORAS.md`

---

## 📊 MÉTRICAS DE ÉXITO

### Métricas Técnicas
- [ ] Tiempo de respuesta < 3s (p95)
- [ ] RAM usage < 400MB durante búsquedas
- [ ] CPU usage < 80% en picos
- [ ] 0 errores en logs de Railway
- [ ] Cobertura de tests > 80%

### Métricas de Producto
- [ ] CTR mejora en ≥10% vs baseline
- [ ] Similarity score promedio mejora en ≥5%
- [ ] Feedback positivo de al menos 1 cliente piloto
- [ ] Configuración de optimizer usada por ≥80% de clientes

---

## ⚠️ RIESGOS Y CONTINGENCIAS

### Riesgo 1: Overhead de CPU excede límites
**Probabilidad**: Media  
**Impacto**: Alto  
**Mitigación**:
- Cacheo agresivo de configuraciones en Redis
- Lazy loading de business_score (solo si weight > 0.1)
- Optimización de queries DB con indexes
**Plan B**: Desactivar optimizer y usar solo visual similarity

### Riesgo 2: Configuración compleja para usuarios
**Probabilidad**: Alta  
**Impacto**: Medio  
**Mitigación**:
- Presets simples ("Visual", "Exactitud", "Balanceado")
- Tooltips explicativos en cada control
- Video tutorial de 2 minutos
**Plan B**: Configuración por defecto optimizada, UI oculta para usuarios básicos

### Riesgo 3: Degradación de calidad de resultados
**Probabilidad**: Baja  
**Impacidad**: Alto  
**Mitigación**:
- A/B testing obligatorio antes de rollout completo
- Dashboard de métricas de calidad
- Rollback fácil a configuración default
**Plan B**: Feature flag para desactivar optimizer globalmente

---

## 📝 CHECKLIST FINAL PRE-DEPLOY

- [ ] Todos los tests unitarios pasan
- [ ] Tests de integración pasan
- [ ] Migración probada en local
- [ ] Seed script probado en local
- [ ] Template de admin funciona correctamente
- [ ] JavaScript validado sin errores
- [ ] Documentación actualizada
- [ ] Tag de versión creado
- [ ] Backup de BD de Railway realizado
- [ ] Plan de rollback documentado

---

## 🎯 CRITERIOS DE ACEPTACIÓN GLOBAL

El proyecto se considera exitoso cuando:

1. ✅ Sistema de optimizadores implementado y funcionando en Railway
2. ✅ Panel de administración accesible y usable
3. ✅ Métricas técnicas dentro de límites (RAM, CPU, tiempo respuesta)
4. ✅ A/B testing muestra mejora ≥10% en CTR
5. ✅ Al menos 1 cliente piloto con feedback positivo
6. ✅ Documentación completa para usuarios y desarrolladores
7. ✅ 0 errores críticos en logs de producción durante 1 semana

---

## 📞 PUNTOS DE REVISIÓN

### Checkpoint 1: Fin de Fase 1 (Día 5)
- **Revisar**: Modelo de datos, migración, tests
- **Decisión**: ¿Proceder a Fase 2 o ajustar modelo?

### Checkpoint 2: Fin de Fase 2 (Día 10)
- **Revisar**: SearchOptimizer implementado, tests unitarios
- **Decisión**: ¿Integrar en API o refactorizar?

### Checkpoint 3: Fin de Fase 3 (Día 13)
- **Revisar**: Integración en flujo de búsqueda, tests de integración
- **Decisión**: ¿Proceder a UI o optimizar performance?

### Checkpoint 4: Fin de Fase 4 (Día 18)
- **Revisar**: Panel de admin completo y funcional
- **Decisión**: ¿Deploy a Railway o ajustar UI?

### Checkpoint 5: Fin de Fase 5 (Día 21)
- **Revisar**: Sistema en producción, métricas, feedback
- **Decisión**: ¿Rollout completo o ajustes?

---

## 🔖 VERSIONADO

- **Tag actual**: `v2.0.0-pre-search-optimizer`
- **Tag siguiente**: `v2.1.0-search-optimizer-mvp` (al completar Fase 5)
- **Tag release**: `v2.1.0-stable` (después de 1 semana en producción sin issues)

---

**Última Actualización**: 23 Octubre 2025  
**Próxima Revisión**: Checkpoint 1 (28 Octubre 2025)
