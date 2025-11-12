# Análisis: ¿Mantener o eliminar calibración con BLIP?

## Caso de uso del sistema

**Flujo:**
1. Cliente (tienda) → sube catálogo de productos individuales
2. Comprador final → sube foto con múltiples prendas puestas
3. Sistema → detecta cada prenda y busca productos similares

**Objetivo:** Multi-label detection + búsqueda por similitud

---

## ¿Qué hace el módulo de calibración?

### Función principal:
Ajustar `confidence_threshold` por categoría para optimizar detección multi-label.

### Proceso:
1. Admin etiqueta dataset (10-50 imágenes): "esta tiene CAMISA + PANTALÓN"
2. Sistema evalúa con diferentes thresholds
3. Encuentra threshold óptimo que maximiza F1-score por categoría
4. Guarda en `categories.confidence_threshold`

### Ejemplo de resultados:
```json
{
  "CAMISA": {
    "threshold_actual": 0.75,
    "threshold_sugerido": 0.42,
    "f1_score": 0.89,
    "precision": 0.92,
    "recall": 0.86
  },
  "GORRA": {
    "threshold_actual": 0.75,
    "threshold_sugerido": 0.68,
    "f1_score": 0.73,
    "precision": 0.71,
    "recall": 0.75
  }
}
```

---

## Escenarios de decisión

### 🟢 OPCIÓN A: Mantener calibración mínima (RECOMENDADO)

**Razones:**

1. **BLIP es desconocido en tu dominio**
   - No sabemos si sus scores son consistentes
   - Diferentes categorías pueden tener distribuciones diferentes
   - Ejemplo real con CLIP:
     - CAMISA: scores típicos 0.35-0.85
     - GORRA: scores típicos 0.15-0.45
     - Con threshold fijo 0.75 → GORRA nunca se detecta

2. **Catálogos heterogéneos por cliente**
   - Cliente A (ropa deportiva): camisetas simples, alta similitud
   - Cliente B (moda formal): camisas con muchas variaciones
   - Los scores pueden variar significativamente

3. **Bajo costo de mantenimiento**
   - Dataset pequeño: 5-10 imágenes por categoría (30-60 total)
   - Calibración 1 vez por cliente al inicio
   - Recalibrar solo si cambias modelo o catálogo cambia mucho

4. **Validación empírica**
   - Te permite medir precision/recall reales
   - Detectas categorías problemáticas antes de producción
   - Evitas frustraciones: "¿por qué no encuentra mis gorras?"

**Qué mantener:**
- ✅ Tablas: `training_images`, `calibration_runs`
- ✅ Blueprint: `calibration.py` (UI de dataset + calibrar)
- ✅ Endpoint: `diagnostic.py` (motor de evaluación)
- ❌ Eliminar: `training_events`, `client_category_variants` (experimento fallido)

**Workflow recomendado:**
```
1. Cliente nuevo → Admin etiqueta 40 imágenes desde catálogo
2. Ejecutar calibración → Aplicar thresholds sugeridos
3. Validar en producción → Ajustar manualmente si es necesario
4. No volver a calibrar (salvo cambios grandes)
```

---

### 🔴 OPCIÓN B: Eliminar calibración (RIESGOSO)

**Razones:**

1. **BLIP produce scores perfectamente consistentes**
   - Todas las categorías tienen distribuciones similares
   - Threshold fijo (ej. 0.50) funciona para todo
   - **ADVERTENCIA:** Esto es poco probable en el mundo real

2. **Ajuste manual aceptable**
   - Admin puede cambiar threshold por categoría en UI
   - Proceso de prueba y error: subir imagen → ver resultados → ajustar
   - **PROBLEMA:** Sin métricas (precision/recall), es adivinanza

3. **Máxima simplificación**
   - Menos código, menos tablas
   - Sistema más simple de mantener

**Qué eliminar:**
- ❌ Tablas: `training_images`, `calibration_runs`, `training_events`, `client_category_variants`
- ❌ Blueprint: `calibration.py`, `training_admin.py`
- ❌ Endpoint diagnóstico (o dejar solo para pruebas manuales)

**Riesgos:**
- No sabes si los thresholds son buenos hasta producción
- Clientes se quejan: "no encuentra X categoría"
- Sin métricas para fundamentar ajustes
- Debugging más difícil: ¿es el modelo o el threshold?

---

## 📊 Comparación práctica

### Escenario: Cliente nuevo con 8 categorías

#### Con calibración (Opción A):
```
Tiempo inicial: 1-2 horas
1. Admin etiqueta 40 imágenes en UI (5 por categoría)
2. Click "Calibrar" → 5 minutos
3. Revisar resultados:
   - CAMISA: F1=0.91 → threshold=0.42 ✅
   - GORRA: F1=0.73 → threshold=0.68 ✅
   - PANTALÓN: F1=0.45 → threshold=0.35 ⚠️
4. Aplicar thresholds sugeridos
5. Producción con confianza

Mantenimiento: CERO (salvo cambios mayores)
```

#### Sin calibración (Opción B):
```
Tiempo inicial: 15 minutos
1. Threshold fijo 0.50 para todas
2. A producción

Problemas en producción:
- Semana 1: "No encuentra gorras" → ajustar a 0.35
- Semana 2: "Detecta camisas donde no hay" → ajustar a 0.65
- Semana 3: Clientes se quejan...
- Sin métricas = adivinanza constante

Mantenimiento: ALTO (ajustes reactivos)
```

---

## 🎯 Recomendación final

### ✅ OPCIÓN A (Mantener calibración mínima)

**Justificación:**
1. Bajo costo de implementación (ya está hecho)
2. Validación empírica antes de producción
3. Flexibilidad por cliente/catálogo
4. Métricas objetivas para decisiones
5. Mejor experiencia de onboarding de clientes

**Plan de limpieza:**
```sql
-- Eliminar solo experimentos fallidos
DROP TABLE client_category_variants;
DROP TABLE training_events;

-- Mantener calibración útil
KEEP TABLE training_images;
KEEP TABLE calibration_runs;
```

**Uso esperado:**
- Calibración 1 vez por cliente nuevo (1-2 horas totales)
- Recalibración solo si:
  - Cambias de CLIP a BLIP
  - Cliente agrega muchas categorías nuevas
  - Catálogo cambia radicalmente
- 99% del tiempo: system funciona sin tocar calibración

---

## 📌 Conclusión

**Pregunta clave:** ¿Vale la pena 1-2 horas de setup por cliente para tener thresholds optimizados?

**Respuesta:** SÍ, porque:
- Evita problemas en producción
- Da confianza al cliente ("mira, 91% de precision")
- Troubleshooting más fácil con métricas
- Una vez calibrado, no lo tocas más

**Elimina calibración solo si:**
- ✅ BLIP demuestra scores ultra-consistentes en todos tus tests
- ✅ Threshold fijo funciona perfecto en todas las categorías
- ✅ Estás dispuesto a ajustes manuales reactivos en producción

**Conclusión:** Mantén calibración mínima (Opción A). Es una red de seguridad que casi no cuesta mantener.
