# Migración a CLIP ViT-L/14

**Fecha:** 11 Noviembre 2025
**Estado:** ✅ Implementado, listo para test

---

## 🎯 Objetivo

Mejorar discriminación entre categorías visualmente similares (ej: Delantal Completo vs Medio Delantal) migrando de **CLIP ViT-B/16 (512D)** a **CLIP ViT-L/14 (768D)**.

---

## 📊 Comparación de Modelos

| Característica | ViT-B/16 (Anterior) | ViT-L/14 (Nuevo) | Mejora |
|----------------|---------------------|------------------|--------|
| **Embedding Dim** | 512D | 768D | +50% |
| **Parámetros** | 150M | 428M | +185% |
| **Tamaño RAM** | ~1 GB | ~3 GB | +200% |
| **ImageNet Acc** | 76.2% | 82.1% | +5.9pp |
| **Velocidad CPU** | ~1s/img | ~2s/img | -50% |
| **Scores Esperados** | 32-50% | 65-75%+ | +40-50% |

---

## ✅ Cambios Implementados

### 1. Configuración del Sistema
- ✅ `system_config.json` → `model_name: "ViT-L/14"`
- ✅ `embeddings.py` → Soporte dinámico 512D/768D
- ✅ `requirements.txt` → Nota Railway Pro requerido

### 2. Scripts de Migración
- ✅ `migrate_to_vitl14.py` → Regenerar embeddings existentes
- ✅ `test_vitl14_vs_vitb16.py` → Comparación A/B en misma imagen

### 3. Compatibilidad DB
- ✅ `Image.clip_embedding` → JSON flexible (soporta cualquier dimensión)
- ✅ `Category.centroid_embedding` → Idem
- ⚠️ **NO requiere migración Alembic** (almacenamiento JSON, no pgvector fijo)

---

## 🚀 Pasos para Migración

### Paso 1: Test Comparativo (Local)

```bash
# Descargar imagen de prueba del delantal problemático
# Ejecutar test A/B
python test_vitl14_vs_vitb16.py test_delantal.jpg --category "MEDIO DELANTAL" --client goody-store
```

**Objetivo:** Verificar que ViT-L/14 puntúa >65% en categoría correcta.

---

### Paso 2: Dry-Run Migración

```bash
# Simular migración (NO hace cambios)
python migrate_to_vitl14.py --client goody-store --dry-run
```

**Verifica:**
- ✅ Cantidad de imágenes a migrar
- ✅ Dimensión actual (512D → 768D)
- ✅ Backup automático funciona

---

### Paso 3: Backup Manual (Crítico)

```bash
# Backup local
python local_db_tool.py backup

# Backup Railway (si aplica)
python railway_db_tool.py backup
```

**Guardar archivos `.sql` en lugar seguro.**

---

### Paso 4: Migración Real

```bash
# Migrar un cliente
python migrate_to_vitl14.py --client goody-store

# O migrar todos
python migrate_to_vitl14.py --client all
```

**Tiempo estimado:** ~2-5 min por cada 100 imágenes.

**Proceso:**
1. Backup automático
2. Itera todas las imágenes del cliente
3. Regenera embedding 768D con ViT-L/14
4. Actualiza `Image.clip_embedding`
5. Recalcula centroides de categorías
6. Commit cada 50 imágenes (seguridad)

---

### Paso 5: Test Multicrop (Verificación)

```bash
cd clip_admin_backend
python app.py
```

1. Abrir: http://localhost:5000/embeddings/test/multicrop
2. Subir imagen delantal problemático
3. Verificar scores >65% en categoría correcta
4. Comparar con logs anteriores (ViT-B/16 ~50%)

---

## 🏗️ Railway Deployment

### Requisitos

**Railway Pro Plan:** $20/mes
**Razón:** ViT-L/14 requiere ~3GB RAM + Flask (~1GB) = 4GB mínimo

### Variables de Entorno

Verificar en Railway:

```env
# Ya configurado en system_config.json
# Pero puede overridearse vía env vars si necesario
CLIP_MODEL_NAME=ViT-L/14
CLIP_IDLE_TIMEOUT_MINUTES=30
```

### Deploy Steps

1. **Upgrade Railway Plan**
   ```bash
   # En dashboard Railway: Upgrade to Pro
   ```

2. **Push código**
   ```bash
   git add .
   git commit -m "feat: Migrate to CLIP ViT-L/14 (768D)"
   git push origin main
   ```

3. **Migrar DB producción**
   ```bash
   # Desde local con conexión Railway
   python migrate_to_vitl14.py --client all
   ```

4. **Verificar health**
   - Logs Railway: Buscar "✅ Modelo CLIP ViT-L/14 cargado"
   - Test endpoint: `curl https://tu-app.railway.app/api/health`

---

## 📈 Métricas Esperadas (Post-Migración)

### Scores de Detección

| Caso | ViT-B/16 (Antes) | ViT-L/14 (Después) | Objetivo |
|------|------------------|-------------------|----------|
| **Delantal Completo** | 32% (tie) | >65% | ✅ |
| **Medio Delantal** | 31% (tie) | >65% | ✅ |
| **Casaca Chef** | 35% | >70% | ✅ |
| **Gorra** | 15% | >60% | ✅ |

### Performance

| Métrica | ViT-B/16 | ViT-L/14 | Impacto |
|---------|----------|----------|---------|
| **Latencia/query** | ~1.5s | ~3s | ⚠️ Aceptable |
| **RAM usage** | ~1.5GB | ~4GB | ⚠️ Requiere Pro |
| **Costo Railway** | $5/mes | $20/mes | 💰 +$15/mes |

---

## 🔄 Rollback Plan

Si ViT-L/14 no mejora suficiente o causa problemas:

### Rollback Rápido

```bash
# 1. Cambiar configuración
# Editar system_config.json:
{
  "clip": {
    "model_name": "openai/clip-vit-base-patch16"
  }
}

# 2. Reiniciar servidor
# El modelo se descarga automáticamente en próxima request

# 3. Restaurar embeddings desde backup
python local_db_tool.py restore backups/pre_vitl14_migration_TIMESTAMP.sql
```

**Tiempo rollback:** ~5 minutos

---

## 🎯 Próximos Pasos (Si ViT-L/14 No Alcanza)

### Plan B: EVA-CLIP ViT-H/14

Si ViT-L/14 puntúa <65%:

- **Modelo:** `laion/CLIP-ViT-H-14-laion2B-s32B-b79K`
- **Embedding:** 1024D
- **RAM:** ~8 GB
- **Railway:** Pro Plan OK
- **Scores esperados:** 75-85%

### Plan C: Fine-Tuning

- Entrenar ViT-L/14 con dataset propio de delantales
- Requiere ~500 imágenes etiquetadas
- Mejora esperada: +10-15pp adicionales

---

## 📝 Checklist Pre-Deploy

- [ ] Test local A/B completado (ViT-L/14 > ViT-B/16)
- [ ] Backup manual creado y verificado
- [ ] Dry-run migración exitoso
- [ ] Migración local completada sin errores
- [ ] Test multicrop local muestra >65% scores
- [ ] Railway Pro Plan activado
- [ ] Git commit + push
- [ ] Migración Railway DB completada
- [ ] Health check producción OK
- [ ] Test API `/api/search` con imagen real

---

## 🐛 Troubleshooting

### Error: "Model too large for memory"

**Causa:** Railway Hobby Plan (512MB RAM)
**Solución:** Upgrade a Pro Plan ($20/mes)

### Error: "No module named transformers"

**Causa:** Dependencias no instaladas
**Solución:**
```bash
pip install -r requirements.txt
```

### Scores siguen bajos (<60%)

**Causa:** Modelo no adecuado para dominio
**Solución:** Evaluar EVA-CLIP o fine-tuning

### Migración se traba

**Causa:** Cloudinary timeout en imágenes pesadas
**Solución:** Reiniciar desde última imagen procesada (commit cada 50)

---

## 📚 Referencias

- [CLIP Paper](https://arxiv.org/abs/2103.00020)
- [OpenAI CLIP Models](https://github.com/openai/CLIP)
- [Hugging Face Transformers](https://huggingface.co/docs/transformers)
- [Railway Docs](https://docs.railway.app)

---

**Autor:** Sistema CLIP Comparador V2
**Última actualización:** 11 Nov 2025
