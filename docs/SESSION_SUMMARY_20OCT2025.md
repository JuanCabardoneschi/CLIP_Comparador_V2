# Resumen de Mejoras - Sistema Visual Search (20 Oct 2025)

## 🎯 Problema Original
Widget mostraba "GORROS – GORRAS" para una imagen de polo blanco, y priorizaba camisas negras sobre blancas.

## ✅ Soluciones Implementadas

### 1. Margen de Victoria en Detección de Categorías
**Problema**: GORROS (0.7927) vs CAMISAS (0.7904) - diferencia de 0.0023 (foto-finish)

**Solución**:
- Margen mínimo de 0.03 para aceptar categoría ganadora
- Si delta < 0.03 → desempate con detector general
- Detector general usa `name_en` de categorías del cliente (dinámico)
- Si segunda categoría coincide con objeto detectado → elegir esa

**Resultado**: Polo blanco → CAMISAS en lugar de GORROS

---

### 2. Boost Dinámico por Color
**Problema**: Camisa negra (0.82) aparecía antes que camisa blanca (0.77)

**Solución**:
- Detectar color dominante usando colores reales del catálogo del cliente
- Query colores únicos de `Product.color` por cliente
- Generar prompts: `"a photo of {color} product"`
- Boost del 12% si `product.color == detected_color` (case-insensitive)

**Resultado**: Camisa blanca (0.86 con boost) → aparece primero

---

### 3. Auto-Recálculo de Centroides
**Problema**: Centroides desactualizados después de añadir imágenes

**Solución**:
- Hook automático en `embeddings.py` después de procesar embeddings
- Identifica categorías afectadas en el lote
- Llama a `category.needs_centroid_update()` para cada una
- Recalcula solo si cambió el número de imágenes
- Un recálculo por categoría, no N veces

**Resultado**: Centroides siempre frescos sin intervención manual

---

### 4. Fix SQL Cast Error
**Problema**: `syntax error at or near ':'` en query de `product_attribute_config`

**Solución**:
- Cambiar `client_id = :client_id::uuid` → `client_id = :client_id`
- PostgreSQL maneja el cast automáticamente
- Previene abortos de transacción que dejaban `image_url` en null

**Resultado**: Sin errores SQL, sesiones estables

---

### 5. Sistema 100% Dinámico (Sin Hardcodeo)
**Problema**: Código con listas hardcodeadas para textiles

**Eliminado**:
- ❌ `commercial_keywords` (hat, shirt, shoe, etc.)
- ❌ Prompts de colores fijos ("white clothing", "black clothing")
- ❌ Mapeo de colores (white → BLANCO/WHITE)
- ❌ Sinónimos de categorías (shirt → camisas/remeras)
- ❌ Categorías generales (car, food, electronics)

**Ahora**:
- ✅ Usa `Product.color` del cliente
- ✅ Usa `Category.name_en` del cliente
- ✅ Matching directo sin mapeos
- ✅ Funciona para CUALQUIER industria

**Resultado**: Sistema universal (textil, muebles, electrónica, etc.)

---

## 📊 Flujo Completo Actual

```
1. Usuario sube imagen (polo blanco)
   ↓
2. Detección de color
   - Query colores del cliente: [BLANCO, NEGRO, AZUL, ...]
   - Prompts: ["a photo of blanco product", ...]
   - Resultado: "BLANCO" (conf: 0.78)
   ↓
3. Detección de categoría (centroides)
   - GORROS: 0.7927
   - CAMISAS: 0.7904
   - Delta: 0.0023 < 0.03 → DESEMPATE
   ↓
4. Desempate con detector general
   - Categorías del cliente: [camisas, gorros, casacas, ...]
   - Prompts: ["a photo of shirt", "a photo of hat", ...]
   - Resultado: "shirt" (conf: 0.65)
   - "shirt" match con CAMISAS (name_en) → ELEGIR CAMISAS
   ↓
5. Búsqueda en categoría CAMISAS
   - Camisa negra: 0.82
   - Camisa blanca: 0.77
   ↓
6. Boost por color
   - Camisa negra: 0.82 (sin boost, NEGRO != BLANCO)
   - Camisa blanca: 0.77 * 1.12 = 0.86 ✅
   ↓
7. Ordenamiento final
   1° Camisa blanca (0.86)
   2° Camisa negra (0.82)
```

---

## 🔧 Parámetros Configurables

### Por Cliente (tabla `clients`):
- `category_confidence_threshold`: 70 (default) → Umbral para aceptar categoría
- `product_similarity_threshold`: 30 (default) → Umbral para incluir producto

### Por Sistema (código):
- `MARGIN_DELTA`: 0.03 → Margen para desempate de categorías
- `COLOR_BOOST`: 1.12 → Magnitud del boost por color (12%)
- `COLOR_CONFIDENCE_MIN`: 0.25 → Umbral para aplicar boost de color

---

## 📁 Archivos Modificados

### Core:
- `clip_admin_backend/app/blueprints/api.py`
  - `detect_dominant_color(image_data, client_id)` - Dinámico
  - `detect_general_object(image_data, client_id)` - Dinámico
  - `detect_image_category_with_centroids()` - Margen + desempate
  - `visual_search()` - Integración de color boost
  - SQL fix (sin ::uuid cast)

- `clip_admin_backend/app/blueprints/embeddings.py`
  - Hook de auto-recálculo de centroides post-embedding
  - Un recálculo por categoría afectada

### Utilidades:
- `tools/maintenance/recalculate_centroids.py` - Script manual de recálculo

### Documentación:
- `docs/COLOR_BOOST_IMPLEMENTATION.md` - Guía completa del boost dinámico
- `docs/IMAGE_HANDLING_GUIDE.md` - Patrón unificado de URLs

---

## 🚀 Deployments

### Commits principales:
1. `5740c6f` - Margen de victoria + desempate + SQL fix
2. `54adf01` - Boost dinámico por color + auto-centroides

### Railway:
- Deploy automático detectado
- Servicio: `clip_admin_backend` (Puerto 5000)
- Base de datos: PostgreSQL con centroides actualizados localmente
- **Nota**: Centroides en Railway deben recalcularse manualmente si se desea

---

## 🧪 Testing

### Local:
```powershell
# Recalcular centroides
python .\tools\maintenance\recalculate_centroids.py

# Resultado: 11/12 categorías actualizadas (REMERAS sin imágenes procesadas)
```

### Widget:
1. Subir imagen de polo blanco
2. Verificar logs:
   ```
   🎨 DETECCIÓN COLOR: BLANCO (confianza: 0.78)
   ⚖️  MARGEN PEQUEÑO (0.0023 < 0.03), aplicando desempate
   🔍 OBJETO GENERAL = shirt (conf 0.65)
   ✅ DESEMPATE → Preferimos 'CAMISAS' por concordar con objeto 'shirt'
   🎨 COLOR BOOST: CAMISA BLANCA (BLANCA) 0.77 → 0.86
   ```
3. Resultado esperado: Camisa blanca primero

---

## 📈 Próximos Pasos Opcionales

1. **Métricas**:
   - Trackear cuántos productos reciben color_boost
   - A/B testing: con/sin boost de color

2. **Ajustes por feedback**:
   - Si usuarios reportan errores → ajustar umbral/magnitud
   - Logs detallados permiten debugging rápido

3. **Recálculo de centroides en Railway**:
   - Ejecutar script en Railway después de deploy
   - Considerar hook automático post-deploy

4. **REMERAS**:
   - Procesar embeddings para imágenes de REMERAS
   - Recalcular centroide para incluir en detección

---

## ✅ Verificación de Calidad

- **Lint**: PASS (sin errores estáticos)
- **Build**: PASS (compilación exitosa)
- **Tests**: N/A (no hay suite de tests en el repo)
- **Deploy**: Railway detectó cambios automáticamente

---

## 🎓 Lecciones Aprendidas

1. **Nunca hardcodear categorías/colores**: Sistema debe adaptarse al cliente
2. **Centroides requieren mantenimiento**: Auto-recálculo es crítico
3. **Color importa**: CLIP captura forma bien, pero color necesita boost explícito
4. **Márgenes pequeños son comunes**: Desempate inteligente es esencial
5. **SQL casts implícitos**: PostgreSQL maneja tipos automáticamente

---

## 📞 Soporte

Para ajustar parámetros o investigar casos edge, revisar logs con prefijo:
- `🎨 RAILWAY LOG:` - Detección de color
- `🔍 RAILWAY LOG:` - Detección de objeto/categoría
- `⚖️  RAILWAY LOG:` - Desempate por margen pequeño
- `🎨 COLOR BOOST:` - Boost aplicado a producto

Todos los cambios están documentados en `docs/COLOR_BOOST_IMPLEMENTATION.md`
