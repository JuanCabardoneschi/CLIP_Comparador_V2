# 🚀 Deployment Railway - Optimización de Costos

**Fecha:** 27 de Octubre, 2025
**Objetivo:** Reducir costos de $50+/mes a ~$15-20/mes (60-70% ahorro)

---

## ✅ CAMBIOS IMPLEMENTADOS (Listos para Deploy)

### 1. Lazy Loading de CLIP
- **Antes:** Modelo cargado al inicio (600MB RAM permanente)
- **Ahora:** Modelo carga solo cuando se hace búsqueda
- **Auto-cleanup:** Libera memoria después de 5 min sin uso
- **Ahorro:** ~500-600MB RAM cuando idle

### 2. Gunicorn (Production Server)
- **Antes:** `python app.py` (desarrollo)
- **Ahora:** Gunicorn 2 workers + 2 threads
- **Beneficios:** Mejor gestión recursos, logs optimizados

### 3. Imports Optimizados
- **Antes:** torch/transformers cargan al inicio
- **Ahora:** Lazy imports (solo cuando se necesitan)
- **Ahorro:** ~200MB RAM al arrancar

---

## 🔧 VARIABLES DE ENTORNO RAILWAY

**IMPORTANTE:** Configurar estas variables en Railway:

```bash
# Deshabilitar precarga de CLIP (CRÍTICO)
CLIP_PRELOAD=false

# Tiempo antes de liberar CLIP (300s = 5 minutos)
CLIP_IDLE_TIMEOUT=300
```

### Cómo Configurar en Railway:

1. Ve a tu proyecto en Railway
2. Click en "Variables" en el panel izquierdo
3. Agregar estas 2 variables:
   - `CLIP_PRELOAD` = `false`
   - `CLIP_IDLE_TIMEOUT` = `300`
4. Deploy automático se iniciará

---

## 📊 MÉTRICAS A MONITOREAR

Después del deploy, revisar en Railway Dashboard:

### Antes del Deploy (Actual)
- RAM Avg: ~1000-1200 MB
- RAM Peak: ~1400 MB
- Costo: $50+/mes

### Después del Deploy (Esperado)
- RAM Idle: ~400-500 MB (60% reducción ✅)
- RAM Búsqueda: ~900-1000 MB (temporal, luego libera)
- Costo: ~$15-20/mes (70% ahorro ✅)

### Qué Observar (primeras 24 horas)

**Métricas Railway:**
1. **Memory Usage:** Debería bajar a 400-500MB idle
2. **Logs:** Buscar estos mensajes:
   ```
   🔄 Cargando modelo CLIP (lazy loading)...
   ✅ Modelo CLIP cargado exitosamente
   🧹 Liberando CLIP (idle 300s > 300s)...
   ✅ Memoria CLIP liberada (~500MB recuperados)
   ```

**Timeline Esperado:**
- 0-5 min: Servicio arranca (400MB RAM)
- Primera búsqueda: Carga CLIP (+600MB = 1000MB)
- 5 min después: Libera CLIP (-600MB = 400MB)
- Siguiente búsqueda: Recarga CLIP (ciclo se repite)

---

## 🚦 CHECKLIST DE DEPLOYMENT

### Pre-Deploy
- [x] Código modificado (embeddings.py)
- [x] Gunicorn agregado (requirements.txt)
- [x] Procfile actualizado
- [x] Variables documentadas (.env.example)

### Durante Deploy
- [ ] Configurar `CLIP_PRELOAD=false` en Railway
- [ ] Configurar `CLIP_IDLE_TIMEOUT=300` en Railway
- [ ] Commit y push cambios a GitHub
- [ ] Railway detecta cambios y redeploy automático

### Post-Deploy (Primeras 2 horas)
- [ ] Verificar servicio arrancó correctamente (healthcheck OK)
- [ ] Revisar logs Railway (buscar "lazy loading")
- [ ] Hacer 1 búsqueda de prueba (verificar funciona)
- [ ] Esperar 5 min sin uso (verificar cleanup en logs)
- [ ] Revisar métricas RAM (debería bajar a ~400MB)

### Post-Deploy (24 horas)
- [ ] Comparar RAM promedio antes vs después
- [ ] Verificar búsquedas funcionan normalmente
- [ ] Confirmar no hay errores en logs
- [ ] Calcular proyección costo mensual

---

## 🐛 TROUBLESHOOTING

### Si RAM no baja después de 5 min:
```bash
# Revisar logs Railway - buscar:
"🧹 Liberando CLIP (idle..."

# Si NO aparece, verificar:
1. CLIP_IDLE_TIMEOUT está configurado
2. Thread de cleanup arrancó ("Thread de auto-cleanup CLIP iniciado")
3. No hay búsquedas constantes impidiendo idle
```

### Si búsquedas fallan:
```bash
# Revisar logs Railway - buscar:
"🔄 Cargando modelo CLIP (lazy loading)..."
"✅ Modelo CLIP cargado exitosamente"

# Si falla carga, puede ser timeout
# Aumentar timeout en Procfile si necesario
```

### Si el servicio no arranca:
```bash
# Verificar logs de Gunicorn
# Posibles causas:
1. Falta gunicorn en requirements.txt
2. Sintaxis Procfile incorrecta
3. Puerto $PORT no configurado (Railway lo hace automático)
```

---

## 📈 RESULTADOS ESPERADOS

### Escenario Típico (10 búsquedas/día)

**Timeline diario:**
- 00:00-09:00: Idle (400MB RAM)
- 09:15: Búsqueda #1 → Carga CLIP (1000MB)
- 09:20: Idle 5 min → Libera CLIP (400MB)
- 12:30: Búsqueda #2 → Recarga CLIP (1000MB)
- 12:35: Idle 5 min → Libera CLIP (400MB)
- ... (ciclo se repite)

**Promedio RAM/día:** ~450-500MB (vs 1000MB actual)
**Ahorro mensual:** ~$30-35 USD

---

## 🎯 SI NECESITAS MÁS OPTIMIZACIÓN (Fase 2)

Si después de 1 semana los costos siguen altos:

1. **Cache embeddings en Redis** (ahorra recomputar)
2. **Cuantización CLIP a int8** (reduce 50% tamaño modelo)
3. **Auto-sleep Railway** (duerme servicio si no hay requests)

Ver [docs/RAILWAY_COST_OPTIMIZATION.md](./RAILWAY_COST_OPTIMIZATION.md) para Fases 2 y 3.

---

## 📞 SIGUIENTES PASOS

1. **Hoy:** Deploy cambios a Railway
2. **Mañana:** Revisar métricas primeras 24h
3. **1 semana:** Comparar costos actual vs anterior
4. **Si necesario:** Implementar Fase 2

**Cualquier duda, revisar logs y compartirlos para análisis.**

---

**Última actualización:** 27 de Octubre, 2025
