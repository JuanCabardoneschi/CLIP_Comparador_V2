# Plan de Optimización de Costos Railway - CLIP Comparador V2

**Fecha:** 27 de Octubre, 2025
**Objetivo:** Reducir consumo de RAM de >50 USD/mes a <10 USD/mes en Railway Hobby Plan

---

## 📊 Diagnóstico del Problema

### Consumo Actual Estimado
- **RAM Base Flask:** ~150-200 MB
- **CLIP Model (ViT-B/16):** ~500-600 MB (cargado permanentemente)
- **PyTorch + Transformers:** ~200-300 MB
- **PostgreSQL Connections + Redis:** ~50-100 MB
- **TOTAL:** ~900-1200 MB RAM constante

### Costos Railway Hobby Plan
- **Incluido:** 512 MB RAM / $5 mes
- **Extra RAM:** $10/GB adicional/mes
- **Consumo actual:** ~1 GB = $5 base + ~$10 extra = **$15-20/mes solo RAM**
- **CPU + Red + Disco:** Adicionales = **Total $50+/mes**

### Causas Principales
1. ✅ **CLIP precargado 24/7:** Modelo cargado al inicio, nunca liberado
2. ✅ **Flask dev server:** Sin optimización de workers
3. ✅ **Sin gestión de idle:** Servicio activo aunque nadie lo use
4. ✅ **Torch sin optimizar:** Sin cuantización ni cache eficiente

---

## 🎯 Plan de Optimización (3 Fases)

### ⚡ FASE 1: Quick Wins (Reducción 40-50%)
**Tiempo:** 2-3 horas
**Reducción esperada:** 400-500 MB RAM
**Ahorro estimado:** $15-20/mes

#### 1.1 Lazy Loading de CLIP (CRÍTICO)
- ✅ Cambiar precarga a lazy loading
- ✅ Cargar modelo solo cuando se hace búsqueda
- ✅ Liberar memoria después de 5 min sin uso
- ✅ Cache embeddings en Redis para evitar recargas

**Implementación:**
```python
# app.py - DESHABILITAR precarga
CLIP_PRELOAD=false  # Lazy loading siempre

# embeddings.py - Auto-cleanup
def get_clip_model():
    global _clip_model, _clip_processor, _last_used

    # Cargar solo si no existe
    if _clip_model is None:
        print("🔄 Cargando CLIP (lazy)...")
        _clip_model = CLIPModel.from_pretrained(...)
        _clip_processor = CLIPProcessor.from_pretrained(...)

    _last_used = time.time()
    return _clip_model, _clip_processor

# Cleanup automático en background
def cleanup_clip_if_idle():
    global _clip_model, _clip_processor
    if time.time() - _last_used > 300:  # 5 min idle
        print("🧹 Liberando CLIP (idle 5 min)...")
        _clip_model = None
        _clip_processor = None
        gc.collect()
```

#### 1.2 Usar Gunicorn en producción
- ✅ Reemplazar `python app.py` por Gunicorn
- ✅ 2 workers (en lugar de 1 proceso)
- ✅ Timeout optimizado para Railway

**Implementación:**
```dockerfile
# Procfile
web: cd clip_admin_backend && gunicorn --workers 2 --threads 2 --timeout 120 --bind 0.0.0.0:$PORT "app:create_app()"

# requirements.txt
gunicorn==21.2.0
```

#### 1.3 Optimizar imports
- ✅ Imports condicionales de torch/transformers
- ✅ Solo cargar cuando se necesita

---

### 🚀 FASE 2: Optimizaciones Avanzadas (Reducción 20-30%)
**Tiempo:** 4-6 horas
**Reducción esperada:** 200-300 MB RAM adicional
**Ahorro estimado:** $5-10/mes adicional

#### 2.1 Cache de embeddings en Redis
- ✅ Cachear embeddings de productos en Redis
- ✅ TTL largo (7 días) para embeddings
- ✅ Invalidar solo cuando cambia imagen

**Implementación:**
```python
def get_or_generate_embedding(image_url, product_id):
    cache_key = f"emb:{product_id}:{hash(image_url)}"

    # Intentar desde Redis
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Generar solo si no existe
    embedding = generate_clip_embedding(image_url)

    # Guardar en Redis (7 días)
    redis_client.setex(cache_key, 604800, json.dumps(embedding))

    return embedding
```

#### 2.2 Cuantización del modelo CLIP
- ✅ Convertir modelo a int8 (reduce 50% tamaño)
- ✅ Pérdida mínima de precisión (<2%)

```python
import torch.quantization

def get_clip_model():
    if _clip_model is None:
        model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16")

        # Cuantizar a int8
        model = torch.quantization.quantize_dynamic(
            model, {torch.nn.Linear}, dtype=torch.qint8
        )

        _clip_model = model
    return _clip_model
```

#### 2.3 Batch processing de embeddings
- ✅ Procesar múltiples imágenes en lote
- ✅ Liberar memoria entre batches

---

### 💰 FASE 3: Arquitectura Serverless (Reducción 60-70%)
**Tiempo:** 1-2 días
**Reducción esperada:** Pagar solo por uso real
**Ahorro estimado:** $30-40/mes

#### 3.1 Separar CLIP en servicio independiente
- ✅ Flask Admin (siempre activo, ligero)
- ✅ CLIP Worker (solo activo cuando hay búsquedas)

**Opción A: Railway Cron Jobs**
```yaml
# railway.toml
[deploy]
healthcheckPath = "/"

[cron.cleanup-clip]
schedule = "*/10 * * * *"  # Cada 10 min
command = "python cleanup_clip.py"
```

**Opción B: Modal Labs / Hugging Face Inference**
- Usar servicio serverless para CLIP
- Pagar solo por inferencia
- ~$0.0001 por búsqueda

#### 3.2 Auto-sleep en Railway
- ✅ Configurar inactividad para dormir servicio
- ✅ Wake-up automático en primer request

```yaml
# railway.toml
[deploy]
sleepAfterInactivity = 300  # 5 min sin requests = sleep
```

---

## 📈 Resultados Esperados

### Sin Optimización (Actual)
- RAM: ~1000-1200 MB
- Costo: $50+/mes
- Uptime: 100%

### Con Fase 1 (Quick Wins)
- RAM: ~500-700 MB
- Costo: ~$15-20/mes (-60%)
- Uptime: 100%

### Con Fase 1 + 2
- RAM: ~300-400 MB
- Costo: ~$8-12/mes (-80%)
- Uptime: 100%

### Con Fase 1 + 2 + 3 (Serverless)
- RAM: ~150-200 MB (solo admin)
- Costo: ~$5-8/mes (-90%)
- Uptime: 95% (auto-sleep)

---

## 🛠️ Datos que Necesito de Railway

Para afinar las optimizaciones, necesito que me proporciones:

### 1. Métricas Actuales (Panel Railway)
- **RAM Usage:** Promedio y picos
- **CPU Usage:** Promedio y picos
- **Network:** Inbound/Outbound traffic
- **Requests/día:** Cuántas búsquedas se hacen realmente

### 2. Logs de Railway
- Última semana de logs (ver frecuencia de búsquedas)
- Tiempo de respuesta promedio
- Errores por falta de recursos

### 3. Uso Real
- **Búsquedas/día:** ¿Cuántas búsquedas se hacen?
- **Horas pico:** ¿A qué hora hay más tráfico?
- **Clientes activos:** ¿Cuántos clientes usan el sistema?

### 4. Configuración Railway
- Screenshot del dashboard de métricas
- Variables de entorno actuales
- Plan actual (Hobby / Pro)

---

## 🚦 Prioridades Recomendadas

### Empezar YA (Hoy)
1. ✅ **Lazy loading CLIP** (CRÍTICO - 40% reducción)
2. ✅ **Gunicorn** (10-15% reducción)
3. ✅ **Deshabilitar precarga** (CLIP_PRELOAD=false)

### Esta Semana
4. ✅ **Cache Redis embeddings** (15-20% reducción)
5. ✅ **Cuantización modelo** (20-25% reducción)

### Próxima Semana (si aún es necesario)
6. ✅ **Arquitectura serverless** (60% reducción)

---

## 📝 Checklist de Implementación

### Fase 1: Quick Wins
- [ ] Cambiar `CLIP_PRELOAD=false` en Railway
- [ ] Implementar auto-cleanup de CLIP (5 min idle)
- [ ] Agregar Gunicorn a requirements.txt
- [ ] Actualizar Procfile con Gunicorn
- [ ] Deploy y verificar RAM después de 1 hora

### Fase 2: Optimizaciones
- [ ] Implementar cache Redis para embeddings
- [ ] Cuantizar modelo CLIP a int8
- [ ] Batch processing de imágenes
- [ ] Deploy y verificar RAM después de 24 horas

### Fase 3: Serverless (Opcional)
- [ ] Evaluar costos CLIP serverless (Modal/HF)
- [ ] Separar worker de CLIP
- [ ] Configurar auto-sleep Railway
- [ ] Migrar a arquitectura híbrida

---

## 💡 Próximos Pasos

1. **Compárteme los datos de Railway** (métricas, logs)
2. **Te implemento Fase 1** (lazy loading + Gunicorn)
3. **Desplegamos y medimos** (comparar antes/después)
4. **Si necesario:** Fase 2 y 3

**Estimación:** Con solo Fase 1 deberías bajar de $50 a ~$15-20/mes.

---

**Última actualización:** 27 de Octubre, 2025
