# 📘 EXTRACTOR V2 - Reglas de Captura de Términos

## 🎯 Objetivo
Extraer **SOLO** los términos relevantes de la query del usuario: categoría de producto + atributos directos (nivel 1), descartando modificadores de modificadores (nivel 2+).

---

## ✅ Reglas de Captura

### 1. Sustantivo Principal (SIEMPRE CAPTURAR)
- **Criterio**: ROOT, obj o nsubj con POS=NOUN/PROPN
- **Función**: Representa la categoría del producto buscado
- **Ejemplo**: En "delantal con cierre" → capturar `delantal`

**⚠️ CRÍTICO**: Si NO se detecta sustantivo principal, devolver **string vacío** y abortar búsqueda (categoría no detectada).

---

### 2. Modificadores de NIVEL 1 (CAPTURAR)
Son los que modifican **directamente** al sustantivo principal.

#### 2.1 Adjetivos Directos (amod)
- **Criterio**: dep=`amod`, POS=`ADJ`, head=principal
- **Ejemplos**:
  - "short **rojo**" → capturar `rojo` ✅
  - "delantal **grande**" → capturar `grande` ✅

#### 2.2 Sustantivos Relacionados (nmod/pobj/compound)
- **Criterio**: dep=`nmod`/`pobj`/`compound`, POS=`NOUN`/`PROPN`, head=principal
- **Ejemplos**:
  - "delantal con **cierre**" → capturar `cierre` ✅ (via prep "con")
  - "remera con **bolsillos**" → capturar `bolsillos` ✅

---

### 3. Modificadores de NIVEL 2+ (DESCARTAR ⛔)
Son modificadores de los modificadores (profundidad ≥2).

#### 3.1 Adjetivos de Atributos
- **Criterio**: Adjetivo que modifica un sustantivo que ya es modificador
- **Ejemplos**:
  - "delantal con bolsillos **grandes**" → descartar `grandes` ⛔ (modifica "bolsillos", no "delantal")
  - "short con cierre **largo**" → descartar `largo` ⛔ (modifica "cierre", no "short")

#### 3.2 Ubicaciones/Posiciones
- **Criterio**: Términos de ubicación que modifican atributos
- **Ejemplos**:
  - "delantal con cierre al **costado**" → descartar `costado` ⛔ (modifica "cierre")
  - "remera con bolsillos al **frente**" → descartar `frente` ⛔ (modifica "bolsillos")
  - "top con logo **lateral**" → descartar `lateral` ⛔ (modifica "logo")

---

### 4. Verbos (SIEMPRE IGNORAR ⛔)
- **Criterio**: Cualquier token con POS=`VERB`
- **Ejemplos**:
  - "**mostrame** delantales" → ignorar `mostrame` ⛔
  - "**busco** short rojo" → ignorar `busco` ⛔
  - "**quiero** ver tops" → ignorar `quiero`, `ver` ⛔

---

## 📊 Casos de Prueba

| Query | Debe Capturar | Debe Descartar | Razón |
|-------|---------------|----------------|-------|
| "delantal con cierre al costado" | `delantal`, `cierre` | `costado` | costado=nivel 2 (modifica cierre) |
| "delantal con bolsillos grandes" | `delantal`, `bolsillos` | `grandes` | grandes=nivel 2 (modifica bolsillos) |
| "short rojo" | `short`, `rojo` | - | rojo=nivel 1 (modifica short) |
| "short rojo con cierre largo" | `short`, `rojo`, `cierre` | `largo` | largo=nivel 2 (modifica cierre) |
| "mostrame delantales" | `delantales` | `mostrame` | mostrame=verbo |
| "busco top negro" | `top`, `negro` | `busco` | busco=verbo |
| "remera con bolsillos amplios al frente" | `remera`, `bolsillos` | `amplios`, `frente` | ambos=nivel 2 |
| "pantalón verde con cierre lateral" | `pantalón`, `verde`, `cierre` | `lateral` | lateral=nivel 2 |

---

## 🧪 Testing

### Herramienta Standalone
```powershell
# Test individual
python tools/test_extractor.py "delantal con cierre al costado"

# Suite completa de tests
python tools/test_extractor.py --batch
```

### Salida Esperada (Test Individual)
```
======================================================================
RESULTADO FINAL:
  Query original: 'delantal con cierre al costado'
  Términos extraídos: 'cierre delantal'
  Términos (lista): ['cierre', 'delantal']
======================================================================
```

---

## 🔧 Implementación Técnica

### Algoritmo
```python
1. Analizar query con spaCy (análisis de dependencias)
2. Buscar sustantivo principal (ROOT/obj/nsubj):
   - Si NO existe → return "" (categoría no detectada)
   - Si existe → capturar
3. Iterar hijos directos del principal:
   - amod (adjetivo) → capturar
   - nmod/pobj/compound (sustantivo) → capturar
   - prep (preposición) → buscar pobj dentro → capturar pobj
   - Para cada hijo capturado: contar pero NO capturar sus hijos (nivel 2)
4. Fallback: capturar NOUN/PROPN mal etiquetados (mistagging)
5. Return: términos únicos ordenados separados por espacio
```

### Whitelist de Anglicismos
Términos que spaCy español puede etiquetar mal:
```python
FASHION_TERMS = {'short', 'shorts', 'top', 'crop', 'leggins', 'jeggings', 'blazer'}
```
Para estos términos se usa el texto original en lugar del lemma.

---

## 🐛 Casos Edge Conocidos

### 1. "grices" (typo de "grises")
**Problema**: spaCy etiqueta como DEP=`punct` (puntuación)
**Solución**: Fallback captura NOUN/PROPN no procesados

### 2. "delantales" etiquetado como ADJ
**Problema**: spaCy confunde plural como adjetivo
**Solución**: Fallback captura por POS sin depender solo de DEP

### 3. Anglicismos ("short", "top")
**Problema**: Lematización errónea ("short" → "shorte")
**Solución**: Whitelist preserva texto original

---

## 📈 Mejoras Futuras (No Implementadas)

1. **Contexto Semántico**: Usar CLIP/MiniLM para validar si un término nivel 2 es realmente relevante
2. **Reglas de Negocio**: Permitir configurar atributos de nivel 2 que sí deberían capturarse por cliente
3. **Aprendizaje**: Feedback loop para ajustar reglas según conversiones exitosas
4. **Multi-idioma**: Extender soporte a inglés, portugués, etc.

---

## 🔗 Referencias

- **Código**: `clip_admin_backend/app/blueprints/search_text.py:_extract_key_terms_with_dependency_parsing()`
- **Testing**: `tools/test_extractor.py`
- **Análisis Original**: `docs/ANALISIS_API_SEARCH_TEXT.md`
- **Log de Ejecución**: Ejemplo en sección "FASE 0" del análisis

---

**Última actualización**: 19 Nov 2025 - Extractor V2 implementado
