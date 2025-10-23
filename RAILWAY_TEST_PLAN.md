# Plan de Pruebas Railway - Post Deploy Fase 1

**Fecha:** 23 de Octubre 2025
**Cambios:** Commit 4527bc5 - FASE 1 StoreSearchConfig
**Riesgo:** 🟢 BAJO (modelo nuevo sin uso en API)

---

## 🎯 Objetivo
Verificar que los cambios del commit FASE 1 no hayan afectado funcionalidades existentes del sistema en producción.

---

## 📋 Checklist de Pruebas

### **NIVEL 1: CRÍTICO** ⚠️ (Obligatorio antes de continuar)

#### 1.1 Health Check Básico
```bash
# URL: https://clip-comparador-v2-production.up.railway.app/
# Verificar: Página de inicio carga sin errores 500
```
- [ ] ✅ Respuesta 200 OK
- [ ] ✅ No hay errores en consola del navegador
- [ ] ✅ CSS/JS carga correctamente

#### 1.2 Inicio de Sesión
```bash
# URL: https://clip-comparador-v2-production.up.railway.app/auth/login
# Usuario: admin@clip.com
# Password: [password configurado]
```
- [ ] ✅ Login exitoso
- [ ] ✅ Redirección a dashboard
- [ ] ✅ Sesión se mantiene

#### 1.3 API de Búsqueda (CRÍTICO)
```bash
# Endpoint: POST /api/search
# Test con widget: test-widget-railway.html
```
**Test A: Búsqueda por Imagen**
```javascript
// Abrir test-widget-railway.html en navegador
// 1. Subir imagen de prueba (ej: zapato)
// 2. Hacer clic en "Buscar Productos"
```
- [ ] ✅ API responde sin error 500
- [ ] ✅ Devuelve resultados JSON válidos
- [ ] ✅ Imágenes se muestran correctamente
- [ ] ✅ Scores de similitud presentes

**Test B: API Key Validation**
```bash
curl -X POST https://clip-comparador-v2-production.up.railway.app/api/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: INVALID_KEY" \
  -d '{"category": "test"}'
```
- [ ] ✅ Retorna 401 Unauthorized
- [ ] ✅ Mensaje de error apropiado

#### 1.4 Base de Datos - Nueva Tabla
```sql
-- Conectar a Railway PostgreSQL
-- Railway Dashboard > PostgreSQL > Connect

-- Verificar que la tabla existe
SELECT COUNT(*) FROM store_search_config;

-- Verificar estructura
\d store_search_config;
```
- [ ] ✅ Tabla existe en Railway
- [ ] ✅ Estructura correcta (7 columnas)
- [ ] ✅ Foreign key a clients funciona

---

### **NIVEL 2: FUNCIONAL** 🔵 (Recomendado)

#### 2.1 Navegación Admin Panel
```bash
# Después de login exitoso:
```
- [ ] Dashboard carga
- [ ] Menú "Clientes" accesible
- [ ] Menú "Categorías" accesible
- [ ] Menú "Productos" accesible

#### 2.2 CRUD de Productos
```bash
# URL: /products/list
```
- [ ] Lista de productos carga
- [ ] Imágenes de productos visibles
- [ ] Atributos dinámicos se muestran
- [ ] Filtros funcionan

#### 2.3 Embeddings CLIP
```bash
# Verificar que embeddings existentes siguen funcionando
# URL: /products/list
# Buscar productos con embeddings generados
```
- [ ] Productos con embeddings tienen ícono verde
- [ ] Al subir nuevo producto, embedding se genera
- [ ] Búsqueda por similitud visual funciona

---

### **NIVEL 3: REGRESIÓN** 🟡 (Opcional pero recomendado)

#### 3.1 Cloudinary Integration
```bash
# Subir nueva imagen de producto
```
- [ ] Subida exitosa a Cloudinary
- [ ] URL pública generada
- [ ] Thumbnail generado

#### 3.2 Redis Caching
```bash
# Verificar en Railway logs
# Buscar líneas con "Redis" o "cache"
```
- [ ] Redis conectado sin errores
- [ ] Cacheo de sesiones funciona

#### 3.3 Rate Limiting
```bash
# Hacer múltiples requests al API en corto tiempo
# Debería haber límite por API key
```
- [ ] Rate limit se activa después de X requests
- [ ] Respuesta 429 Too Many Requests

---

## 🔧 COMANDOS ÚTILES

### Conectar a Railway PostgreSQL
```bash
# Desde Railway Dashboard > PostgreSQL > Connect
psql postgresql://[CONNECTION_STRING]
```

### Ver Logs en Tiempo Real
```bash
# Railway CLI
railway logs --tail

# O desde Railway Dashboard > Deployments > [Latest] > Logs
```

### Verificar Variables de Entorno
```bash
railway variables

# O desde Railway Dashboard > Variables
```

---

## ⚠️ SI ALGO FALLA

### Rollback Rápido
```bash
# Revertir último commit
git revert HEAD
git push origin main

# O desde Railway Dashboard > Deployments > [Previous] > Redeploy
```

### Ejecutar Migración Manual (si tabla no existe)
```bash
# 1. Conectar a Railway PostgreSQL
psql postgresql://[CONNECTION_STRING]

# 2. Copiar y ejecutar SQL de create_migration.py
# Ver contenido del archivo para el SQL completo
```

### Verificar Estado de Migraciones
```bash
# Desde Railway shell
railway run python -c "from clip_admin_backend.app import db; print(db.engine.table_names())"
```

---

## 📊 RESULTADO ESPERADO

**Si todas las pruebas Nivel 1 pasan:**
✅ Sistema estable, seguro continuar con FASE 2

**Si alguna prueba Nivel 1 falla:**
🔴 Investigar y corregir antes de continuar
- Revisar Railway logs
- Verificar variables de entorno
- Comprobar estado de PostgreSQL
- Considerar rollback

---

## 📝 REGISTRO DE PRUEBAS

**Ejecutado por:** _________________
**Fecha:** _________________
**Hora:** _________________

**Resultados:**
- Nivel 1: ___/4 pruebas pasadas
- Nivel 2: ___/3 pruebas pasadas
- Nivel 3: ___/3 pruebas pasadas

**Observaciones:**
```
[Escribir aquí cualquier comportamiento inesperado o nota relevante]
```

**Estado Final:**
- [ ] ✅ TODO OK - Continuar con FASE 2
- [ ] ⚠️ ADVERTENCIAS - Revisar antes de continuar
- [ ] 🔴 FALLOS CRÍTICOS - Rollback necesario

---

## 🔗 Enlaces Útiles

- **Frontend:** https://clip-comparador-v2-production.up.railway.app/
- **Widget Test:** file:///c:/Personal/CLIP_Comparador_V2/test-widget-railway.html
- **Railway Dashboard:** https://railway.app/project/[PROJECT_ID]
- **Docs Internas:** `/docs/SENSITIVITY_VS_OPTIMIZERS.md`
