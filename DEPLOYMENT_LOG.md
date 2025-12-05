# Deployment Log - CLIP Comparador V2

## 🚀 Deployments a Railway (Producción)

---

### Pre-Deploy: Estado Actual en Railway (4 Dic 2025)
**Versión en Producción**: `v2.3.2-tiendanube.1`
**Última actualización**: 4 Diciembre 2025
**Commit Hash Railway**: (por determinar - verificar en Railway dashboard)
**Endpoint**: https://clip-comparador-v2-production.up.railway.app

**Características en Producción**:
- ✅ Sistema de Inventario (API Externa + Panel Admin)
- ✅ Atributos Dinámicos de Productos (CRUD completo)
- ✅ Auto-completado de Atributos con CLIP
- ✅ SearchOptimizer con pesos configurables (60/30/10)
- ✅ Búsqueda Multi-Categoría (adaptativa strict/lax)
- ✅ Detección de Color por Paleta de Categoría
- ✅ Migración de Búsqueda Textual (COMPLETADA 31 Oct)

**Estado de BD en Railway**:
- Clientes: Demo Fashion Store, Eve's Store (datos reales)
- Productos: ~30+ productos con atributos JSONB
- Embeddings: CLIP embeddings generados y centroides calculados

---

### 🎯 Deploy Actual: v2.3.0-pre.1 (2 Nov 2025)
**Estado**: ✅ DEPLOYADO EN RAILWAY
**Tipo**: Pre-release (testing de mejoras multi-categoría)
**Fecha deploy**: 2 Noviembre 2025 ~19:00 ART
**Commit**: `b91ffbe`

**Cambios Incluidos**:
1. **Mejoras Multi-Categoría**:
   - Fix: Filtro de diversidad conservador (skip cuando ≤2 categorías)
   - Threshold de diversidad aumentado a 0.80 (evita colapsar prendas distintas)
   - Logs mejorados para debugging

2. **Herramientas de Sincronización**:
   - Script `tools/sync/clone_client_from_railway.py` para replicar clientes en local

3. **Documentación**:
   - Análisis de pesos Visual/Metadata/Business en BACKLOG_MEJORAS.md
   - Plan para diales personalizados y consolidación de hardcodes

**Archivos Modificados**:
- `clip_admin_backend/app/blueprints/api.py` (diversity filter logic)
- `BACKLOG_MEJORAS.md` (análisis y roadmap)
- `tools/sync/clone_client_from_railway.py` (nuevo)

**Commit Base**: `b977d4f` - "fix: indentación en diversity filter (syntax error)"

**Testing Pre-Deploy**:
- [x] Validar en local con datos de Eve's Store clonados
- [x] Probar imagen de shorts+musculosa (debe devolver 2 categorías)
- [x] Probar imagen de delantal (debe devolver DELANTAL y CHAQUETAS)
- [x] Verificar que diversity filter no colapsa categorías válidas

**Testing Post-Deploy en Railway**:
- [ ] Verificar endpoint health: https://clip-comparador-v2-production.up.railway.app/health
- [ ] Probar búsqueda visual multi-categoría con imagen de prueba
- [ ] Validar panel de administración de Eve's Store
- [ ] Confirmar logs de diversity filter en Railway
- [ ] Verificar que clientes existentes no se vieron afectados

**Rollback Plan**:
- Si falla el deploy → Railway auto-rollback al último deployment exitoso
- Si falla en runtime → Revertir a tag `v2.2.0-stable` manualmente
- Comando rollback: `git checkout v2.2.0-stable && railway up`

---

## 📋 Historial de Deployments

### v2.3.2-tiendanube.1 (4 Dic 2025) 🆕
- Auto-login para TiendaNube (/tiendanube/config endpoint)
- Sincronización de productos via webhooks
- Generación de embeddings CLIP en webhooks
- Filtrado de productos inactivos en UI
- **Status**: ✅ DEPLOYADO A RAILWAY
- **Commits**:
  - c0e1af3: feat: Implement auto-login at `/tiendanube/config`
  - 70ed69c: fix: Correct User query (active vs is_active)
  - 23816c8: fix: Fix embedding generation in webhooks (remove CLIPService import)
  - 36ac3b4: fix: Filtrar productos inactivos en la lista
- **Rollback**: v2.3.0-pre.1 disponible

### v2.3.0-pre.1 (2 Nov 2025)
- Mejoras diversity filter multi-categoría
- Tool de sincronización Railway→Local
- Análisis pesos optimizer
- **Status**: ✅ EN PRODUCCIÓN (PRE-RELEASE)
- **Commit**: b91ffbe
- **Rollback**: v2.2.0-stable disponible

### v2.2.0-stable (31 Oct 2025)
- Sistema de Inventario completo
- Migración de Búsqueda Textual
- Auto-completado de Atributos
- **Status**: ✅ ESTABLE EN PRODUCCIÓN

### v2.1.0-stable (Octubre 2025)
- SearchOptimizer implementado
- Atributos dinámicos JSONB
- **Status**: ✅ REEMPLAZADO

### v2.0.0-stable (Octubre 2025)
- Lanzamiento inicial Railway
- Multi-tenancy completo
- **Status**: ✅ REEMPLAZADO

---

## 🔄 Proceso de Rollback

### Rollback Automático (Railway)
Railway mantiene los últimos deployments. En caso de fallo:
1. Dashboard Railway → Deployments
2. Seleccionar deployment anterior exitoso
3. Click "Redeploy"

### Rollback Manual (Git)
```bash
# Ver versiones disponibles
git tag --list "v*" | sort -V

# Checkout a versión anterior
git checkout v2.2.0-stable

# Forzar deploy
railway up --detach

# Volver a main después
git checkout main
```

### Verificación Post-Rollback
- [ ] Verificar endpoint: https://clip-comparador-v2-production.up.railway.app/health
- [ ] Probar búsqueda visual con imagen de prueba
- [ ] Validar panel de administración
- [ ] Confirmar que clientes pueden acceder a sus datos

---

## 📝 Notas

- Siempre crear backup de BD Railway antes de deploy importante
- Validar migraciones en local primero (usar restore_from_railway.ps1)
- Deployments de pre-release solo para testing, no para clientes finales
- Mantener este log actualizado en cada deploy
