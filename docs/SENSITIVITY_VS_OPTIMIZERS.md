# Interacción: Sensibilidad de Detección vs Search Optimizers

**Fecha**: 23 Octubre 2025  
**Versión**: CLIP Comparador V2

---

## 📊 Resumen Ejecutivo

Son **dos sistemas complementarios** que trabajan en **diferentes etapas** del flujo de búsqueda:

```
┌─────────────────────────────────────────────────────────────┐
│                    FLUJO DE BÚSQUEDA                        │
└─────────────────────────────────────────────────────────────┘

1️⃣ ENTRADA                    2️⃣ FILTRADO                3️⃣ RANKING
   (Usuario sube imagen)         (Sensibilidad)             (Optimizers)
         │                              │                         │
         ▼                              ▼                         ▼
   ┌──────────┐              ┌──────────────────┐     ┌──────────────────┐
   │  Imagen  │              │ THRESHOLDS       │     │ SEARCH OPTIMIZER │
   │   CLIP   │──────────────▶                  │─────▶                  │
   │ Embedding│              │ • Categoría 70%  │     │ • Visual: 0.6    │
   └──────────┘              │ • Productos 30%  │     │ • Metadata: 0.3  │
                             │                  │     │ • Business: 0.1  │
                             │ DECIDE:          │     │                  │
                             │ ¿Incluir o no?   │     │ DECIDE:          │
                             └──────────────────┘     │ ¿Qué orden?      │
                                                      └──────────────────┘
```

---

## 🎯 Sistema 1: Sensibilidad de Detección (EXISTENTE)

### Ubicación
- **Modelo**: `Client.category_confidence_threshold` y `Client.product_similarity_threshold`
- **Valores**: 1-100 (porcentaje)
- **UI**: Ya existe en panel de admin (imagen del screenshot)

### Función: **FILTRADO** (¿Entra o no entra?)

#### 1. `category_confidence_threshold` (default: 70%)
**Pregunta**: *"¿La imagen corresponde a una categoría válida?"*

```python
# En detect_image_category_with_centroids()
if category_confidence >= category_confidence_threshold:
    ✅ "Es una CAMISA con 80% de confianza" → ACEPTAR
else:
    ❌ "Es una CAMISA con 65% de confianza" → RECHAZAR (no pasa el 70%)
```

**Efecto**:
- **Threshold alto (80%)**: Más estricto, menos falsos positivos
- **Threshold bajo (50%)**: Más permisivo, puede aceptar imágenes dudosas

---

#### 2. `product_similarity_threshold` (default: 30%)
**Pregunta**: *"¿Este producto es suficientemente similar para mostrarlo?"*

```python
# En _find_similar_products_in_category()
if similarity >= product_similarity_threshold:
    ✅ producto con similarity=0.45 → INCLUIR en resultados
else:
    ❌ producto con similarity=0.25 → EXCLUIR (no pasa el 30%)
```

**Efecto**:
- **Threshold alto (50%)**: Solo muestra productos muy similares
- **Threshold bajo (20%)**: Muestra más productos, menos exigente

---

## ⚙️ Sistema 2: Search Optimizers (NUEVO)

### Ubicación
- **Modelo**: `StoreSearchConfig.visual_weight`, `metadata_weight`, `business_weight`
- **Valores**: 0.0-1.0 (deben sumar 1.0)
- **UI**: Pendiente de crear (Fase 4)

### Función: **RANKING** (¿En qué orden aparecen?)

Los optimizers **NO filtran**, sino que **reordenan** los productos que YA pasaron el filtro de sensibilidad.

```python
# Flujo actual (sin optimizer)
Producto A: similarity = 0.45  → posición 1
Producto B: similarity = 0.40  → posición 2
Producto C: similarity = 0.35  → posición 3

# Con optimizer (visual=0.6, metadata=0.3, business=0.1)
Producto B: 
  - visual_score = 0.40
  - metadata_score = 0.8 (color + marca coinciden)
  - business_score = 0.6 (en stock + featured)
  - final_score = 0.6×0.40 + 0.3×0.8 + 0.1×0.6 = 0.54  → posición 1 ✨

Producto A:
  - visual_score = 0.45
  - metadata_score = 0.2 (solo color coincide)
  - business_score = 0.0 (sin stock)
  - final_score = 0.6×0.45 + 0.3×0.2 + 0.1×0.0 = 0.33  → posición 2

Producto C:
  - visual_score = 0.35
  - metadata_score = 0.0 (nada coincide)
  - business_score = 0.4 (en stock)
  - final_score = 0.6×0.35 + 0.3×0.0 + 0.1×0.4 = 0.25  → posición 3
```

**Efecto**:
- **visual_weight alto (0.8)**: Prioriza apariencia visual
- **metadata_weight alto (0.6)**: Prioriza coincidencias exactas (color, marca)
- **business_weight alto (0.3)**: Prioriza productos en stock/destacados

---

## 🔄 Interacción Entre Ambos Sistemas

### Flujo Completo con Ejemplo Real

**Usuario sube**: Imagen de polo blanco Nike

```
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 1: DETECCIÓN DE CATEGORÍA (Sensibilidad)                 │
└─────────────────────────────────────────────────────────────────┘

1. CLIP compara imagen vs centroides de categorías
   
   Resultados:
   - CAMISAS: 78% de confianza
   - GORROS: 76% de confianza
   - CASACAS: 45% de confianza

2. Verificar threshold: category_confidence_threshold = 70%
   
   ✅ CAMISAS pasa el 70% → ACEPTADA
   ✅ GORROS pasa el 70% → ACEPTADA (pero se usa desempate)
   ❌ CASACAS NO pasa el 70% → DESCARTADA

3. Aplicar desempate (margin=3%):
   78% - 76% = 2% < 3% → Muy ajustado, usar detector general
   
   Detector general: "shirt" (conf: 65%)
   "shirt" match con CAMISAS → CATEGORÍA FINAL: CAMISAS ✅


┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 2: BÚSQUEDA DE PRODUCTOS (Sensibilidad + Color Boost)    │
└─────────────────────────────────────────────────────────────────┘

4. Buscar productos solo en CAMISAS
   
   Color detectado: BLANCO (conf: 78%)
   
   Resultados con similarity:
   - Polo Nike blanco: 0.82 (color match) → +12% boost → 0.92
   - Camisa Adidas blanca: 0.77 (color match) → +12% boost → 0.86
   - Polo Nike negro: 0.80 (NO color match) → sin boost → 0.80
   - Camisa genérica blanca: 0.45
   - Polo genérico gris: 0.28

5. Verificar threshold: product_similarity_threshold = 30%
   
   ✅ Polo Nike blanco (0.92) → INCLUIR
   ✅ Camisa Adidas blanca (0.86) → INCLUIR
   ✅ Polo Nike negro (0.80) → INCLUIR
   ✅ Camisa genérica blanca (0.45) → INCLUIR
   ❌ Polo genérico gris (0.28) → EXCLUIR (NO pasa el 30%)

   Productos que PASAN el filtro: 4


┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 3: RANKING CON OPTIMIZERS (NUEVO)                        │
└─────────────────────────────────────────────────────────────────┘

6. Aplicar Search Optimizer (visual=0.6, metadata=0.3, business=0.1)

   Polo Nike blanco:
     • visual_score = 0.92
     • metadata_score = 0.6 (color + marca match)
     • business_score = 0.7 (stock + featured)
     • final_score = 0.6×0.92 + 0.3×0.6 + 0.1×0.7 = 0.80  → #1 🥇

   Camisa Adidas blanca:
     • visual_score = 0.86
     • metadata_score = 0.3 (solo color match)
     • business_score = 0.4 (solo stock)
     • final_score = 0.6×0.86 + 0.3×0.3 + 0.1×0.4 = 0.64  → #2 🥈

   Polo Nike negro:
     • visual_score = 0.80
     • metadata_score = 0.3 (solo marca match)
     • business_score = 0.0 (sin stock)
     • final_score = 0.6×0.80 + 0.3×0.3 + 0.1×0.0 = 0.57  → #3 🥉

   Camisa genérica blanca:
     • visual_score = 0.45
     • metadata_score = 0.3 (solo color match)
     • business_score = 0.0 (sin stock, sin marca)
     • final_score = 0.6×0.45 + 0.3×0.3 + 0.1×0.0 = 0.36  → #4


┌─────────────────────────────────────────────────────────────────┐
│ RESULTADO FINAL MOSTRADO AL USUARIO                            │
└─────────────────────────────────────────────────────────────────┘

1. Polo Nike blanco (score: 0.80)
2. Camisa Adidas blanca (score: 0.64)
3. Polo Nike negro (score: 0.57)
4. Camisa genérica blanca (score: 0.36)
```

---

## 🎛️ Escenarios de Configuración

### Escenario 1: Tienda Exigente con Énfasis en Calidad Visual

```yaml
Sensibilidad:
  category_confidence_threshold: 80%  # Solo categorías muy claras
  product_similarity_threshold: 45%   # Solo productos muy similares

Optimizers:
  visual_weight: 0.8   # Prioriza apariencia
  metadata_weight: 0.1 # Baja prioridad a coincidencias exactas
  business_weight: 0.1 # Baja prioridad a stock
```

**Resultado**: Pocos productos pero muy relevantes visualmente

---

### Escenario 2: Tienda Flexible con Énfasis en Conversión

```yaml
Sensibilidad:
  category_confidence_threshold: 60%  # Más permisivo
  product_similarity_threshold: 25%   # Muestra más productos

Optimizers:
  visual_weight: 0.3   # Baja prioridad visual
  metadata_weight: 0.3 # Media prioridad exactitud
  business_weight: 0.4 # ALTA prioridad a stock/featured
```

**Resultado**: Muchos productos, ordenados por disponibilidad

---

### Escenario 3: Tienda de Moda con Énfasis en Exactitud

```yaml
Sensibilidad:
  category_confidence_threshold: 70%  # Balanceado
  product_similarity_threshold: 30%   # Balanceado

Optimizers:
  visual_weight: 0.3   # Baja prioridad visual
  metadata_weight: 0.6 # ALTA prioridad a color/marca exacta
  business_weight: 0.1 # Baja prioridad stock
```

**Resultado**: Productos que matchean exactamente color/marca buscado

---

## 📋 Tabla Comparativa

| Aspecto | Sensibilidad de Detección | Search Optimizers |
|---------|---------------------------|-------------------|
| **Función** | Filtrado (incluir/excluir) | Ranking (orden) |
| **Etapa** | Pre-filtro | Post-filtro |
| **Pregunta** | "¿Es relevante?" | "¿Cuál primero?" |
| **Efecto en resultados** | Cantidad de productos | Orden de productos |
| **Valores** | 1-100% (threshold) | 0.0-1.0 (pesos) |
| **Default** | 70% categoría, 30% productos | 0.6, 0.3, 0.1 |
| **UI existente** | ✅ Sí (screenshot) | ❌ No (Fase 4) |
| **Implementado** | ✅ Sí | ⏳ En progreso |

---

## 🔧 Recomendaciones de Configuración por Industria

### Textil/Fashion (actual Eve's Store)
```
Sensibilidad: category=70%, product=30%
Optimizers: visual=0.6, metadata=0.3, business=0.1
Razón: Balance entre apariencia y exactitud de color/marca
```

### Muebles/Decoración
```
Sensibilidad: category=75%, product=35%
Optimizers: visual=0.8, metadata=0.1, business=0.1
Razón: La apariencia es crítica en decoración
```

### Electrónica
```
Sensibilidad: category=80%, product=40%
Optimizers: visual=0.3, metadata=0.6, business=0.1
Razón: Marca y especificaciones son más importantes que apariencia
```

### E-commerce Rápido (marketplace)
```
Sensibilidad: category=65%, product=25%
Optimizers: visual=0.3, metadata=0.2, business=0.5
Razón: Priorizar productos en stock para conversión rápida
```

---

## ⚠️ Consideraciones Importantes

### 1. Orden de Aplicación
```
Sensibilidad → Color Boost → Category Boost → Optimizers
     ↓              ↓              ↓               ↓
  Filtrado       +12%           +15%          Reordenar
```

Los boosts de color y categoría **modifican el visual_score** que luego usa el optimizer.

### 2. No Son Redundantes
- **Sensibilidad**: Define el universo de productos a considerar
- **Optimizers**: Define cómo priorizar dentro de ese universo

### 3. Compatibilidad
Los sistemas son **totalmente compatibles**. El optimizer usa el `similarity` que ya fue boosteado por color/categoría.

---

## 🚀 Próximos Pasos (Fase 4)

1. Crear UI en panel de admin para configurar optimizers
2. Permitir ajuste independiente de ambos sistemas
3. Dashboard para comparar métricas con/sin optimizer
4. Presets por industria

---

**Conclusión**: Los sistemas trabajan en **serie** (secuencial), no en paralelo. Primero filtran, luego rankean. Esto da máxima flexibilidad para ajustar tanto la **cantidad** como el **orden** de resultados.
