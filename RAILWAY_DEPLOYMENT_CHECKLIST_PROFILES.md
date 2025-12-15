# Railway Deployment Checklist - Profiles System

## Pre-Deployment (Local)

- [x] Validar sintaxis Python: `py_compile` exitoso en all modules
- [x] Código commiteado: `9851f5f` (profiles) + `00a80cc` (docs)
- [x] Imports validados: SearchProfilesService importa correctamente
- [x] Blueprint registrado en `app.py`
- [x] Templates creados: `list.html` y `edit.html`
- [x] Documentación completada: `SEARCH_PROFILES_SYSTEM.md`
- [x] Fallback chain implementado (profile → module → generic)

## Deploy Steps

### Step 1: Push a Railway
```powershell
# Verificar remoto
git remote -v

# Push (ya hecho en commit anterior)
git push origin main
```
**Status:** ✅ Completado en commit anterior

### Step 2: Verificar Logs en Railway
```
Railway Dashboard → Services → clip-admin-backend → Logs
Buscar:
- "[SearchProfilesService] Initializing..."
- "Blueprint 'search_profiles_admin' registered"
- "No errors in imports"
```

### Step 3: Validar Endpoints

#### A) Admin List
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://clip-comparador-v2-prod.up.railway.app/search-profiles-admin/profiles
```
**Expected:** HTML con tabla de clientes

#### B) Available Profiles
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  -X POST \
  https://clip-comparador-v2-prod.up.railway.app/search-profiles-admin/profiles/available
```
**Expected:** JSON con lista de perfiles (fashion, uniforms, generic)

#### C) Client Edit Form
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://clip-comparador-v2-prod.up.railway.app/search-profiles-admin/client/{client_id}/edit
```
**Expected:** HTML con formulario de edición

### Step 4: Test Preview Widget
1. Navegar a `/search-profiles-admin/client/{client_id}/edit` (desde navegador)
2. Ingresar query: "short rojo"
3. Esperado:
   - Normalized tokens: `["short", "rojo"]`
   - Expanded: `["short", "rojo", "shore", "shores"]` (si existen sinónimos)
   - Categories detected: IDs de categorías con "short"

### Step 5: Test Integration con Search
1. Crear query de búsqueda en Search API: `POST /api/search`
   ```json
   {
     "query": "short rojo",
     "api_key": "{tiendanube_api_key}",
     "limit": 10
   }
   ```
2. Verificar logs: `SearchProfilesService.normalize_tokens()` debe ejecutarse
3. Respuesta debe usar perfil fashion (si cliente es fashion)

### Step 6: Test Fallback Chain
1. Para cliente sin industria asignada:
   - Debe usar módulo custom (si existe: Eve/Demo)
   - Si no existe módulo: usar genérico
2. Verificar en logs:
   ```
   [search_text.py] Using profile fallback: {profile_name}
   [search_text.py] Using custom module: {module_name}
   [search_text.py] Using generic fallback
   ```

### Step 7: Test Cache Invalidation
1. Editar overrides para cliente fashion:
   - Agregar variante custom: "pollerita" → "falda"
2. Guardar (POST `/search-profiles-admin/client/{id}/edit`)
3. Verificar en Redis:
   ```bash
   redis-cli GET "profile:{client_id}:fashion"
   # Debe estar vacío (invalidado)
   ```
4. Hacer preview nuevamente:
   - Nuevo perfil cacheado
   - Variante custom visible

## Database Migrations

- **Status:** No se requieren migraciones nuevas
- **Razón:** Se usa campo existente `Client.integration_config` (JSON)
- **Validación:** Ejecutar en Railway DB:
  ```sql
  SELECT id, integration_config->>'search_rules' AS rules
  FROM clients LIMIT 5;
  ```
  **Expected:** `rules` es NULL (sin overrides) o JSON válido

## Rollback Plan

Si hay problemas:

1. **Quick Rollback:**
   ```bash
   git revert {commit_hash}  # Revert individual commit
   git push origin main
   # Railway redeploy automático
   ```

2. **Disable profiles (keep modules):**
   - Editar `search_text.py`: comentar `SearchProfilesService.get_profile()`
   - Fallback automático a módulos custom

3. **Full Rollback:**
   ```bash
   git reset --hard HEAD~2  # Volver 2 commits atrás
   git push -f origin main  # Force push
   ```

## Performance Monitoring

### Métricas a monitorear (primeras 24h):

1. **Redis Hit Rate** (Dashboard → Redis)
   - Esperado: >90% para profiles (caché 1h)
   - Si <80%: Aumentar TTL o revisar invalidación

2. **Query Response Time** (Search API)
   - Antes: ~800ms
   - Esperado con profiles: ~750-800ms (sin degradación)
   - Si >900ms: Revisar normalization/expansion performance

3. **Memory Usage** (Railway Metrics)
   - Pequeño incremento (~50MB) por caché de perfiles
   - Si >500MB: Revisar leak en SearchProfilesService

4. **Error Logs**
   - Buscar: `Exception`, `KeyError`, `AttributeError`
   - Si >1% de requests: Critical issue, rollback

### Queries de monitoreo

```sql
-- Clientes con industry asignado
SELECT industry, COUNT(*) FROM clients
WHERE industry IS NOT NULL GROUP BY industry;

-- Clientes con overrides (customizaciones)
SELECT COUNT(*) FROM clients
WHERE integration_config->'search_rules' IS NOT NULL;
```

## Post-Deployment Validation

- [ ] All 5 endpoints responding
- [ ] Cache working (Redis logs show hits)
- [ ] Fallback chain functional
- [ ] Search API returning results with profile optimization
- [ ] No errors in application logs (24h)
- [ ] Response time within SLA

## Communication

**To stakeholders:**
> Sistema de perfiles de búsqueda deployde. TiendaNube clients ahora soportan búsqueda optimizada por industria sin módulos custom. Admin UI disponible en `/search-profiles-admin/profiles`.

**To support:**
- Si cliente reporta: "búsqueda no funciona"
  - Verificar: `client.industry` está asignado
  - Verificar: Perfil visible en `/search-profiles-admin/profiles`
  - Si industrial is NULL: Asignar manualmente o esperar próxima sincronización

---

## Success Criteria

✅ **Deploy successful** cuando:
1. ✅ Endpoints retornan 200 (no 500)
2. ✅ TiendaNube client (con fashion categories) sincroniza → industry='fashion'
3. ✅ Admin UI muestra cliente con perfil fashion
4. ✅ Search queries retornan resultados consistentes
5. ✅ Response time ≤ SLA (sin degradación)
6. ✅ No errors en logs (24h observación)

---

**Deployment Date:** 2025-01-XX
**Deployed By:** [Your Name]
**Status:** Ready for Railway Deploy
