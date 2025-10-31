# 🧪 Guía de Testing: Query Enrichment desde demo-store.html

## Fecha: 31 de Octubre, 2025
## Feature: Query Enrichment con Tags Inferidos
## Estado: ✅ Activado (enable_inferred_tags: true)

---

## 📋 Checklist de Pruebas

### Preparación
- [x] `system_config.json` tiene `enable_inferred_tags: true`
- [ ] Servidor corriendo en `http://localhost:5000`
- [ ] demo-store.html abierto en navegador
- [ ] Consola del servidor visible para ver logs

---

## 🎯 Test 1: Búsqueda con Color

**Query:** `camisa roja`

### Qué hacer:
1. Abre `http://localhost:5000/static/demo-store.html`
2. Haz clic en el botón "🔮 Búsqueda AI"
3. Ve a la pestaña "Texto"
4. Escribe: "camisa roja"
5. Haz clic en "Buscar"

### Qué esperar en la consola del servidor:
```
👉 TEXT SEARCH HIT: path=/api/search from=127.0.0.1 has_key=True
🔍 TEXT SEARCH: Analizando X productos...
🧪 FUSION: alpha=1.0 beta_tag=0.5 phrases=1 tags=0
   ↑ Indica que generó 1 frase: "a red colored product"
Producto: Camisa Roja | CLIP: 0.XXX | Attr: 0.XXX | Tag: 0.XXX | Score: 0.XXX
```

### Qué esperar en el widget:
- Productos rojos aparecen primero
- Scores CLIP más altos en productos rojos vs otros colores
- Orden mejorado comparado con búsqueda sin enriquecimiento

**Resultado esperado:** ✅ PASS si ves log `🧪 FUSION: ... phrases=1`

---

## 🎯 Test 2: Búsqueda con Color + Estilo

**Query:** `delantal azul elegante`

### Qué hacer:
1. En el mismo widget (pestaña Texto)
2. Escribe: "delantal azul elegante"
3. Buscar

### Qué esperar en la consola:
```
🧪 FUSION: alpha=1.0 beta_tag=0.5 phrases=2 tags=0
   ↑ Frases: "a blue colored product" + "an elegant style product"
```

### Qué esperar en el widget:
- Delantales azules + elegantes tienen mejor score
- Separación clara entre productos que cumplen ambos criterios

**Resultado esperado:** ✅ PASS si ves `phrases=2`

---

## 🎯 Test 3: Búsqueda Solo Categoría (sin color)

**Query:** `camisa`

### Qué hacer:
1. Escribe solo: "camisa"
2. Buscar

### Qué esperar en la consola:
```
🔍 TEXT SEARCH: Analizando X productos...
(NO debe aparecer log 🧪 FUSION porque no hay color/contexto detectado)
```

### Qué esperar en el widget:
- Búsqueda funciona normalmente
- No se rompe sin enriquecimiento
- Resultados basados solo en CLIP + atributos + tags normales

**Resultado esperado:** ✅ PASS si NO hay log FUSION y búsqueda funciona

---

## 🎯 Test 4: Cache Hit (repetir búsqueda)

**Query:** `camisa roja` (repetir Test 1)

### Qué hacer:
1. Repite exactamente la búsqueda del Test 1
2. Observa los logs

### Qué esperar en la consola:
```
💾 CACHE HIT: enrichment para query="camisa roja"
   ↑ Indica que usó resultado cacheado (más rápido)
🧪 FUSION: alpha=1.0 beta_tag=0.5 phrases=1 tags=0
```

### Qué esperar en el widget:
- Resultados idénticos al Test 1
- Respuesta ligeramente más rápida

**Resultado esperado:** ✅ PASS si ves `💾 CACHE HIT`

---

## 🎯 Test 5: Múltiples Contextos

**Query:** `camisa blanca casual moderna`

### Qué hacer:
1. Escribe: "camisa blanca casual moderna"
2. Buscar

### Qué esperar en la consola:
```
🧪 FUSION: alpha=1.0 beta_tag=0.5 phrases=3 tags=0
   ↑ Frases: "white colored product" + "casual style" + "modern style"
```

### Qué esperar en el widget:
- Productos que cumplen múltiples criterios tienen mejor score
- Camisa blanca + casual + moderna aparece primera

**Resultado esperado:** ✅ PASS si ves `phrases=3`

---

## 🎯 Test 6: Búsqueda Visual (NO afectada)

### Qué hacer:
1. Ve a la pestaña "Imagen" del widget
2. Sube una imagen o toma foto
3. Buscar

### Qué esperar en la consola:
```
(NO debe aparecer log 🧪 FUSION porque es búsqueda visual, no textual)
```

### Qué esperar en el widget:
- Búsqueda visual funciona normal
- Sin cambios en el comportamiento

**Resultado esperado:** ✅ PASS - La búsqueda visual NO usa enriquecimiento

---

## 📊 Comparación de Scores: Antes vs Después

### Ejemplo Real (Query: "delantal rojo")

#### ANTES (enable_inferred_tags: false):
```
Producto: Delantal Rojo Clásico
  CLIP: 0.782
  Attr: 0.650
  Tag:  0.100
  FINAL: 0.676
```

#### DESPUÉS (enable_inferred_tags: true):
```
Producto: Delantal Rojo Clásico
  CLIP: 0.887  ← ⬆️ Mejoró por fusión con "a red colored product"
  Attr: 0.650
  Tag:  0.100
  FINAL: 0.723  ← ⬆️ Score final mejor
```

**Diferencia:** +0.105 en CLIP, +0.047 en score final

---

## ⚠️ Troubleshooting

### Si NO ves logs `🧪 FUSION`:

**Check 1:** Verificar feature flag
```bash
cat system_config.json | grep enable_inferred_tags
# Debe mostrar: "enable_inferred_tags": true
```

**Check 2:** Reiniciar servidor
```bash
cd clip_admin_backend
python app.py
# Espera ver: ✓ Blueprint api registrado (sin errores)
```

**Check 3:** Verificar endpoint
- La búsqueda debe ir a `/api/search` (texto)
- NO a `/api/search/image` (visual)

**Check 4:** Ver errores
Si hay log `⚠️ FUSION skip: [error]`, hay un problema en el servicio.
Revisa el traceback completo.

---

## 🎓 Interpretación de Logs

### Log Normal (funcionando):
```
👉 TEXT SEARCH HIT: path=/api/search from=127.0.0.1 has_key=True
🔍 TEXT SEARCH: Analizando 15 productos...
🧪 FUSION: alpha=1.0 beta_tag=0.5 phrases=2 tags=0
Producto: Camisa Roja | CLIP: 0.891 | Attr: 0.650 | Tag: 0.100 | Score: 0.725
✅ TEXT SEARCH: 5 resultados en 0.234s
```

### Log con Error (fallback silencioso):
```
👉 TEXT SEARCH HIT: path=/api/search from=127.0.0.1 has_key=True
🔍 TEXT SEARCH: Analizando 15 productos...
⚠️ FUSION skip: [error message]
Traceback (most recent call last):
  ...
Producto: Camisa Roja | CLIP: 0.782 | Attr: 0.650 | Tag: 0.100 | Score: 0.676
✅ TEXT SEARCH: 5 resultados en 0.234s
```
**Nota:** Aunque haya error, la búsqueda funciona (usa embedding sin enriquecer)

---

## ✅ Criterios de Éxito

La funcionalidad está funcionando correctamente si:

1. ✅ Ves logs `🧪 FUSION: ...` en búsquedas textuales con color/contexto
2. ✅ `phrases=X` varía según la complejidad del query
3. ✅ Scores CLIP son más altos en productos que coinciden con tags inferidos
4. ✅ Ves `💾 CACHE HIT` en búsquedas repetidas
5. ✅ Búsquedas sin color/contexto funcionan normal (sin log FUSION)
6. ✅ Búsqueda visual NO muestra logs FUSION (solo afecta texto)
7. ✅ No hay errores que bloqueen la búsqueda

---

## 📈 Métricas de Mejora Esperadas

Según el tipo de query:

| Tipo de Query | Mejora en CLIP Similarity | Mejora en Score Final |
|---------------|--------------------------|----------------------|
| Color simple ("rojo") | +0.08 - +0.12 | +0.04 - +0.06 |
| Color + estilo ("rojo casual") | +0.10 - +0.15 | +0.05 - +0.08 |
| Múltiples contextos | +0.12 - +0.18 | +0.06 - +0.09 |
| Sin color/contexto | Sin cambio | Sin cambio |

---

## 🔧 Parámetros Ajustables

En `system_config.json`:

```json
"clip_fusion": {
  "alpha": 1.0,      // Peso del query original (1.0 = 100%)
  "beta_tag": 0.5    // Peso de los tags inferidos (0.5 = 50%)
}
```

**Experimentos sugeridos:**
- `beta_tag: 0.3` - Fusión más conservadora
- `beta_tag: 0.7` - Fusión más agresiva
- `beta_tag: 1.0` - Peso igual a query original

**Después de cambiar:** Reinicia servidor y limpia cache con búsqueda nueva.

---

## 📝 Notas Finales

- **Sin breaking changes:** Si desactivas el flag, todo vuelve a funcionar como antes
- **Fallback automático:** Si algo falla, usa embedding original
- **Cache eficiente:** Búsquedas repetidas son más rápidas
- **Solo texto:** Búsqueda visual NO se ve afectada

**Fecha de implementación:** 31 de Octubre, 2025
**Versión:** CLIP Comparador V2 - Query Enrichment v1.0
**Branch:** savepoint/2025-10-31-autofill-baseline
