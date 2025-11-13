# Código de Integración: Multi-Crop → Producción

> **Complemento de**: INTEGRATION_MULTICROP_PRODUCTION.md
> **Código listo para copiar/pegar** en implementación Fase 1-2

---

## 📦 1. Actualizar `system_config.json`

**Archivo**: `c:\Personal\CLIP_Comparador_V2\system_config.json`

**Agregar sección** (después de `pair_exclusion_rules`):

```json
{
  "// ... otras configuraciones existentes ...": "",

  "pair_exclusion_rules": {
    "delantal": {
      "tie_margin": 0.02,
      "override_gap_max": 0.10,
      "torso_evidence_min": 0.24,
      "torso_advantage_min": 0.06,
      "suppression_evidence_threshold": 0.20
    }
  },

  "multicrop_detection": {
    "enabled": true,
    "mode": "auto",
    "ambiguous_categories": [
      "DELANTAL COMPLETO",
      "MEDIO DELANTAL",
      "CASACAS",
      "GORRO",
      "GORROS",
      "CASACA",
      "CASACA CHEF"
    ],
    "apply_pair_exclusion": true,
    "top_k_results": 3,
    "fallback_to_single": true
  }
}
```

**Descripción de parámetros**:
- `enabled`: Master switch para activar/desactivar multi-crop globalmente
- `mode`: `"off"` (single siempre), `"auto"` (solo ambiguas), `"always"` (todo multi-crop)
- `ambiguous_categories`: Lista de categorías que requieren multi-crop
- `apply_pair_exclusion`: Aplicar reglas de exclusión de pares
- `top_k_results`: Número de categorías candidatas en multi-crop
- `fallback_to_single`: Si multi-crop falla, volver a single-crop

---

## 🔧 2. Función Adaptadora en `api.py`

**Archivo**: `clip_admin_backend/app/blueprints/api.py`

**Ubicación**: Agregar después de `detect_image_category_with_centroids()` (~línea 1500)

```python
def detect_category_smart(image_data, client_id, confidence_threshold=0.2):
    """
    Detección inteligente de categoría con soporte multi-crop adaptativo.

    Modos:
    - 'off': Solo single-crop (tradicional)
    - 'auto': Multi-crop solo para categorías ambiguas (recomendado)
    - 'always': Multi-crop para todas las búsquedas

    Args:
        image_data: Datos binarios de imagen
        client_id: UUID del cliente
        confidence_threshold: Umbral mínimo de confianza

    Returns:
        tuple: (Category, float) - Categoría detectada y confianza

    Raises:
        Exception: Si ambos métodos fallan
    """
    from app.utils.system_config import SystemConfig

    # Cargar configuración de multi-crop
    config = SystemConfig()
    multicrop_config = config.get('multicrop_detection', {})

    enabled = multicrop_config.get('enabled', False)
    mode = multicrop_config.get('mode', 'auto')
    ambiguous = multicrop_config.get('ambiguous_categories', [])
    apply_exclusion = multicrop_config.get('apply_pair_exclusion', True)
    top_k = multicrop_config.get('top_k_results', 3)
    fallback = multicrop_config.get('fallback_to_single', True)

    railway_log(f"🎯 SMART DETECTION: enabled={enabled}, mode={mode}, fallback={fallback}")

    # Si multi-crop está deshabilitado, usar single-crop
    if not enabled or mode == 'off':
        railway_log("📍 Multi-crop DISABLED, usando single-crop")
        return detect_image_category_with_centroids(image_data, client_id, confidence_threshold)

    # Modo 'always': siempre usar multi-crop
    if mode == 'always':
        railway_log("🔄 Multi-crop ALWAYS mode")
        try:
            results = detect_categories_multi_crop(
                image_data,
                client_id,
                threshold=confidence_threshold,
                top_k=top_k,
                apply_pair_exclusion=apply_exclusion
            )

            if results and len(results) > 0:
                # Filtrar resultados que no pasen threshold o estén excluidos
                valid_results = [
                    r for r in results
                    if r.get('passes_threshold', True) and not r.get('excluded_pair', False)
                ]

                if valid_results:
                    best = valid_results[0]
                    category = Category.query.get(best['category_id'])
                    confidence = best['score']
                    railway_log(f"✅ Multi-crop SUCCESS: {category.name} (conf={confidence:.3f})")
                    return category, confidence

            # Si no hay resultados válidos, fallback
            if fallback:
                railway_log("⚠️ Multi-crop sin resultados, fallback a single-crop")
                return detect_image_category_with_centroids(image_data, client_id, confidence_threshold)
            else:
                railway_log("❌ Multi-crop sin resultados, fallback deshabilitado")
                return None, 0.0

        except Exception as e:
            railway_log(f"❌ Multi-crop ERROR: {e}")
            if fallback:
                railway_log("⚠️ Multi-crop falló, fallback a single-crop")
                return detect_image_category_with_centroids(image_data, client_id, confidence_threshold)
            else:
                raise

    # Modo 'auto': usar multi-crop solo para categorías ambiguas
    if mode == 'auto':
        railway_log("🔄 Multi-crop AUTO mode")

        # Primera pasada: detección rápida con single-crop
        detected_category, confidence = detect_image_category_with_centroids(
            image_data, client_id, confidence_threshold
        )

        if detected_category is None:
            railway_log("❌ Single-crop no detectó categoría")
            return None, 0.0

        # Verificar si la categoría detectada es ambigua
        is_ambiguous = any(
            amb.upper() in detected_category.name.upper()
            for amb in ambiguous
        )

        if not is_ambiguous:
            railway_log(f"✅ Categoría NO ambigua: {detected_category.name}, usando single-crop")
            return detected_category, confidence

        # Categoría ambigua: re-detectar con multi-crop
        railway_log(f"🔄 Categoría AMBIGUA detectada: {detected_category.name}, aplicando multi-crop")

        try:
            results = detect_categories_multi_crop(
                image_data,
                client_id,
                threshold=confidence_threshold,
                top_k=top_k,
                apply_pair_exclusion=apply_exclusion
            )

            if results and len(results) > 0:
                valid_results = [
                    r for r in results
                    if r.get('passes_threshold', True) and not r.get('excluded_pair', False)
                ]

                if valid_results:
                    best = valid_results[0]
                    multi_category = Category.query.get(best['category_id'])
                    multi_confidence = best['score']

                    # Logging comparativo
                    railway_log(f"📊 COMPARACIÓN:")
                    railway_log(f"   Single-crop: {detected_category.name} (conf={confidence:.3f})")
                    railway_log(f"   Multi-crop:  {multi_category.name} (conf={multi_confidence:.3f})")

                    # Si multi-crop cambió la categoría, loggear la razón
                    if multi_category.id != detected_category.id:
                        exclusion_reason = best.get('exclusion_reason', 'N/A')
                        railway_log(f"🔀 CAMBIO DE CATEGORÍA: {detected_category.name} → {multi_category.name} (reason={exclusion_reason})")

                    return multi_category, multi_confidence

            # Si multi-crop falla, mantener resultado single-crop
            railway_log("⚠️ Multi-crop sin resultados válidos, manteniendo single-crop")
            return detected_category, confidence

        except Exception as e:
            railway_log(f"❌ Multi-crop ERROR: {e}, manteniendo single-crop")
            return detected_category, confidence

    # Modo desconocido: fallback a single-crop
    railway_log(f"⚠️ Modo desconocido '{mode}', usando single-crop")
    return detect_image_category_with_centroids(image_data, client_id, confidence_threshold)
```

---

## 🔌 3. Integración en Endpoint `/api/search`

**Archivo**: `clip_admin_backend/app/blueprints/api.py`

**Ubicación**: Línea ~1931 (en función `visual_search()`, modo SINGLE)

**ANTES** (código actual):
```python
# ===== PASO 1: DETECCIÓN DE CATEGORÍA ESPECÍFICA =====
railway_log(f" LOG: INICIANDO DETECCIÓN DE CATEGORÍA ESPECÍFICA (SINGLE MODE)")

detected_category, category_confidence = detect_image_category_with_centroids(
    image_data,
    client.id,
    confidence_threshold=category_confidence_threshold  # Sensibilidad por cliente
)

railway_log(f" LOG: Resultado detección = {detected_category.name if detected_category else 'NULL'} (conf: {category_confidence:.3f})")
```

**DESPUÉS** (código modificado):
```python
# ===== PASO 1: DETECCIÓN DE CATEGORÍA ESPECÍFICA (SMART MODE) =====
railway_log(f" LOG: INICIANDO DETECCIÓN DE CATEGORÍA ESPECÍFICA (SMART MODE)")

detected_category, category_confidence = detect_category_smart(
    image_data,
    client.id,
    confidence_threshold=category_confidence_threshold  # Sensibilidad por cliente
)

railway_log(f" LOG: Resultado detección = {detected_category.name if detected_category else 'NULL'} (conf: {category_confidence:.3f})")
```

**Cambio**: Solo reemplazar `detect_image_category_with_centroids` por `detect_category_smart`. ¡Todo lo demás permanece igual!

---

## 🧪 4. Testing Local

### Test 1: Modo OFF (comportamiento actual)

**Configurar** en `system_config.json`:
```json
{
  "multicrop_detection": {
    "enabled": false
  }
}
```

**Ejecutar**:
```bash
cd clip_admin_backend
python app.py
```

**Probar** con demo-store:
```
1. Abrir http://localhost:5000/static/demo-store.html
2. Subir imagen de "Delantal Completo"
3. Verificar en logs: "📍 Multi-crop DISABLED, usando single-crop"
4. Medir latencia (debe ser ~500ms)
```

---

### Test 2: Modo AUTO (recomendado)

**Configurar** en `system_config.json`:
```json
{
  "multicrop_detection": {
    "enabled": true,
    "mode": "auto"
  }
}
```

**Probar**:

1. **Imagen ambigua** (Delantal Completo):
   - Logs esperados:
     ```
     🔄 Multi-crop AUTO mode
     ✅ Categoría NO ambigua: ... (si single-crop acierta)
     O
     🔄 Categoría AMBIGUA detectada: ...
     📊 COMPARACIÓN:
        Single-crop: MEDIO DELANTAL (conf=0.750)
        Multi-crop:  DELANTAL COMPLETO (conf=0.820)
     🔀 CAMBIO DE CATEGORÍA: MEDIO DELANTAL → DELANTAL COMPLETO (reason=torso_evidence)
     ```
   - Latencia: ~1.5s (2 detecciones)

2. **Imagen simple** (Remera):
   - Logs esperados:
     ```
     🔄 Multi-crop AUTO mode
     ✅ Categoría NO ambigua: Remera, usando single-crop
     ```
   - Latencia: ~500ms (1 detección)

---

### Test 3: Modo ALWAYS (máximo accuracy)

**Configurar** en `system_config.json`:
```json
{
  "multicrop_detection": {
    "enabled": true,
    "mode": "always"
  }
}
```

**Probar**:
- Todas las búsquedas deben mostrar: "🔄 Multi-crop ALWAYS mode"
- Latencia constante: ~1.5s

---

## 📊 5. Métricas y Logging

### Agregar logging extendido (opcional)

**Crear** archivo `clip_admin_backend/app/utils/multicrop_logger.py`:

```python
import json
from datetime import datetime
from pathlib import Path

class MultiCropLogger:
    """Logger para trackear performance de multi-crop vs single-crop"""

    def __init__(self, log_file='logs/multicrop_stats.jsonl'):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_detection(
        self,
        client_id,
        mode,
        single_category=None,
        single_confidence=0.0,
        multi_category=None,
        multi_confidence=0.0,
        latency_ms=0.0,
        category_changed=False,
        exclusion_reason=None
    ):
        """
        Log una detección para análisis posterior
        """
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'client_id': str(client_id),
            'mode': mode,
            'single': {
                'category': single_category,
                'confidence': single_confidence
            },
            'multi': {
                'category': multi_category,
                'confidence': multi_confidence
            },
            'latency_ms': latency_ms,
            'category_changed': category_changed,
            'exclusion_reason': exclusion_reason
        }

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def get_stats(self, client_id=None):
        """
        Calcular estadísticas de uso
        """
        if not self.log_file.exists():
            return {}

        entries = []
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                entry = json.loads(line)
                if client_id is None or entry['client_id'] == str(client_id):
                    entries.append(entry)

        if not entries:
            return {}

        total = len(entries)
        mode_auto = len([e for e in entries if e['mode'] == 'auto'])
        category_changes = len([e for e in entries if e['category_changed']])
        avg_latency = sum(e['latency_ms'] for e in entries) / total

        return {
            'total_detections': total,
            'mode_auto_count': mode_auto,
            'category_changes': category_changes,
            'category_change_rate': category_changes / total if total > 0 else 0,
            'avg_latency_ms': avg_latency
        }
```

**Usar** en `detect_category_smart()`:

```python
# Al inicio de la función
from app.utils.multicrop_logger import MultiCropLogger
logger = MultiCropLogger()
start_time = time.time()

# Al final (antes de return)
latency_ms = (time.time() - start_time) * 1000
logger.log_detection(
    client_id=client_id,
    mode=mode,
    single_category=detected_category.name if detected_category else None,
    single_confidence=confidence,
    multi_category=multi_category.name if multi_category else None,
    multi_confidence=multi_confidence,
    latency_ms=latency_ms,
    category_changed=(multi_category.id != detected_category.id) if (multi_category and detected_category) else False,
    exclusion_reason=best.get('exclusion_reason') if results else None
)
```

---

## 🚀 6. Deploy a Railway

### Variables de entorno

**Agregar** en Railway dashboard:

```bash
# Multicrop mode (off/auto/always)
MULTICROP_MODE=auto

# Enable/disable multicrop globally
MULTICROP_ENABLED=true

# Fallback to single-crop on error
MULTICROP_FALLBACK=true
```

### Leer variables de entorno en código

**Modificar** `detect_category_smart()` para leer env vars:

```python
import os

# Override config con variables de entorno (Railway)
mode = os.getenv('MULTICROP_MODE', multicrop_config.get('mode', 'auto'))
enabled = os.getenv('MULTICROP_ENABLED', str(enabled)).lower() == 'true'
fallback = os.getenv('MULTICROP_FALLBACK', str(fallback)).lower() == 'true'

railway_log(f"🎯 SMART DETECTION: mode={mode} (env override), enabled={enabled}, fallback={fallback}")
```

### Comando de deploy

```bash
# Commit cambios
git add .
git commit -m "feat: Integración multi-crop en producción (modo auto)"

# Tag de release
git tag -a v2.5.0-multicrop-production -m "v2.5.0 - Multi-crop detection integrada en /api/search con modo adaptativo (12 Nov 2025)"

# Push a Railway (auto-deploy)
git push origin main
git push origin v2.5.0-multicrop-production
```

---

## 📝 7. Checklist de Implementación

### Fase 1: Preparación
- [ ] Actualizar `system_config.json` con sección `multicrop_detection`
- [ ] Agregar función `detect_category_smart()` en `api.py`
- [ ] Reemplazar llamada en línea ~1931 de `api.py`
- [ ] (Opcional) Crear `MultiCropLogger` para métricas

### Fase 2: Testing Local
- [ ] Test modo `off`: Verificar comportamiento idéntico a producción actual
- [ ] Test modo `auto`: Probar con imagen ambigua (Delantal Completo)
- [ ] Test modo `auto`: Probar con imagen simple (Remera)
- [ ] Test modo `always`: Verificar latencia aceptable (<2s)
- [ ] Validar contrato API con `demo-store.html`

### Fase 3: Deploy Railway
- [ ] Setear variables `MULTICROP_MODE=auto`, `MULTICROP_ENABLED=true`
- [ ] Commit y tag `v2.5.0-multicrop-production`
- [ ] Push a Railway
- [ ] Smoke testing: 10 búsquedas variadas
- [ ] Verificar logs de Railway

### Fase 4: Monitoreo
- [ ] Trackear latencia promedio (Railway metrics)
- [ ] Analizar `multicrop_stats.jsonl` (tasa de cambio de categoría)
- [ ] Ajustar `ambiguous_categories` si es necesario
- [ ] Considerar cambio a `always` si latencia aceptable

---

## 🔍 Troubleshooting

### Problema: Multi-crop siempre usa single-crop
**Causa**: `enabled=false` o `mode='off'`
**Solución**: Verificar `system_config.json` y variables de entorno Railway

### Problema: Latencia > 3s
**Causa**: Todos los requests usan multi-crop (`mode='always'`)
**Solución**: Cambiar a `mode='auto'` para reducir latencia promedio

### Problema: Categoría incorrecta con multi-crop
**Causa**: Pesos regionales mal calibrados o pair exclusion demasiado agresivo
**Solución**: Ajustar `region_weights` en `detect_categories_multi_crop()` o revisar parámetros de exclusión

### Problema: Errores de import `detect_categories_multi_crop`
**Causa**: Función está en `embeddings.py`, necesita import
**Solución**: Agregar en `api.py`:
```python
from app.blueprints.embeddings import detect_categories_multi_crop
```

---

**Fecha**: 12 Noviembre 2025
**Versión**: v2.4.0 → v2.5.0
**Autor**: GitHub Copilot + Usuario
**Estado**: ✅ Código listo para implementación
