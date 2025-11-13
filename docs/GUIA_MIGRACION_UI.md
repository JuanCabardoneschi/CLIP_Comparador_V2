# 🔄 Guía de Migración BLIP-2 para Usuarios

## 📋 Resumen

Has completado con éxito la **migración del código de CLIP a BLIP-2**. Ahora necesitas **regenerar todos los embeddings** de tu base de datos local para que el sistema funcione correctamente.

---

## ❗ IMPORTANTE: ¿Por qué hay que regenerar?

**Embeddings incompatibles:**
- **CLIP** genera embeddings de **512 dimensiones**
- **BLIP-2** genera embeddings de **256 dimensiones**
- ❌ **NO se pueden comparar** (diferentes espacios vectoriales)

**Estructura de base de datos:**
- ✅ La BD **NO cambia** (mismas tablas y columnas)
- ❌ Los **valores** de embeddings son incompatibles
- 🔄 Hay que **re-generar** todos los embeddings con BLIP-2

---

## 🎯 Opciones de Regeneración

Tienes **2 formas** de regenerar embeddings:

### **Opción 1: Desde la UI (Panel Admin)** 🖥️

#### Acceso:
1. Iniciar sistema: `.\start_local.ps1`
2. Navegar: http://localhost:5000
3. Login con usuario admin de cada cliente
4. Ir a: **Embeddings** → **Administración de Embeddings BLIP-2**

#### Proceso por cliente:

1. **Ver panel de embeddings**:
   - Estadísticas actuales (total, procesados, pendientes)
   - Lista de imágenes con sus estados

2. **Sección "Migración CLIP → BLIP-2" (Card roja)**:
   - Aparece solo para STORE_ADMIN
   - Explica qué hace el proceso:
     * 1️⃣ Resetea embeddings CLIP (512D)
     * 2️⃣ Regenera con BLIP-2 (256D, imagen completa)
     * 3️⃣ Recalcula centroides automáticamente
   - Botón grande: **"REGENERAR TODO CON BLIP-2"**

3. **Click en el botón**:
   - Se abre confirmación explicativa

4. **Confirmar**:
   ```
   ⚠️ ¿Regenerar TODOS los embeddings con BLIP-2?

   Este proceso hará reset de X embeddings y los regenerará
   usando BLIP-2 (imagen completa, sin recortes).

   ¿Confirmas?
   ```

4. **Monitorear**:
   - Ver progreso en pantalla
   - Logs en consola del backend
   - Esperar hasta 100% completado
   - **✨ IMPORTANTE**: Los centroides se recalculan **automáticamente** cada 3 imágenes procesadas

5. **Verificar en logs**:
   ```
   🔄 Procesando imagen1.jpg...
   ✅ imagen1.jpg procesado con blip2_unified
   💾 Lote guardado: 3/150 imágenes procesadas
   📊 Centroide actualizado para categoría: Gorras
   ✅ 1 centroides actualizados
   ```

#### Tiempo estimado:
- **~500ms por imagen** con BLIP-2 (CPU)
- **50 imágenes**: ~25 segundos
- **200 imágenes**: ~100 segundos (~1.5 minutos)
- **500 imágenes**: ~250 segundos (~4 minutos)

#### ✅ **Ventaja de usar UI:**
- Recalcula centroides **automáticamente** por lotes
- No necesitas ejecutar `recalculate_blip2_centroids.py` después
- Actualización incremental más eficiente

---

### **Opción 2: Script desde Terminal (Recomendado para catálogos grandes)** 💻

#### Ventajas:
- ✅ Más confiable (no depende de UI/navegador)
- ✅ **Backup automático** antes de empezar
- ✅ Log detallado en archivo
- ✅ Manejo de errores robusto
- ✅ Dry-run para validar primero

#### Proceso:

**Paso 1: Dry-run (Simulación)**
```powershell
# Activar entorno virtual
.\venv\Scripts\Activate.ps1

# Probar sin cambiar nada
python reembed_with_blip2.py --dry-run
```

Esto te mostrará:
- ✅ Qué imágenes se procesarán
- ✅ Total de embeddings a regenerar
- ✅ Clientes afectados
- ❌ **NO modifica** la base de datos

**Paso 2: Re-embedding real**
```powershell
# Ejecutar regeneración completa
python reembed_with_blip2.py

# Ver progreso:
# [1/200] Cliente: ACME Corp | Producto: Gorra Azul | ✅ 256D
# [2/200] Cliente: Fashion Store | Producto: Remera Roja | ✅ 256D
# ...
```

**Paso 3: Recalcular centroides**
```powershell
# Solo necesario si usaste el script terminal
# La UI ya lo hace automáticamente
python recalculate_blip2_centroids.py --force
```
**⚠️ NOTA**: Si usaste la **UI "Regenerar Todo"**, los centroides ya están actualizados automáticamente. Este paso es **solo para quien use el script terminal**.

<!-- Paso 4 de Re-calibración eliminado -->

---

## 📊 Verificación Post-Migración

### Checklist de validación:

#### 1. **Embeddings regenerados**
```powershell
# Verificar dimensiones
python check_embeddings.py
```

Esperado:
```
✅ Cliente ACME Corp:
   - 150/150 imágenes con embeddings
   - Dimensión: 256D (BLIP-2)
   - Todas normalizadas (norma L2 = 1.0)

✅ Cliente Fashion Store:
   - 200/200 imágenes con embeddings
   - Dimensión: 256D (BLIP-2)
   - Todas normalizadas (norma L2 = 1.0)
```

#### 2. **Centroides actualizados**
```powershell
# Verificar centroides por categoría
python -c "
from clip_admin_backend.app.models.category import Category
from clip_admin_backend.app import create_app, db

app = create_app()
with app.app_context():
    categories = Category.query.filter_by(is_active=True).all()
    for cat in categories:
        print(f'{cat.name}: {cat.centroid_image_count} imágenes, última actualización: {cat.centroid_updated_at}')
"
```

#### 3. **Búsqueda funciona**
- Subir una imagen de prueba
- Verificar que devuelve resultados
- Comparar similitud (debe estar entre 0.0 y 1.0)

#### 4. **API externa funciona**
```powershell
# Test de búsqueda por imagen
python test_search_api.py
```

---

## ❓ Preguntas Frecuentes

### **¿Puedo seguir trabajando mientras regenera?**
- ✅ Sí, el backend sigue funcionando
- ⚠️ Las búsquedas pueden dar resultados inconsistentes durante la migración
- 💡 Mejor hacer la regeneración fuera de horario productivo

### **¿Qué pasa si se interrumpe el proceso?**
- ✅ El script guarda progreso por lotes (cada 10 imágenes)
- ✅ Puedes volver a ejecutar y continuará desde donde quedó
- ✅ El backup automático protege tus datos

### **¿Cuánto espacio en disco necesito?**
- **Backup automático**: ~Tamaño de tu BD (ej: 500MB → 500MB backup)
- **Embeddings BLIP-2**: Mitad de espacio que CLIP (256D vs 512D)
- **Total**: ~1.5x el tamaño actual de tu BD

### **¿Los embeddings antiguos se pierden?**
- ❌ Sí, se sobrescriben con BLIP-2
- ✅ Pero hay **backup automático** antes de empezar
- 🔙 Puedes restaurar con `restore_from_backup.ps1` si hay problemas

### **¿Necesito reinstalar dependencias?**
No, todas las dependencias de BLIP-2 ya están en `requirements.txt`:
```
transformers>=4.45.0
torch>=2.0.0
Pillow>=9.0.0
```

### **¿Cambia la API externa?**
- ✅ **NO**, la API sigue igual
- ✅ Los endpoints son los mismos: `/api/search`
- ✅ La respuesta tiene la misma estructura
- 🆕 Internamente usa BLIP-2 (más rápido y preciso)

---

## 🚨 Troubleshooting

### **Error: "No module named 'blip2_embeddings'"**
```powershell
# Verificar archivo existe
ls clip_admin_backend\app\utils\blip2_embeddings.py

# Si no existe, crearlo desde migrate_clip_to_blip2_auto.py
python migrate_clip_to_blip2_auto.py
```

### **Error: "CUDA out of memory"**
BLIP-2 está configurado para **CPU only**:
```json
// system_config.json
"blip2": {
  "device": "cpu",
  "use_fp16": true  // Reduce RAM a la mitad
}
```

Si necesitas más performance:
- Upgrade a Railway Pro (32GB RAM)
- O considera GPU en futuro

### **Error: "Embeddings dimension mismatch"**
Significa que hay embeddings antiguos de CLIP (512D) mezclados con BLIP-2 (256D).

**Solución**:
```powershell
# Forzar regeneración completa
python reembed_with_blip2.py --force
```

### **UI no muestra progreso**
1. Verificar que backend está corriendo
2. Abrir DevTools (F12) → Console
3. Ver si hay errores de JavaScript
4. Refrescar página (F5)

---

## 📞 Soporte

Si tienes problemas:

1. **Revisar logs**:
   ```powershell
   # Ver logs del backend
   tail -f logs/app.log
   ```

2. **Verificar estado**:
   ```powershell
   # Ver estadísticas de embeddings
   python check_embeddings.py
   ```

3. **Restaurar backup** (último recurso):
   ```powershell
   # Si algo salió mal
   .\restore_from_backup.ps1 <fecha_backup>
   ```

---

## ✅ Resumen del Flujo Completo

```
1️⃣ Migración de código (YA HECHO ✅)
   - blip2_embeddings.py creado
   - api.py actualizado
   - embeddings.py refactorizado
   - system_config.json migrado

2️⃣ Regeneración local (TU PASO ACTUAL)
   Opción A: UI Admin Panel
     → Login → Embeddings → "Regenerar Todo"

   Opción B: Script Terminal (RECOMENDADO)
     → python reembed_with_blip2.py

3️⃣ Recalcular centroides
   → python recalculate_blip2_centroids.py --force

<!-- Re-calibración eliminada del flujo final -->

5️⃣ Testing local
   → Probar búsquedas visuales/texto
   → Verificar resultados

6️⃣ Deploy a Railway Pro
   → Upgrade plan → Deploy → Monitor
```

---

## 🎉 Checklist Final

Antes de considerar la migración completa:

- [ ] Embeddings regenerados con BLIP-2 (256D)
- [ ] Centroides recalculados
- [ ] Búsquedas funcionan correctamente
- [ ] API externa probada y validada
- [ ] Performance aceptable (latencia < 2s)
- [ ] Sin errores en logs
- [ ] Backup disponible por si acaso
- [ ] Cliente 1 migrado y testeado
- [ ] Cliente 2 migrado y testeado
- [ ] Listo para deploy a Railway Pro

---

## 🚀 Próximos Pasos

Una vez completada la migración local:

1. **Upgrade Railway a Pro** ($20/mes)
2. **Deploy a Railway** con BLIP-2
3. **Monitor performance** (RAM/CPU/latencia)
4. **Limpiar código CLIP** obsoleto
5. **Celebrar** 🎉 - Tienes BLIP-2 funcionando!

---

**Fecha de migración**: Noviembre 2025
**Versión sistema**: 2.1.0 (BLIP-2)
**Contacto soporte**: Ver README.md
