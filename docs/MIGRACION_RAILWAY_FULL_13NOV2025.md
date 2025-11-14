# 🚀 Plan de Migración COMPLETA a Railway - 13 Noviembre 2025

## 📋 Resumen Ejecutivo

**ESTRATEGIA**: Reemplazo TOTAL de Railway con copia EXACTA de local

**Objetivo**: Railway será un **CLON COMPLETO** de local:
- ✅ **Software**: Código actualizado (vision_hint, sin jerarquías)
- ✅ **Base de datos**: Schema completo de local
- ✅ **Datos**: TODOS los datos de local (categorías, productos, imágenes, clientes)
- ⚠️ **EXCEPTO**: API Keys de Railway (se preservan las originales)

---

## 🎯 Contexto

### Situación Actual
- **Local**:
  - Schema actualizado (vision_hint, sin jerarquías)
  - 24 categorías, 90 productos, 101 imágenes
  - Código completo y funcional

- **Railway**:
  - Schema desactualizado (sin vision_hint, con jerarquías)
  - Datos desactualizados
  - Código antiguo

### Resultado Esperado
Railway tendrá **exactamente lo mismo** que local:
- Mismas categorías con vision_hints
- Mismos productos con atributos
- Mismas imágenes con embeddings
- Mismos clientes
- **PERO**: API keys de Railway preservadas (no las de local)

---

## 📊 Cambios a Migrar

### Schema Changes
1. **Agregado**: `vision_hint TEXT` en `categories` (para GPT-4V)
2. **Eliminado**: `parent_id`, `level`, `is_leaf` de `categories` (jerarquías)
3. **Agregado**: `name_en TEXT` en `categories` (nombres en inglés)
4. **Fix**: `filename` se genera desde `cloudinary_public_id` cuando es NULL
5. **Fix**: `client_id` actualizado a UUID en algunas relaciones

### Código
1. vision_hint integrado en crear/editar categorías
2. vision_hint integrado en GPT-4V detection
3. Hierarchies eliminadas de blueprints y templates
4. Forms actualizados con textarea vision_hint

### Datos
1. **Categorías**: Todas de local con vision_hints completos
2. **Productos**: Todos de local con atributos dinámicos
3. **Imágenes**: Todas de local con embeddings CLIP
4. **Clientes**: Todos de local
5. **API Keys**: Solo se preservan las de Railway (crítico)

---

## 🛠️ Plan de Ejecución

### Fase 1: Backup (5 minutos)

**⚠️ CRÍTICO**: Backup de API Keys de Railway antes de cualquier cambio

```powershell
# 1. Backup completo de Railway
python railway_db_tool.py --backup
# Genera: backups/railway_backup_YYYYMMDD_HHMMSS.sql

# 2. CRÍTICO: Backup ESPECÍFICO de API Keys de Railway
python -c "
import psycopg2
conn = psycopg2.connect(
    host='ballast.proxy.rlwy.net',
    port=54363,
    user='postgres',
    password='uEZEkqTKkbKxuLJdmmhvNiPNONrSllce',
    database='railway'
)
cur = conn.cursor()
cur.execute('SELECT id, client_id, api_key, created_at FROM api_keys ORDER BY created_at')
with open('backups/railway_apikeys_backup.txt', 'w', encoding='utf-8') as f:
    f.write('-- API Keys de Railway (PRODUCCION)\n')
    for row in cur.fetchall():
        f.write(f'{row[0]},{row[1]},{row[2]},{row[3]}\n')
conn.close()
print('✅ API Keys de Railway guardadas en backups/railway_apikeys_backup.txt')
"

# 3. Backup de local (referencia)
python local_db_tool.py --backup
# Genera: backups/local_backup_YYYYMMDD_HHMMSS.sql
```

**Verificación**:
- ✅ `railway_backup_*.sql` creado
- ✅ `railway_apikeys_backup.txt` contiene las API keys de producción
- ✅ `local_backup_*.sql` creado
- ✅ Archivos tienen tamaño razonable (>1KB)

---

### Fase 2: Generar Dump Completo de Local (10 minutos)

**Crear dump pg_dump de toda la base local**

```powershell
# Dump completo: estructura + datos
pg_dump -h localhost -U postgres -d clip_comparador_v2 -F p -f backups/local_full_dump.sql

# Verificar que se generó correctamente
ls -lh backups/local_full_dump.sql
```

**Crear script SQL con API Keys de Railway (para restaurar después)**

```powershell
# Extraer SOLO api_keys de Railway en formato SQL INSERT
python -c "
import psycopg2
conn = psycopg2.connect(
    host='ballast.proxy.rlwy.net',
    port=54363,
    user='postgres',
    password='uEZEkqTKkbKxuLJdmmhvNiPNONrSllce',
    database='railway'
)
cur = conn.cursor()
cur.execute('SELECT id, client_id, api_key, created_at FROM api_keys ORDER BY created_at')
with open('backups/railway_apikeys_restore.sql', 'w', encoding='utf-8') as f:
    f.write('-- Restaurar API Keys de Railway (PRODUCCION)\n')
    f.write('DELETE FROM api_keys;\n')
    for row in cur.fetchall():
        f.write(f\"INSERT INTO api_keys (id, client_id, api_key, created_at) VALUES ('{row[0]}', '{row[1]}', '{row[2]}', '{row[3]}');\n\")
conn.close()
print('✅ Script SQL de API Keys creado en backups/railway_apikeys_restore.sql')
"
```

**Verificación**:
- ✅ `local_full_dump.sql` creado (~500KB+)
- ✅ `railway_apikeys_restore.sql` creado
- ✅ railway_apikeys_restore.sql contiene DELETE + INSERT de api_keys

---

### Fase 3: Restaurar Local en Railway (15 minutos)

**⚠️ DOWNTIME COMIENZA AQUÍ (~5 minutos) ⚠️**

```powershell
# 1. Restaurar dump completo de local en Railway
psql -h ballast.proxy.rlwy.net -p 54363 -U postgres -d railway < backups/local_full_dump.sql

# 2. Restaurar API keys de Railway (sobrescribe las de local)
psql -h ballast.proxy.rlwy.net -p 54363 -U postgres -d railway < backups/railway_apikeys_restore.sql
```

**Verificación Post-Restauración**

```powershell
# 1. Verificar schema actualizado
python railway_db_tool.py --query "SELECT column_name FROM information_schema.columns WHERE table_name='categories' AND column_name='vision_hint';"
# Debe retornar: vision_hint

# 2. Verificar jerarquías eliminadas
python railway_db_tool.py --query "SELECT column_name FROM information_schema.columns WHERE table_name='categories' AND column_name IN ('parent_id', 'level', 'is_leaf');"
# Debe retornar: (vacío)

# 3. Verificar conteo de datos
python railway_db_tool.py --query "SELECT 'categories' as tabla, COUNT(*) FROM categories UNION SELECT 'products', COUNT(*) FROM products UNION SELECT 'images', COUNT(*) FROM images;"

# 4. CRÍTICO: Verificar API keys de Railway restauradas
python railway_db_tool.py --query "SELECT LEFT(api_key, 10) || '...' as api_key_prefix FROM api_keys LIMIT 2;"
# Debe mostrar las API keys de RAILWAY (no las de local)

# 5. Verificar vision_hints migrados
python railway_db_tool.py --query "SELECT name, LEFT(vision_hint, 50) FROM categories WHERE vision_hint IS NOT NULL LIMIT 3;"
```

**Checklist**:
- ✅ vision_hint existe en Railway
- ✅ parent_id, level, is_leaf NO existen en Railway
- ✅ Conteo de categorías/productos/imágenes coincide con local
- ✅ API keys son las de Railway (NO las de local)
- ✅ vision_hints copiados correctamente

---

### Fase 4: Deploy Código a Railway (15 minutos)

**⚠️ DOWNTIME CONTINÚA (~5 minutos más) ⚠️**

```bash
# 1. Verificar que todos los cambios están commiteados
git status

# 2. Si hay cambios pendientes, commitear
git add .
git commit -m "feat: full migration - vision_hint + hierarchy removal + complete data sync"

# 3. Push a Railway
git push railway main
```

**Monitorear Deploy en Railway Dashboard**:
- Ir a: https://railway.app/project/<tu-proyecto>
- Pestaña: Deployments
- Ver logs en tiempo real
- Esperar: "Build successful" → "Deployment successful"

**Verificación Deploy**:
- ✅ Deploy exitoso en Railway Dashboard
- ✅ Logs sin errores críticos
- ✅ Service status: "Running"

**⚠️ DOWNTIME TERMINA AQUÍ ⚠️**

---

### Fase 5: Verificación Post-Deploy (15 minutos)

**Smoke Tests**

```powershell
# 1. Health check
curl https://clip-comparador-v2-production.up.railway.app/health

# 2. Test API con API key ORIGINAL de Railway
# (Usar la API key que guardaste en railway_apikeys_backup.txt)
$RAILWAY_API_KEY = "xxxxxxxx"  # Reemplazar con API key de Railway

curl -X POST https://clip-comparador-v2-production.up.railway.app/api/search `
  -H "X-API-Key: $RAILWAY_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"image":"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAGgwJ/lwVvAAAAAElFTkSuQmCC","top_k":3}'

# 3. Test admin panel
curl https://clip-comparador-v2-production.up.railway.app/login

# 4. Verificar datos migrados
python railway_db_tool.py --query "SELECT 'categories' as tabla, COUNT(*) FROM categories UNION SELECT 'products', COUNT(*) FROM products UNION SELECT 'images', COUNT(*) FROM images;"

# 5. Verificar categorías con vision_hint
python railway_db_tool.py --query "SELECT id, name, LEFT(vision_hint, 50) FROM categories WHERE vision_hint IS NOT NULL LIMIT 3;"

# 6. CRÍTICO: Verificar API keys son las de Railway
python railway_db_tool.py --query "SELECT LEFT(api_key, 10) || '...' FROM api_keys LIMIT 2;"

# 7. Comparar conteos local vs Railway
python local_db_tool.py --query "SELECT 'categories' as tabla, COUNT(*) FROM categories UNION SELECT 'products', COUNT(*) FROM products UNION SELECT 'images', COUNT(*) FROM images;"
```

**Checklist Post-Deploy**:
- ✅ /health responde 200 OK
- ✅ API search funciona con API key ORIGINAL de Railway
- ✅ Admin panel carga correctamente
- ✅ Conteo de categorías/productos/imágenes coincide 100% con local
- ✅ vision_hint visible en categorías
- ✅ API keys son las de Railway (NO las de local)
- ✅ No errores en Railway logs

---

### Fase 6: Cleanup (5 minutos)

**Archivar backups**

```powershell
# Crear carpeta de archivo
New-Item -ItemType Directory -Force -Path backups/migration_13nov2025

# Mover backups
Move-Item backups/railway_backup_*.sql backups/migration_13nov2025/
Move-Item backups/railway_apikeys_backup.txt backups/migration_13nov2025/
Move-Item backups/railway_apikeys_restore.sql backups/migration_13nov2025/
Move-Item backups/local_backup_*.sql backups/migration_13nov2025/
Move-Item backups/local_full_dump.sql backups/migration_13nov2025/
```

**Documentar**:
- ✅ Actualizar README.md con fecha de última migración
- ✅ Documentar API keys preservadas
- ✅ Archivar este plan de migración

---

### Fase 7: Validación Final (10 minutos)

**Tests de Integración**:

1. **Crear nueva categoría con vision_hint**:
   - Login admin panel Railway
   - Ir a /categories/create
   - Crear categoría de prueba con vision_hint
   - Verificar que se guarda correctamente

2. **Subir producto con imagen**:
   - Ir a /products/create
   - Crear producto con imagen
   - Verificar auto-crop y generación de embedding

3. **Probar búsqueda visual**:
   - Usar API key ORIGINAL de Railway
   - Hacer request a /api/search
   - Verificar que retorna resultados

4. **Verificar GPT-4V**:
   - Subir imagen sin categoría
   - Verificar que GPT-4V sugiere categoría usando vision_hint

5. **Comparar datos local vs Railway**:
   ```powershell
   # Comparar categorías
   python local_db_tool.py --query "SELECT name FROM categories ORDER BY name;" > temp_local_categories.txt
   python railway_db_tool.py --query "SELECT name FROM categories ORDER BY name;" > temp_railway_categories.txt
   Compare-Object (Get-Content temp_local_categories.txt) (Get-Content temp_railway_categories.txt)
   # Debe retornar: (vacío) = son idénticas
   ```

**Monitoreo Railway**:
- Railway Dashboard → Metrics
- Verificar CPU, Memory, Request count estables
- Revisar logs por 10 minutos sin errores

**Checklist Final**:
- ✅ CRUD de categorías funciona en Railway
- ✅ vision_hint se guarda y muestra correctamente
- ✅ API de búsqueda responde OK con API key de Railway
- ✅ Conteo de datos coincide 100% con local
- ✅ Categorías idénticas entre local y Railway
- ✅ No memory leaks (memory usage estable)
- ✅ No errores en logs
- ✅ Performance normal
- ✅ API keys de Railway preservadas

---

## ⏱️ Timeline Total

| Fase | Duración | Downtime |
|------|----------|----------|
| 1. Backup | 5 min | ❌ |
| 2. Generar Dump Local | 10 min | ❌ |
| 3. Restaurar en Railway | 15 min | ✅ 5 min |
| 4. Deploy Código | 15 min | ✅ 5 min |
| 5. Verificación Post-Deploy | 15 min | ❌ |
| 6. Cleanup | 5 min | ❌ |
| 7. Validación Final | 10 min | ❌ |
| **TOTAL** | **~1 hora 15 min** | **~10 minutos** |

---

## 🔄 Rollback Plan

### Si algo sale mal en Fase 3 (Restauración de Datos)

```powershell
# Restaurar backup completo de Railway
psql -h ballast.proxy.rlwy.net -p 54363 -U postgres -d railway < backups/railway_backup_YYYYMMDD_HHMMSS.sql

# Verificar
python railway_db_tool.py --query "SELECT COUNT(*) FROM categories;"
curl https://clip-comparador-v2-production.up.railway.app/health
```

### Si algo sale mal en Fase 4 (Deploy)

**Opción 1: Desde Railway Dashboard**
- Ir a Deployments
- Click en deploy anterior (el que funcionaba)
- Click "Redeploy"

**Opción 2: Desde Git**
```bash
# Ver commits recientes
git log --oneline -5

# Revertir a commit anterior
git reset --hard <COMMIT_ANTERIOR>
git push railway main --force
```

### Rollback Completo (Nuclear Option)

```powershell
# 1. Restaurar DB completa de Railway (antes de migración)
psql -h ballast.proxy.rlwy.net -p 54363 -U postgres -d railway < backups/railway_backup_YYYYMMDD_HHMMSS.sql

# 2. Revertir código a commit anterior
git reset --hard <COMMIT_ANTERIOR>
git push railway main --force

# 3. Verificar API keys restauradas
python railway_db_tool.py --query "SELECT LEFT(api_key, 10) || '...' FROM api_keys LIMIT 2;"

# 4. Verificar servicio funcionando
curl https://clip-comparador-v2-production.up.railway.app/health
curl -X POST https://clip-comparador-v2-production.up.railway.app/api/search -H "X-API-Key: $RAILWAY_API_KEY" -H "Content-Type: application/json" -d '{"image":"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAGgwJ/lwVvAAAAAElFTkSuQmCC","top_k":3}'
```

**⚠️ IMPORTANTE**:
- El backup de Railway incluye TODO (schema + datos + API keys originales)
- Un rollback completo restaura el estado 100% original
- Las API keys de producción están en el backup

---

## 📦 Scripts de Soporte

### 1. railway_db_tool.py
Herramienta para backup y queries en Railway:
```powershell
# Backup completo
python railway_db_tool.py --backup

# Query específica
python railway_db_tool.py --query "SELECT COUNT(*) FROM categories;"
```

### 2. local_db_tool.py
Herramienta para backup local:
```powershell
python local_db_tool.py --backup
```

### 3. Comandos PostgreSQL Nativos
Para migración completa de datos:
```powershell
# Dump completo de local
pg_dump -h localhost -U postgres -d clip_comparador_v2 -F p -f backups/local_full_dump.sql

# Restaurar en Railway
psql -h ballast.proxy.rlwy.net -p 54363 -U postgres -d railway < backups/local_full_dump.sql
```

---

## ✅ Criterios de Éxito

### Schema
- ✅ Railway DB tiene schema IDÉNTICO a local
- ✅ `vision_hint` existe en `categories` table
- ✅ `parent_id`, `level`, `is_leaf` NO existen en `categories`
- ✅ `name_en` existe en `categories` table

### Datos
- ✅ Railway tiene TODOS los datos de local
- ✅ Conteo de categorías/productos/imágenes coincide 100% con local
- ✅ vision_hints copiados correctamente
- ✅ Embeddings copiados correctamente
- ✅ Clientes copiados correctamente
- ⚠️ **API keys de Railway PRESERVADAS** (NO sobrescritas)

### Funcionalidad
- ✅ Admin panel permite crear/editar categorías con vision_hint
- ✅ GPT-4V detection lee y usa vision_hint correctamente
- ✅ API de búsqueda funciona con API key ORIGINAL de Railway
- ✅ Forms no muestran campos de jerarquía
- ✅ Todos los productos e imágenes accesibles
- ✅ Auto-crop funciona en imágenes nuevas
- ✅ Embeddings se generan correctamente

### Performance
- ✅ Response times normales (<2s para búsquedas)
- ✅ Sin memory leaks (memory usage estable)
- ✅ Logs sin errores críticos
- ✅ CPU usage normal (<50% promedio)

### Data Integrity
- ✅ Railway es CLON EXACTO de local (excepto API keys)
- ✅ API keys de Railway preservadas (verificado)
- ✅ Embeddings funcionando correctamente
- ✅ Cloudinary URLs funcionando
- ✅ Relaciones FK intactas
- ✅ No datos perdidos o corruptos

---

## ⚠️ Precauciones

### Antes de Ejecutar
1. ✅ Verificar que local está funcionando 100%
2. ✅ Verificar que tienes acceso a Railway Dashboard
3. ✅ Verificar credenciales PostgreSQL de Railway
4. ✅ Tener a mano las API keys de Railway (railway_apikeys_backup.txt)
5. ✅ Revisar que no hay deploys en curso en Railway

### Durante Ejecución
1. ⚠️ NO interrumpir el proceso de restauración (Fase 3)
2. ⚠️ NO hacer cambios manuales en Railway durante migración
3. ⚠️ Monitorear logs de Railway constantemente
4. ⚠️ Tener plan de rollback listo

### Después de Ejecución
1. ✅ Verificar API keys INMEDIATAMENTE
2. ✅ Hacer smoke tests completos
3. ✅ Monitorear Railway por 30 minutos
4. ✅ Notificar a usuarios de posibles problemas
5. ✅ Archivar backups de forma segura

---

## 📝 Notas Adicionales

### Por qué preservar API keys de Railway
- Las API keys de Railway están en uso en producción
- Los clientes/widgets tienen estas API keys embebidas
- Cambiarlas requeriría actualizar todos los widgets desplegados
- Es más seguro preservar las existentes

### Por qué reemplazar todos los datos
- Garantiza consistencia total entre local y Railway
- Elimina cualquier discrepancia de schema
- Asegura que vision_hints estén en todas las categorías
- Simplifica troubleshooting futuro

### Verificación de Integridad
- Comparar conteos es crítico
- Verificar API keys es crítico
- Smoke tests son obligatorios
- Monitoreo post-deploy es esencial

---

## 🎯 Checklist Pre-Ejecución

Antes de empezar, verificar:

- [ ] Local funcionando correctamente (http://localhost:5000)
- [ ] Railway Dashboard accesible
- [ ] Credenciales PostgreSQL de Railway funcionando
- [ ] pg_dump y psql instalados y en PATH
- [ ] Python scripts (railway_db_tool.py, local_db_tool.py) funcionando
- [ ] Espacio en disco suficiente para backups (~100MB)
- [ ] Tiempo disponible (~1.5 horas sin interrupciones)
- [ ] Acceso a git y permisos para push a Railway
- [ ] Plan de comunicación a usuarios sobre downtime

---

**Última actualización**: 13 Noviembre 2025
**Autor**: GitHub Copilot + Juan
**Versión**: 2.0 - Full Migration Strategy
