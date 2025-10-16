# Migración de Centroides a Base de Datos
## CLIP Comparador V2 - Performance Optimization

### 🎯 OBJETIVO
Reducir tiempo de detección de categorías de **28 segundos a 1-2 segundos** almacenando centroides precalculados en PostgreSQL.

### 📋 PLAN DE MIGRACIÓN

#### Fase 1: Preparación Base de Datos ✅
- [x] Agregar columnas `centroid_embedding`, `centroid_updated_at`, `centroid_image_count` a tabla `categories`
- [x] Crear triggers para invalidación automática cuando cambian imágenes
- [x] Crear funciones SQL de soporte
- [x] Crear vista de estadísticas `category_centroid_stats`

#### Fase 2: Actualización del Modelo ✅
- [x] Método `update_centroid_embedding()` optimizado con logging
- [x] Método `get_centroid_embedding()` para carga desde BD
- [x] Método `needs_centroid_update()` para detectar cambios
- [x] Método `recalculate_all_centroids()` para migración masiva

#### Fase 3: API Ultra-Optimizada ✅
- [x] Función `detect_image_category_with_centroids()` usando BD
- [x] Timing detallado por operación
- [x] Cache automático con fallback a cálculo
- [x] Logging de performance (BD vs calculado)

#### Fase 4: Scripts de Migración ✅
- [x] `migration_add_centroids.sql` - DDL completo
- [x] `apply_centroid_migration.py` - Aplicar migración a Railway
- [x] `recalculate_centroids.py` - Migrar centroides existentes

### 🚀 DEPLOYMENT A RAILWAY

#### Paso 1: Aplicar Migración SQL
```bash
# En Railway PostgreSQL Console o conexión directa
python shared/database/apply_centroid_migration.py
```

#### Paso 2: Migrar Centroides Existentes
```bash
# Recalcular todos los centroides y guardarlos en BD
python shared/database/recalculate_centroids.py
```

#### Paso 3: Deploy Código Actualizado
```bash
git add .
git commit -m "feat: Centroides en BD - Performance 28s → 1-2s"
git push  # Auto-deploy en Railway
```

### ⚡ PERFORMANCE ESPERADO

| Scenario | Tiempo Anterior | Tiempo Con BD | Mejora |
|----------|----------------|---------------|---------|
| Primera búsqueda (cold start) | 28s | 5-8s | 71% mejora |
| Búsquedas subsecuentes | 28s | 1-2s | 95% mejora |
| Con cache lleno | 28s | 0.5-1s | 98% mejora |

### 📊 BREAKDOWN DE TIEMPO

**Con Centroides en BD:**
- Carga modelo CLIP: ~0.5s (una vez)
- Generar embedding query: ~0.8s
- Cargar centroides desde BD: ~0.1s  
- Comparar similitudes: ~0.1s
- **Total: ~1.5s**

**Anterior (cálculo on-demand):**
- Carga modelo CLIP: ~0.5s
- Generar embedding query: ~0.8s
- Calcular 12 centroides: ~26s
- Comparar similitudes: ~0.7s
- **Total: ~28s**

### 🔧 ARQUITECTURA

```
┌─────────────────────────────────────────────────┐
│                 CLIP API REQUEST                │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│            Generate Query Embedding             │
│              (~0.8s - ÚNICO CÁLCULO)           │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│         Load Category Centroids from BD         │
│              (~0.1s - SÚPER RÁPIDO)            │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│            Cosine Similarity Comparison          │
│               (~0.1s - MATEMÁTICA)              │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│              Return Best Match                   │
│                  (~1.5s TOTAL)                  │
└─────────────────────────────────────────────────┘
```

### 🔄 AUTO-ACTUALIZACIÓN

**Triggers SQL automáticos:**
- Cuando se **crea/modifica/elimina** una imagen → Invalida centroide de categoría
- Próxima búsqueda → Recalcula centroide automáticamente
- **Sistema siempre actualizado** sin intervención manual

### 📝 TESTING PLAN

1. **Aplicar migración** en Railway PostgreSQL
2. **Recalcular centroides** existentes
3. **Deploy código** actualizado
4. **Probar con widget** - gorra púrpura
5. **Verificar tiempo** < 2 segundos
6. **Probar segunda búsqueda** - tiempo < 1 segundo

### 🛡️ ROLLBACK PLAN

Si algo falla:
```sql
-- Rollback rápido - eliminar columnas
ALTER TABLE categories 
DROP COLUMN IF EXISTS centroid_embedding,
DROP COLUMN IF EXISTS centroid_updated_at,
DROP COLUMN IF EXISTS centroid_image_count;

-- Volver a código anterior
git revert HEAD
```

### 📈 MONITOREO

**Logs a observar:**
- `⚡ Centroide cargado desde BD` → Performance óptima
- `🔄 Centroide no existe, calculando` → Primera vez (normal)
- `✅ Centroide actualizado` → Auto-actualización funcionando
- `⏱️ Tiempo total: X.XXs` → Verificar < 2s

### 🎉 RESULTADO ESPERADO

**Antes:** 28 segundos por búsqueda (inaceptable)  
**Después:** 1-2 segundos por búsqueda (production-ready)  
**Escalabilidad:** Lineal con número de categorías  
**Mantenimiento:** Automático con triggers  

¡Lista para deployment! 🚀