# 🚀 Guía de Deploy a Railway - CLIP Comparador V2

## 📋 Tabla de Contenidos
- [Deploy Interactivo](#deploy-interactivo-recomendado)
- [Deploy Rápido](#deploy-rápido)
- [Troubleshooting](#troubleshooting)
- [Rollback](#rollback-en-caso-de-problemas)

---

## 🎯 Deploy Interactivo (RECOMENDADO)

### Script: `deploy_to_railway.ps1`

Este es el método recomendado para la mayoría de deploys. Incluye validaciones, guías y buenas prácticas.

### Uso Básico

```powershell
.\deploy_to_railway.ps1
```

### Ejemplo de Sesión Completa

```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           🚀 DEPLOY A RAILWAY - CLIP Comparador V2        ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

📊 Verificando estado del repositorio...

✓ Cambios detectados:

 M clip_admin_backend/app/blueprints/api.py
 M docs/TOOLS_REFERENCE.md

📝 Selecciona el tipo de cambio:

  1) feat     - Nueva funcionalidad
  2) fix      - Corrección de bug
  3) refactor - Refactorización de código
  4) perf     - Mejora de performance
  5) style    - Cambios de formato/estilo
  6) docs     - Documentación
  7) test     - Tests
  8) chore    - Mantenimiento
  9) hotfix   - Corrección urgente en producción

Selecciona una opción (1-9): 1

✍️  Describe el cambio o funcionalidad:
(Sé específico y conciso, ej: 'agregar filtro por color en búsqueda')

Mensaje: agregar condicional de interpretación de categoría

🧪 ¿Ejecutaste tests locales?
(s/n): s

📋 ¿Agregar notas adicionales? (opcional)
(s/n): n

============================================================
RESUMEN DEL DEPLOY
============================================================

Tipo:    feat
Mensaje: feat: agregar condicional de interpretación de categoría

 M clip_admin_backend/app/blueprints/api.py
 M docs/TOOLS_REFERENCE.md
============================================================

⚠️  ¿Estás seguro de hacer deploy a Railway?
Esto ejecutará automáticamente en producción.

Confirmar (s/n): s

🔄 Ejecutando deploy...

1️⃣  Agregando archivos...
2️⃣  Creando commit...
3️⃣  Subiendo a Railway...

Enumerating objects: 11, done.
Counting objects: 100% (11/11), done.
Delta compression using up to 12 threads
Compressing objects: 100% (6/6), done.
Writing objects: 100% (6/6), 777 bytes | 155.00 KiB/s, done.
Total 6 (delta 5), reused 0 (delta 0), pack-reused 0
To https://github.com/JuanCabardoneschi/CLIP_Comparador_V2.git
   0e0186b..e2a2fe1  main -> main

╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║                    ✅ DEPLOY EXITOSO                      ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

🔗 Railway está procesando el deploy automáticamente
📊 Monitorea el progreso en: https://railway.app/

⏱️  El deploy típicamente tarda 2-5 minutos
🔍 Verifica los logs en Railway para confirmar que todo funciona

⚠️  Recomendaciones post-deploy:
   1. Verificar logs de Railway por errores
   2. Probar endpoint de salud: /api/health
   3. Ejecutar búsqueda de prueba
   4. Revisar métricas de uso de recursos
```

### Opciones Avanzadas

```powershell
# Saltar pregunta de tests
.\deploy_to_railway.ps1 -SkipTests

# Forzar deploy desde branch diferente a main
.\deploy_to_railway.ps1 -Force
```

---

## ⚡ Deploy Rápido

### Script: `quick_deploy.ps1`

Para cambios pequeños, fixes urgentes o cuando ya sabes exactamente qué commitear.

### Uso Básico

```powershell
# Interactivo
.\quick_deploy.ps1

# Con parámetros (más rápido)
.\quick_deploy.ps1 -Type "fix" -Message "corregir validación de stock"
```

### Ejemplo de Sesión

```
🚀 Quick Deploy a Railway

Describe el cambio: corregir mensaje de error en búsqueda

Commit: fix: corregir mensaje de error en búsqueda
 M clip_admin_backend/app/blueprints/api.py

¿Continuar? (s/n): s

📦 Ejecutando deploy...

[main e2a2fe1] fix: corregir mensaje de error en búsqueda
 1 file changed, 2 insertions(+), 2 deletions(-)

Enumerating objects: 9, done.
Counting objects: 100% (9/9), done.
...
To https://github.com/JuanCabardoneschi/CLIP_Comparador_V2.git
   abc1234..e2a2fe1  main -> main

✅ Deploy exitoso - Railway está procesando...
🔗 https://railway.app/
```

### Tipos de Commit Disponibles

| Tipo | Descripción | Ejemplo |
|------|-------------|---------|
| `feat` | Nueva funcionalidad | "agregar filtro por precio" |
| `fix` | Corrección de bug | "corregir búsqueda de colores" |
| `refactor` | Refactorización | "reorganizar módulo de búsqueda" |
| `perf` | Mejora de performance | "optimizar queries de BD" |
| `style` | Formato/estilo | "formatear código con black" |
| `docs` | Documentación | "actualizar README con API" |
| `test` | Tests | "agregar tests de integración" |
| `chore` | Mantenimiento | "actualizar dependencias" |
| `hotfix` | Urgente en producción | "fix crítico en autenticación" |

---

## 🤔 ¿Cuál Script Usar?

### Usa `deploy_to_railway.ps1` cuando:
- ✅ Es un cambio importante o feature nueva
- ✅ Quieres validaciones y guía paso a paso
- ✅ Necesitas agregar notas detalladas
- ✅ Estás aprendiendo el flujo de deploy
- ✅ Quieres ver resumen completo antes de commitear

### Usa `quick_deploy.ps1` cuando:
- ⚡ Es un fix pequeño o typo
- ⚡ Ya testeaste y estás seguro del cambio
- ⚡ Necesitas deployar rápido (hotfix)
- ⚡ El commit message es simple y directo
- ⚡ Ya conoces el proceso y no necesitas guía

---

## 🔍 Monitoreo Post-Deploy

### 1. Verificar Logs en Railway

```powershell
# Si tienes Railway CLI instalado
railway logs --tail
```

O desde el Dashboard: https://railway.app/project/[tu-proyecto]/deployments

### 2. Probar Endpoints

```powershell
# Health check
Invoke-RestMethod -Uri "https://clip-comparador-v2.railway.app/api/health"

# Listar clientes
Invoke-RestMethod -Uri "https://clip-comparador-v2.railway.app/api/clients/list"
```

### 3. Verificar Status del Deploy

Railway Dashboard → Deployments → Ver logs del último deploy

**Buscar por**:
- ✅ "Build successful"
- ✅ "Deployment successful"
- ❌ Errores en logs
- ⚠️ Warnings de dependencias

---

## 🚨 Troubleshooting

### Deploy Falla: "Build failed"

**Posibles causas**:
1. Error de sintaxis en Python
2. Dependencia faltante en requirements.txt
3. Variables de entorno no configuradas

**Solución**:
```powershell
# Verificar localmente primero
python -m py_compile clip_admin_backend/app.py
python -m flake8 clip_admin_backend/

# Ver logs específicos en Railway
railway logs --deployment [deployment-id]
```

### Deploy Exitoso pero App No Responde

**Posibles causas**:
1. Base de datos no conecta
2. Redis no disponible
3. Puerto incorrecto

**Solución**:
1. Verificar variables de entorno en Railway:
   - `DATABASE_URL`
   - `REDIS_URL`
   - `PORT` (debe ser asignado por Railway)
2. Ver logs de runtime en Railway Dashboard
3. Verificar health endpoint

### Cambios No se Reflejan

**Posibles causas**:
1. Caché del navegador
2. Deploy aún procesando
3. Cambios no comiteados

**Solución**:
```powershell
# Verificar status de git
git status

# Ver último commit
git log -1

# Verificar que se hizo push
git log origin/main -1

# Limpiar caché del navegador o probar en incógnito
```

---

## 🔄 Rollback en Caso de Problemas

### Método 1: Desde Railway Dashboard (MÁS RÁPIDO)

1. Ir a Railway Dashboard → Deployments
2. Seleccionar el deploy anterior (que funcionaba)
3. Click en "Redeploy"
4. Confirmar

**Ventaja**: No requiere git, deploy inmediato

### Método 2: Git Revert

```powershell
# Ver últimos commits
git log --oneline -5

# Revertir el último commit
git revert HEAD

# O revertir un commit específico
git revert [commit-hash]

# Push del revert
git push origin main
```

**Ventaja**: Mantiene historial completo en git

### Método 3: Git Reset (CUIDADO)

```powershell
# SOLO usar si el commit malo aún no fue pusheado
git reset --soft HEAD~1   # Mantiene cambios en staging
git reset --hard HEAD~1   # ELIMINA cambios (PELIGROSO)

# Si ya hiciste push, necesitas force push (EVITAR EN PRODUCCIÓN)
git push --force origin main  # ⚠️ PELIGROSO
```

**⚠️ Warning**: Git reset con force push puede causar problemas en equipos.

---

## 📚 Recursos Adicionales

- **Railway Dashboard**: https://railway.app/
- **Documentación Railway**: https://docs.railway.app/
- **TOOLS_REFERENCE.md**: Referencia completa de scripts
- **README.md**: Documentación principal del proyecto

---

## 💡 Tips y Mejores Prácticas

### Antes de Deployar

- ✅ Ejecutar tests localmente
- ✅ Verificar que la app corre en local
- ✅ Revisar archivos modificados con `git status`
- ✅ Hacer backup de BD si es cambio crítico

### Durante el Deploy

- ✅ Usar mensajes de commit descriptivos
- ✅ Agrupar cambios relacionados en un commit
- ✅ No mezclar features con fixes en el mismo commit
- ✅ Agregar notas si el cambio requiere acciones manuales

### Después del Deploy

- ✅ Verificar logs inmediatamente
- ✅ Probar funcionalidad modificada
- ✅ Monitorear métricas por 5-10 minutos
- ✅ Avisar al equipo de cambios importantes

### Commits Semánticos

```
feat: nueva funcionalidad
fix: corrección de bug
refactor: cambio de código sin modificar funcionalidad
perf: mejora de performance
style: cambios de formato
docs: documentación
test: tests
chore: mantenimiento
```

---

**Última actualización**: 16 de Noviembre, 2025
