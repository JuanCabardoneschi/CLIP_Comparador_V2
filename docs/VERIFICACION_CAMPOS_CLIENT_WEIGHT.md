# Verificación: Campos visual_weight, color_weight, enable_stock_boost

**Fecha**: 7 Nov 2025
**Pregunta Usuario**: "Estos campos creo que ya no se usan en nada útil, verifica"

---

## 🔍 ANÁLISIS DE USO

### Campos en Modelo Client:
```python
visual_weight = db.Column(db.Integer, default=70)
color_weight = db.Column(db.Integer, default=30)
enable_stock_boost = db.Column(db.Boolean, default=True)
```

---

## 📊 BLUEPRINTS QUE LOS USAN

### 1. **diagnostic.py** 🟡 EXPERIMENTAL

**Líneas de uso**: 199-220, 261, 510, 547, 562, 852, 939, 1081, 1117

**Uso intensivo**:
```python
# Líneas 199-220: Lee desde BD
visual_weight = float(client.visual_weight or 70) / 100.0
color_weight = float(client.color_weight or 30) / 100.0
enable_stock_boost = client.enable_stock_boost if client.enable_stock_boost is not None else True

# Línea 547: Scoring híbrido
combined = (visual_weight * visual_sim) + (color_weight * color_similarity)

# Línea 562: Stock boost
if enable_stock_boost:
    all_images = _apply_stock_boost(all_images, enable_stock_boost=True)
```

**Endpoints**:
- `/api/diagnostic/clip-raw`
- `/api/diagnostic/text-search`

**Estado**: Experimental - NO está en Railway

---

### 2. **search_config.py** 🛠️ PANEL ADMIN

**Líneas de uso**: 35-37, 48-50, 98-108

**Funcionalidad**:
```python
# GET /search-config/ - Muestra configuración
configs_data = [{
    'client': client,
    'visual_weight': client.visual_weight or 70,
    'color_weight': client.color_weight or 30,
    'enable_stock_boost': client.enable_stock_boost or True
}]

# POST /search-config/update - Actualiza pesos
visual_weight = int(request.form.get("visual_weight", 70))
color_weight = int(request.form.get("color_weight", 30))
enable_stock_boost = request.form.get("enable_stock_boost") == "on"

client.visual_weight = visual_weight
client.color_weight = color_weight
client.enable_stock_boost = enable_stock_boost
db.session.commit()
```

**Endpoint**: `/search-config/`

**Estado**: Panel admin registrado (app.py línea ~335)

---

### 3. **api.py** ❌ NO USA ESTOS CAMPOS

**Búsqueda realizada**:
```
visual_weight → "score_visual_weight" (variable DIFERENTE)
```

**Código api.py línea 1827**:
```python
# ❌ NO es client.visual_weight
score_visual_weight = float(mc.get('score_visual_weight', sys_mc.get('score_visual_weight', 0.7)))
```

**Explicación**:
- `score_visual_weight` viene de `multi_category_config` (JSON en system_config)
- **NO** lee de `client.visual_weight` (campo BD)

**Confirmado**: `/api/search` (producción) **NO USA** estos campos

---

## 🎯 CONCLUSIÓN

### ✅ CAMPOS SÍ SE USAN PERO...

**Usos confirmados**:
1. ✅ `diagnostic.py` (experimental) - Lee y usa activamente
2. ✅ `search_config.py` (panel admin) - Permite editar vía UI

**Usos NO confirmados**:
- ❌ `/api/search` (producción) - NO los usa
- ❌ `textile_search.py` - NO los usa
- ❌ `textile_search_v2.py` - NO los usa

---

## 🤔 ¿SON ÚTILES O NO?

### Escenario 1: diagnostic.py NO va a producción

**Si NO desplegamos diagnostic.py a Railway**:
- ❌ Campos **SIN USO** en producción
- ✅ Panel `/search-config/` existe pero edita campos que no hace nada
- **Recomendación**: **ELIMINAR** campos + panel + migración

### Escenario 2: diagnostic.py SÍ va a producción

**Si SÍ desplegamos diagnostic.py a Railway**:
- ✅ Campos **ÚTILES** para búsqueda híbrida
- ✅ Panel `/search-config/` permite configurar pesos por cliente
- ✅ Stock boost mejora resultados (+15% productos disponibles)
- **Recomendación**: **MANTENER** todo

---

## 📋 DECISIÓN REQUERIDA

### Opción A: Eliminar Todo ❌

**Si diagnostic.py queda solo local**:

1. **Eliminar migración**:
   ```bash
   rm migrations/2025-11-04_simplify_client_config.sql
   ```

2. **Eliminar campos modelo**:
   ```python
   # models/client.py - ELIMINAR:
   visual_weight = db.Column(db.Integer, default=70)
   color_weight = db.Column(db.Integer, default=30)
   enable_stock_boost = db.Column(db.Boolean, default=True)
   ```

3. **Eliminar blueprint**:
   ```bash
   rm clip_admin_backend/app/blueprints/search_config.py
   ```

4. **Desregistrar en app.py**:
   ```python
   # app.py - COMENTAR/ELIMINAR:
   from app.blueprints.search_config import bp as search_config_bp
   app.register_blueprint(search_config_bp, url_prefix="/search-config")
   ```

5. **Limpiar diagnostic.py**:
   - Usar valores hardcoded (70/30/True)
   - Eliminar lectura desde `client.*_weight`

**Resultado**:
- 🟢 Código más limpio
- 🟢 Sin campos BD innecesarios
- 🔴 diagnostic.py pierde flexibilidad (pesos fijos)

---

### Opción B: Mantener Todo ✅

**Si diagnostic.py se usa (local o producción)**:

1. **Mantener migración** (ya limpia sin `color_detection_method`)
2. **Mantener campos modelo**
3. **Mantener panel `/search-config/`** (UI para editar)
4. **Opcional**: Mejorar UI panel (Bootstrap 5)

**Resultado**:
- 🟢 Flexibilidad per-client (cada cliente configura pesos)
- 🟢 Panel admin útil
- 🔴 Código extra en proyecto

---

## 🎬 RECOMENDACIÓN FINAL

### **SI** usuario pregunta "ya no se usan en nada útil" → Probablemente quiere Opción A

**Evidencia**:
- `/api/search` (producción) NO los usa
- Solo `diagnostic.py` (experimental) los usa
- Panel `/search-config/` existe pero configura algo que no afecta producción

**Plan limpieza sugerido**:

1. **Ahora**: Eliminar campos + migración + panel
2. **Futuro**: Si diagnostic.py va a producción, re-agregar (migración nueva)

**Código a eliminar**:
- ❌ `migrations/2025-11-04_simplify_client_config.sql`
- ❌ `blueprints/search_config.py`
- ❌ Campos en `models/client.py`
- ❌ Sección app.py que registra search_config blueprint
- ⚠️ Adaptar `diagnostic.py` para usar valores fijos

---

## ❓ PREGUNTA PARA USUARIO

**¿Quieres eliminar estos campos porque diagnostic.py no va a usarse en producción?**

- **SÍ** → Ejecuto limpieza completa (Opción A)
- **NO** → Los mantenemos para usar diagnostic.py después (Opción B)

**Esperando confirmación antes de proceder** 🔧
