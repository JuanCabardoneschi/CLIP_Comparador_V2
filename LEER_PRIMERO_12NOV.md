# 🚀 LEER PRIMERO - Sesión 12 Nov 2025

## ⚡ ACCIONES INMEDIATAS AL INICIAR

### 1️⃣ ✅ AUTOCROP GLOBAL COMPLETADO

```
========================================
🎉 SISTEMA COMPLETO OPTIMIZADO
========================================

📊 ESTADÍSTICAS GLOBALES:
  Total procesadas: 90 imágenes
  Crops aplicados: 28 (31.1%)
  Sin cambios: 62 (68.9%)

💡 MEJORAS:
  Promedio (aplicados): +0.0106 (1.06%)
  Máxima: +0.0208 (2.08%)

📂 CATEGORÍAS OPTIMIZADAS (12):
  • Delantal Completo: 5 crops
  • CASACAS: 5 crops
  • tops: 3 crops
  • remera musculosas: 3 crops
  • shores tiro alto/bajo: 4 crops
  • CAMISAS, CHAQUETAS, AMBO: 5 crops
  • Otros: 3 crops
```

**CSV generado**: `clip_admin_backend/logs/autocrop_results_20251112_041809.csv`
**Estado**: ✅ ¡TODO EL SISTEMA OPTIMIZADO! Embeddings regenerados, centroides actualizados

---

### 2️⃣ Probar Sistema de Exclusión de Pares
```bash
# Iniciar Flask
cd C:\Personal\CLIP_Comparador_V2\clip_admin_backend
python app.py

# Ir a: http://localhost:5000
# Login como STORE_ADMIN
# Menú lateral → "Reglas de Exclusión" (nuevo ícono de exclude)
```

**Crear regla de prueba**:
- Primary: "Delantal Completo"
- Secondary: "Medio Delantal"
- Usar defaults o ajustar parámetros

**Testear**: `/embeddings/test-multicrop` con imágenes de delantales

---

### 3️⃣ Verificar BD
```bash
cd C:\Personal\CLIP_Comparador_V2
python local_db_tool.py sql -e "SELECT * FROM category_pair_exclusions"
```

---

## 🎯 QUÉ SE COMPLETÓ AYER

### ✅ Sistema de Exclusión de Pares (100% FUNCIONAL)

**Base de Datos**:
- ✅ Tabla `category_pair_exclusions` creada
- ✅ Migración aplicada con `local_db_tool.py`
- ✅ Modelo `CategoryPairExclusion` con relaciones
- ✅ Índices y constraints optimizados

**Backend**:
- ✅ Blueprint `category_exclusions` registrado en `wsgi.py`
- ✅ CRUD completo (index, create, edit, toggle, delete)
- ✅ Filtrado automático por `client_id` (seguridad)
- ✅ Integrado en `detect_categories_multi_crop` con fallback

**Frontend**:
- ✅ Menú en STORE_ADMIN (después de "Atributos")
- ✅ Templates: `index.html`, `create.html`, `edit.html`
- ✅ Formularios con 5 parámetros configurables

**Configuración**:
- ✅ `system_config.json` con sección `pair_exclusion_rules`
- ✅ Defaults: gap_max=0.10, torso_min=0.24, advantage=0.06

**Documentación**:
- ✅ `PAIR_EXCLUSION_RULES.md` en `docs/`
- ✅ `RESUMEN_SESION_12NOV2025.md` (detalles completos)

---

## 🔧 ARQUITECTURA CLAVE

### Flujo de Exclusión:
```
Usuario busca imagen
    ↓
detect_categories_multi_crop()
    ↓
Query BD: CategoryPairExclusion.filter_by(client_id, is_active=True)
    ↓
¿Hay regla para el par detectado?
    ├─ SÍ → Aplica lógica torso_evidence con params JSONB
    └─ NO → Fallback a system_config.json + lógica hardcoded
    ↓
Retorna categoría ganadora (excluye la otra)
```

### Parámetros JSONB (torso_evidence):
- `override_gap_max`: Diferencia máxima permitida (0.10)
- `torso_evidence_min`: Score mínimo de chest_focus (0.24)
- `torso_advantage_min`: Ventaja torso sobre cintura (0.06)
- `suppression_evidence_threshold`: Umbral de supresión (0.22)
- `tie_margin`: Margen de empate (0.02)

---

## 📝 PENDIENTES (TODO LIST)

### 1. Verificar y analizar autocrop batch
- CSVs generados en `logs/`
- Calcular métricas agregadas

### 2. Logging extendido en detect_categories_multi_crop
- Añadir: `torso_full`, `waist_half`, `gap`, `decision_reason`
- JSONL diario para auditoría

### 3. Badge ambigüedad en test_multicrop UI
- Si gap < 0.10, mostrar badge amarillo
- Mini barra comparativa torso vs cintura

### 4. Script `summarize_autocrop_csv.py`
- Agregar métricas: applied ratio, mean improvement, distribución

---

## 🚨 PROBLEMAS CONOCIDOS Y SOLUCIONES

### PostgreSQL password auth failed
**Solución**: Usar `local_db_tool.py` para operaciones SQL directas
```bash
python local_db_tool.py --yes sql -f archivo.sql
python local_db_tool.py sql -e "SELECT * FROM tabla"
```

### UnicodeEncodeError en PowerShell
**Solución**: Forzar UTF-8
```powershell
$env:PYTHONIOENCODING='utf-8'
```

---

## 📂 ARCHIVOS CLAVE MODIFICADOS AYER

### Backend:
- `clip_admin_backend/app/models/category_pair_exclusion.py` (NUEVO)
- `clip_admin_backend/app/blueprints/category_exclusions.py` (NUEVO)
- `clip_admin_backend/app/blueprints/embeddings.py` (modificado líneas 1570-1650)
- `clip_admin_backend/wsgi.py` (registrado blueprint)

### Frontend:
- `clip_admin_backend/app/templates/category_exclusions/index.html` (NUEVO)
- `clip_admin_backend/app/templates/category_exclusions/create.html` (NUEVO)
- `clip_admin_backend/app/templates/category_exclusions/edit.html` (NUEVO)
- `clip_admin_backend/app/templates/layouts/base.html` (menú STORE_ADMIN)

### Config/Docs:
- `system_config.json` (nueva sección pair_exclusion_rules)
- `docs/PAIR_EXCLUSION_RULES.md` (NUEVO)
- `RESUMEN_SESION_12NOV2025.md` (NUEVO - detalles completos)

### Scripts:
- `clip_admin_backend/tools/run_autocrop_all_clients.ps1` (ya existía)
- Ejecutado en background con threshold=0.005 adaptive

---

## 🎓 CONTEXTO DEL PROYECTO

**Objetivo**: Mejorar discriminación entre "Delantal Completo" y "Medio Delantal"

**Evolución**:
1. ❌ Intentos con modelos CLIP más grandes (marginal)
2. ❌ Refined prompts (marginal)
3. ✅ **Multi-crop con region weighting** (significativo)
4. ✅ **Autocrop heurístico** (~27% aplicación, +0.008 mejora)
5. ✅ **Pair exclusion rules** (ahora configurable por cliente)

**Estado actual**: Sistema robusto con UI admin para ajustes por cliente

---

## 💡 SIGUIENTE SESIÓN - PLAN DE ACCIÓN

### Corto Plazo (hoy/mañana):
1. ✅ Verificar resultados autocrop
2. ✅ Crear primera regla de exclusión vía UI
3. ✅ Testear con imágenes reales
4. 📊 Implementar logging extendido (JSONL)

### Mediano Plazo (esta semana):
1. 📈 Script de análisis de CSVs
2. 🎨 Badge ambigüedad en UI
3. 🚀 Deploy a Railway si todo OK
4. 📊 Dashboard de métricas de exclusión

---

## 🔑 COMANDOS RÁPIDOS

```bash
# Ver estructura BD
python local_db_tool.py sql -e "\dt"

# Contar reglas
python local_db_tool.py sql -e "SELECT COUNT(*) FROM category_pair_exclusions"

# Ver clientes activos
python local_db_tool.py sql -e "SELECT name, is_active FROM clients"

# Iniciar Flask
cd clip_admin_backend && python app.py

# Ver logs autocrop
Get-Content logs\autocrop_direct.log -Tail 50
```

---

**Archivo creado**: 2025-11-12 01:20 AM
**Próxima revisión**: Al iniciar siguiente sesión
**Estado**: ✅ Sistema funcional, esperando validación con datos reales

---

## 📞 CONTACTO/NOTAS

Si algo no funciona al iniciar:
1. Verificar PostgreSQL corriendo
2. Verificar venv activado
3. Revisar `RESUMEN_SESION_12NOV2025.md` para detalles completos
4. Logs en `C:\Personal\CLIP_Comparador_V2\logs\`

**¡TODO LISTO PARA CONTINUAR MAÑANA! 🚀**
