# 🚀 Plan de Migración a Railway - 13 Noviembre 2025

## 📋 Resumen Ejecutivo

Este documento detalla el plan completo para migrar CLIP Comparador V2 desde desarrollo local a producción en Railway, incluyendo la migración de la base de datos PostgreSQL con todos los datos existentes.

**Estado Actual:**
- ✅ Código refactorizado (jerarquías eliminadas, vision_hint activo)
- ✅ Base de datos local PostgreSQL con datos completos
- ✅ Sistema funcionando en local (localhost:5000)
- ⚠️ Railway tiene schema antiguo (sin vision_hint, con jerarquías)

**Objetivo:**
Desplegar versión actualizada en Railway manteniendo:
- Todos los datos existentes (clientes, categorías, productos, imágenes)
- Nuevas columnas y cambios de schema
- Configuración optimizada para Railway Hobby Plan ($5/mes)

---

## 🔄 Cambios Realizados en el Código (Contexto)

### ✅ Eliminaciones
1. **Jerarquías de Categorías** - Removidas completamente:
   - ❌ `parent_id` (columna)
   - ❌ `level` (columna)
   - ❌ `is_leaf` (columna)
   - ❌ Lógica de subcategorías
   - ❌ Validaciones de jerarquía

2. **Archivos Obsoletos Eliminados**:
   - Scripts de migración antiguos
   - Documentación desactualizada
   - Templates de jerarquías

### ✅ Adiciones
1. **Campo `vision_hint`** - Agregado a tabla `categories`:
   - Tipo: `TEXT` (nullable)
   - Propósito: Hints visuales para GPT-4 Vision
   - Ejemplo: "SHORT DE TIRO ALTO: cintura por encima del ombligo"
   - Uso: Desambiguación en detección automática de categorías

2. **Mejoras de Código**:
   - Refactorización de blueprints
   - Optimización de queries
   - Limpieza de código legacy

### ⚠️ Incompatibilidades Schema Local vs Railway

| Tabla | Campo | Local | Railway | Acción |
|-------|-------|-------|---------|--------|
| `categories` | `vision_hint` | ✅ Existe (TEXT) | ❌ No existe | Agregar columna |
| `categories` | `parent_id` | ❌ Eliminado | ✅ Existe | Eliminar columna |
| `categories` | `level` | ❌ Eliminado | ✅ Existe | Eliminar columna |
| `categories` | `is_leaf` | ❌ Eliminado | ✅ Existe | Eliminar columna |
| `categories` | `name_en` | ✅ Existe | ❌ No existe | Ya en local |
| `products` | `name_en` | ✅ Existe | ❌ No existe | Ya en local |
| `images` | `filename` | ✅ NOT NULL | ✅ Existe | OK |
| `images` | `thumbnail_url` | ❌ No existe* | ❌ No existe | OK (@property) |

*`thumbnail_url` es un `@property` del modelo, no columna real

---

## 📊 Inventario de Datos Actual

### ⚠️ IMPORTANTE: Estrategia de Datos
**Los datos de local están sincronizados y actualizados desde Railway.**
**API Keys son DIFERENTES entre local y Railway - NO se reemplazarán.**

### Datos en Local (Desarrollo - Sincronizados desde Railway)
```
👥 Clientes: 2
  - Goody Fashion Store (API Key: LOCAL diferente)
  - Eve's Store (API Key: LOCAL diferente)

📁 Categorías: 24 (incluyendo DELANTAL - ya en local)

📦 Productos: 90
  - Todos sincronizados desde Railway
  - Últimos: 5 pantalones (rio, rombo, jade, gema, leon)

🖼️ Imágenes: 101
  - Todas sincronizadas desde Railway
  - 7 imágenes nuevas pendientes de embeddings locales
  - Embeddings en Railway están completos

🔑 API Keys: 2 (EXCLUSIVAS DE LOCAL - no migrar)
```

### Datos en Railway (Producción Actual)
```
👥 Clientes: 2 (API Keys en PRODUCCIÓN activas)
📁 Categorías: 24 (con schema antiguo - sin vision_hint)
📦 Productos: 90 (mismos que local)
🖼️ Imágenes: 101 (mismas que local)
🔄 Embeddings: Completos y procesados
```

**Diferencias críticas:**
1. Railway tiene schema desactualizado (sin vision_hint, con jerarquías)
2. API Keys son diferentes y NO se deben reemplazar
3. Embeddings en Railway están procesados, en local hay 7 pendientes

---

## 🎯 Estrategia de Migración

### Opción Seleccionada: **Solo Actualización de Schema (Sin Migración de Datos)**

**Ventajas:**
- ✅ Mantiene API Keys activas en producción
- ✅ Mantiene embeddings procesados en Railway
- ✅ Solo actualiza estructura de BD
- ✅ Downtime < 2 minutos
- ✅ Sin riesgo de pérdida de datos

**Restricciones de Railway:**
- ⚠️ No permite ejecutar SQL directamente desde Railway CLI/Dashboard
- ✅ Se ejecutará SQL remotamente desde local usando psycopg2
- ✅ Tenemos credenciales de conexión directa a PostgreSQL

**Lo que NO se hará:**
- ❌ NO reemplazar datos de clientes
- ❌ NO reemplazar API Keys
- ❌ NO reemplazar productos/categorías/imágenes
- ❌ NO regenerar embeddings

**Lo que SÍ se hará:**
- ✅ Actualizar schema de `categories` (agregar vision_hint, eliminar jerarquías)
- ✅ Desplegar código actualizado
- ✅ Verificar funcionamiento

**Fases:**
1. Backup completo de Railway actual
2. Actualizar schema en Railway (ejecutar SQL desde local)
3. Desplegar código actualizado
4. Verificación y smoke tests

---

## 📝 Plan Detallado Paso a Paso

### FASE 1: Preparación y Backup (30 min)

#### 1.1 Backup de Railway Producción
```powershell
# Ejecutar desde raíz del proyecto
python railway_db_tool.py backup

# Output esperado:
# ✅ Backup guardado en: backups/railway_YYYYMMDD_HHMMSS.sql
```

**Verificación:**
- [ ] Archivo .sql generado en carpeta `backups/`
- [ ] Tamaño > 100 KB (datos completos)
- [ ] Sin errores en log

#### 1.2 Backup de Base Local
```powershell
python backup_local_db.py

# Output esperado:
# ✅ Backup local guardado en: backups/local_YYYYMMDD_HHMMSS.dump
```

**Verificación:**
- [ ] Archivo .dump generado
- [ ] Tamaño similar al de Railway

#### 1.3 Verificar Diferencias de Datos
```powershell
# Comparar conteos
python -c "
from clip_admin_backend.app import create_app, db
from clip_admin_backend.app.models.category import Category
from clip_admin_backend.app.models.product import Product
from clip_admin_backend.app.models.image import Image

app = create_app()
with app.app_context():
    print(f'Categorías local: {Category.query.count()}')
    print(f'Productos local: {Product.query.count()}')
    print(f'Imágenes local: {Image.query.count()}')
"
```

**Documentar:**
- Número de registros en cada tabla (local)
- Comprar con Railway (ya sabemos: 24, 90, 101)

---

### FASE 2: Actualización de Schema en Railway (15 min)

#### 2.1 Script de Migración SQL Ya Creado

**Archivo:** `migrations/railway_schema_update_13nov2025.sql`

✅ Ya existe - Revisa el contenido antes de ejecutar

**Qué hace el script:**
- Agrega `vision_hint TEXT` a `categories`
- Elimina `parent_id`, `level`, `is_leaf` de `categories`
- Agrega `name_en` a `categories` y `products` si no existe
- Asegura `filename NOT NULL` en `images`
- Asegura `client_id` en `images` con FK

#### 2.2 Ejecutar Migración SQL desde Local

**⚠️ IMPORTANTE:** Railway no permite ejecutar SQL desde su CLI/Dashboard.
**Solución:** Ejecutar remotamente desde local usando credenciales directas.

**Usar script auxiliar:**

```powershell
# El script ya está creado: railway_execute_sql.py
python railway_execute_sql.py migrations/railway_schema_update_13nov2025.sql
```

**El script hace:**
1. Lee el archivo SQL
2. Conecta a Railway PostgreSQL usando credenciales directas
3. Ejecuta en una transacción (COMMIT al final)
4. Muestra RAISE NOTICE del progreso
5. Si hay error, hace ROLLBACK automático

**Output esperado:**
```
📁 Leyendo archivo: migrations/railway_schema_update_13nov2025.sql
📄 Contenido: 4523 caracteres
🔌 Conectando a Railway...
⚙️ Ejecutando SQL...
✅ Migración completada exitosamente
  ℹ️ NOTICE: Columna vision_hint agregada
  ℹ️ NOTICE: Columna parent_id eliminada
  ℹ️ NOTICE: Columna level eliminada
  ℹ️ NOTICE: Columna is_leaf eliminada
  ℹ️ NOTICE: === VERIFICACIÓN POST-MIGRACIÓN ===
  ℹ️ NOTICE: Categorías: 24
  ℹ️ NOTICE: Productos: 90
  ℹ️ NOTICE: Imágenes: 101
```

**Verificación Post-Migración:**
```powershell
# Verificar columnas en categories
python railway_db_tool.py query "SELECT column_name FROM information_schema.columns WHERE table_name = 'categories' ORDER BY column_name"

# Verificar datos
python railway_db_tool.py query "SELECT COUNT(*) as total FROM categories"
```

**Esperado:**
- ✅ `vision_hint` existe
- ❌ NO existen: `parent_id`, `level`, `is_leaf`
- ✅ 24 categorías presentes

---

### FASE 3: ~~Sincronización de Datos~~ (OMITIDA)

**Esta fase se omite porque:**
- ✅ Datos ya están sincronizados
- ✅ API Keys no se deben reemplazar
- ✅ Embeddings ya están procesados en Railway
- ✅ Solo necesitamos actualizar schema y código

---

### FASE 4: Despliegue de Código a Railway (30 min)

#### 4.1 Preparar Variables de Entorno

**En Railway Dashboard:**

1. Ir a proyecto CLIP Comparador V2
2. Settings → Variables
3. Verificar/Actualizar:

```env
# Flask
FLASK_ENV=production
SECRET_KEY=<generar-nuevo-con-secrets.token_hex(32)>

# Database (Auto-generada por Railway)
DATABASE_URL=postgresql://postgres:****@ballast.proxy.rlwy.net:54363/railway

# Redis (Si está configurado)
REDIS_URL=redis://****

# Cloudinary
CLOUDINARY_CLOUD_NAME=dgtsan81n
CLOUDINARY_API_KEY=****
CLOUDINARY_API_SECRET=****

# OpenAI (para GPT-4 Vision)
OPENAI_API_KEY=****

# Sistema
PYTHONUNBUFFERED=1
PORT=5000
```

#### 4.2 Verificar Procfile

**Archivo:** `Procfile`

```
web: cd clip_admin_backend && gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 wsgi:app
```

**Verificar que existe y es correcto:**
```powershell
Get-Content Procfile
```

#### 4.3 Verificar requirements.txt

```powershell
Get-Content requirements.txt | Select-String -Pattern "Flask|psycopg2|gunicorn|cloudinary"
```

**Debe incluir:**
- Flask==3.x
- psycopg2-binary
- gunicorn
- cloudinary
- torch (para CLIP)
- transformers
- Pillow

#### 4.4 Push a Railway

**Opción A: Git Push (Recomendado)**

```bash
# Asegurar que todo está commiteado
git status
git add .
git commit -m "feat: Remove hierarchy, add vision_hint, Railway migration ready"

# Push a Railway
git push railway main
```

**Opción B: Railway CLI**

```bash
railway up
```

#### 4.5 Monitorear Deployment

**En Railway Dashboard:**
1. Ver logs en tiempo real
2. Esperar "Build successful"
3. Esperar "Deploy successful"
4. Verificar que el servicio está "Active"

**Tiempo estimado:** 3-5 minutos

---

### FASE 5: Verificación y Smoke Tests (20 min)

#### 5.1 Health Check

```powershell
# Verificar que la app responde
Invoke-WebRequest -Uri "https://clip-comparador-v2.up.railway.app/" -Method GET

# Debe retornar 200 OK
```

#### 5.2 Verificar Schema de Base de Datos

```powershell
# Verificar columnas en categories
python railway_db_tool.py query "SELECT column_name FROM information_schema.columns WHERE table_name = 'categories' ORDER BY column_name"

# Verificar datos
python railway_db_tool.py query "SELECT COUNT(*) as total, COUNT(vision_hint) as con_hint FROM categories"
```

**Esperado:**
- `vision_hint` existe
- NO existen: `parent_id`, `level`, `is_leaf`

#### 5.3 Test de API - Listar Clientes

```powershell
# Test endpoint público
$response = Invoke-RestMethod -Uri "https://clip-comparador-v2.up.railway.app/api/clients/list" -Method GET
$response | ConvertTo-Json -Depth 3
```

**Esperado:**
```json
{
  "success": true,
  "clients": [
    {"name": "Goody Fashion Store", "api_key": "****"},
    {"name": "Eve's Store", "api_key": "****"}
  ]
}
```

#### 5.4 Test de Búsqueda Visual

```powershell
# Obtener API Key de un cliente
$apiKey = $response.clients[0].api_key

# Test de búsqueda
$body = @{
    image = "data:image/png;base64,iVBORw0KGg..."  # Imagen de prueba
    top_k = 5
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://clip-comparador-v2.up.railway.app/api/search/unified" `
    -Method POST `
    -Headers @{ "X-API-Key" = $apiKey; "Content-Type" = "application/json" } `
    -Body $body
```

**Esperado:**
- Status 200
- Resultados con productos y scores

#### 5.5 Test de Admin Panel

1. Abrir: `https://clip-comparador-v2.up.railway.app/auth/login`
2. Login con credenciales de SUPER_ADMIN
3. Verificar:
   - [ ] Dashboard carga correctamente
   - [ ] Estadísticas muestran números correctos
   - [ ] Navegación a Categorías funciona
   - [ ] Navegación a Productos funciona
   - [ ] Navegación a Embeddings funciona
   - [ ] No hay errores de JS en consola

#### 5.6 Test de Categorías (vision_hint)

1. Ir a `/categories`
2. Seleccionar una categoría
3. Click "Editar"
4. Verificar:
   - [ ] Campo `vision_hint` aparece en el formulario
   - [ ] Puede guardarse texto en `vision_hint`
   - [ ] Se guarda correctamente (refresh y verifica)

#### 5.7 Verificar Embeddings

```powershell
python railway_db_tool.py query "SELECT COUNT(*) as total, COUNT(clip_embedding) as procesadas FROM images"
```

**Esperado:**
- Total: 101 imágenes
- Procesadas: ~94 (algunas pueden estar pendientes)

---

### FASE 6: Procesamiento Post-Migración (15 min)

#### 6.1 Procesar Imágenes Pendientes

Si hay imágenes sin embeddings:

1. Login al admin panel en Railway
2. Ir a `/embeddings`
3. Click "Procesar Pendientes"
4. Esperar a que complete

**O desde script:**
```powershell
# Llamar endpoint de procesamiento
$token = "<session-token>"  # Obtener de cookies después de login

Invoke-RestMethod -Uri "https://clip-comparador-v2.up.railway.app/embeddings/process_pending" `
    -Method POST `
    -Headers @{ "Cookie" = "session=$token" }
```

#### 6.2 Recalcular Centroides

Si es necesario:

1. Ir a `/categories`
2. Para cada categoría con productos:
   - Ver detalles
   - Click "Recalcular Centroide" (si disponible)

---

### FASE 7: Rollback Plan (Si algo falla)

#### 7.1 Restaurar Base de Datos

```powershell
# Restaurar desde backup
python railway_db_tool.py restore backups/railway_YYYYMMDD_HHMMSS.sql
```

#### 7.2 Revertir Código

```bash
# Revertir al commit anterior
git revert HEAD
git push railway main --force
```

#### 7.3 Verificar Restauración

Ejecutar smoke tests de FASE 5 nuevamente.

---

## ⏱️ Timeline Total Estimado (Actualizado)

| Fase | Tiempo | Downtime |
|------|--------|----------|
| 1. Preparación y Backup | 15 min | No |
| 2. Actualización Schema (SQL remoto) | 15 min | **Sí (2 min)** |
| 3. ~~Sincronización Datos~~ | ~~OMITIDA~~ | No |
| 4. Despliegue Código | 20 min | **Sí (3 min)** |
| 5. Verificación | 15 min | No |
| 6. ~~Post-Migración~~ | ~~OMITIDA~~ | No |
| **TOTAL** | **~1 hora** | **~5 min** |

---

## 🎯 Criterios de Éxito

### ✅ Schema
- [ ] `vision_hint` existe en `categories`
- [ ] `parent_id`, `level`, `is_leaf` NO existen en `categories`
- [ ] `name_en` existe en `categories` y `products`
- [ ] `client_id` existe en `images` con FK

### ✅ Datos
- [ ] 2 clientes activos
- [ ] 24 categorías (incluyendo DELANTAL)
- [ ] 90 productos
- [ ] 101 imágenes
- [ ] Embeddings procesados (>90%)

### ✅ Funcionalidad
- [ ] API `/api/search/unified` funciona
- [ ] Admin panel accesible
- [ ] Login funciona
- [ ] Crear/editar categorías con `vision_hint`
- [ ] GPT-4 Vision detection funciona
- [ ] Embeddings se pueden regenerar

### ✅ Performance
- [ ] Tiempo de respuesta API < 2s
- [ ] Búsqueda visual < 1.5s
- [ ] Admin panel carga < 3s
- [ ] No memory leaks (monitorear Railway metrics)

---

## 🔧 Comandos de Referencia Rápida

### Backup
```powershell
# Railway
python railway_db_tool.py backup

# Local
python backup_local_db.py
```

### Schema Migration
```powershell
# Ejecutar SQL en Railway
python railway_execute_sql.py migrations/railway_schema_update_13nov2025.sql
```

### Deploy
```bash
git push railway main
```

### Verificación
```powershell
# Health check
Invoke-WebRequest -Uri "https://clip-comparador-v2.up.railway.app/" -Method GET

# Test API
python test_api_search_quick.ps1
```

### Rollback
```powershell
# Restaurar DB
python railway_db_tool.py restore backups/railway_YYYYMMDD_HHMMSS.sql

# Revertir código
git revert HEAD && git push railway main --force
```

---

## 📞 Contactos y Recursos

### Railway Dashboard
- URL: https://railway.app/
- Proyecto: CLIP Comparador V2
- Region: US West

### Monitoreo
- Logs: Railway Dashboard → Deployments → View Logs
- Metrics: Railway Dashboard → Metrics
- Alerts: Email configurado en Railway

### Documentación
- Railway Docs: https://docs.railway.app/
- PostgreSQL Migration Guide: https://www.postgresql.org/docs/current/pg-dump.html

---

## 📝 Notas Importantes

### 🚨 Datos Críticos a Preservar
1. **API Keys de clientes** - No regenerar, mantener las existentes
2. **Embeddings CLIP** - Costosos de regenerar (tiempo + OpenAI API)
3. **Cloudinary Public IDs** - Referencian imágenes en CDN
4. **Relaciones FK** - Mantener integridad referencial

### ⚠️ Precauciones
1. **Hacer backup ANTES de cualquier cambio**
2. **Ejecutar SQL desde local usando railway_execute_sql.py**
3. **No eliminar backups hasta confirmar éxito total**
4. **Mantener ventana de Railway abierta para monitoreo**
5. **Tener plan de rollback listo**
6. **NO reemplazar API Keys de Railway - mantener las existentes**
7. **Los datos YA están sincronizados - solo actualizar schema**

### 💡 Tips
1. Ejecutar migración en horario de bajo tráfico
2. Comunicar mantenimiento a usuarios (si aplica)
3. Monitorear Railway metrics después del deploy
4. Verificar logs por errores durante las primeras horas
5. Hacer backup post-migración exitosa

---

## ✅ Checklist Pre-Migración

Antes de comenzar, verificar:

- [ ] Tengo acceso a Railway Dashboard
- [ ] Tengo credenciales de base de datos Railway
- [ ] Código local está actualizado y funcionando
- [ ] Tengo backups recientes
- [ ] He revisado el plan completo
- [ ] Tengo ~3 horas disponibles sin interrupciones
- [ ] He notificado a stakeholders (si aplica)
- [ ] Tengo plan de rollback listo

---

## 📅 Próximos Pasos Post-Migración

1. **Monitoreo** (Semana 1):
   - Revisar logs diarios
   - Monitorear métricas de Railway
   - Verificar errores en Sentry (si configurado)

2. **Optimización** (Semana 2):
   - Analizar queries lentas
   - Optimizar embeddings si es necesario
   - Ajustar workers de Gunicorn según uso

3. **Documentación** (Semana 3):
   - Actualizar README con URL de producción
   - Documentar proceso de deployment
   - Crear guía de troubleshooting

---

**Documento generado:** 13 Noviembre 2025
**Versión:** 1.0
**Autor:** CLIP Comparador V2 Team
**Estado:** Ready for execution

