# Política de Base de Datos - CLIP Comparador V2

## ⚠️ IMPORTANTE: Solo PostgreSQL Soportado

Este proyecto **SOLO soporta PostgreSQL** como base de datos. SQLite NO está soportado y cualquier referencia a SQLite es obsoleta o pertenece a módulos no utilizados.

---

## 🗄️ Configuración de Base de Datos

### ✅ Producción (Railway)
- **Base de datos**: PostgreSQL 17.6
- **Host**: ballast.proxy.rlwy.net (Railway)
- **Configuración**: Variables de entorno en Railway Dashboard
- **URL**: Configurada automáticamente por Railway

### ✅ Desarrollo Local
- **Base de datos**: PostgreSQL 18.0+ (instalado localmente)
- **Host**: localhost
- **Puerto**: 5432
- **Base de datos**: `clip_comparador_v2`
- **Configuración**: Archivo `.env.local`

---

## 📋 Configuración Requerida

### Archivo `.env.local` (Desarrollo)
```bash
DATABASE_URL=postgresql://postgres:PASSWORD@localhost:5432/clip_comparador_v2
```

**NOTA**: Si tu password contiene caracteres especiales como `@`, debes encodearlos:
- `@` → `%40`
- `#` → `%23`
- `/` → `%2F`

Ejemplo:
```bash
# Password: Laurana@01
DATABASE_URL=postgresql://postgres:Laurana%4001@localhost:5432/clip_comparador_v2
```

---

## 🚫 SQLite NO Soportado

### Razones Técnicas

1. **UUIDs Nativos**: PostgreSQL soporta UUID nativo
2. **Vectores de Embeddings**: Necesitamos pgvector para CLIP
3. **JSON Avanzado**: Campos JSONB para configuraciones
4. **Transacciones**: ACID completo para operaciones críticas
5. **Concurrencia**: Multi-tenant requiere locks apropiados

### Referencias Obsoletas a SQLite

Las siguientes referencias a SQLite son **obsoletas** y se mantienen solo para contexto histórico:

- ❌ `clip_search_api/app/middleware/auth.py` - Módulo FastAPI no usado actualmente
- ❌ `clip_search_api/app/core/search_engine.py` - Módulo FastAPI no usado actualmente
- ❌ `.env` (DATABASE_URL con sqlite) - Solo se usa si NO existe `.env.local`

---

## ✅ Validaciones Implementadas

### En `config.py`:
```python
def get_database_url():
    db_url = os.environ.get('DATABASE_URL')

    # Validar que sea PostgreSQL
    if not (db_url.startswith('postgresql://') or db_url.startswith('postgres://')):
        raise ValueError("DATABASE_URL debe ser PostgreSQL, no SQLite")

    return db_url
```

### Detección de Entorno:
```python
def is_production():
    # Detecta si DATABASE_URL apunta a Railway
    db_url = os.environ.get('DATABASE_URL', '')
    if 'railway.app' in db_url or 'railway.internal' in db_url:
        return True
    return False
```

---

## 🔧 Instalación de PostgreSQL Local

### Windows
```powershell
# 1. Descargar PostgreSQL 18.0+
# https://www.postgresql.org/download/windows/

# 2. Instalar y configurar password

# 3. Agregar al PATH
$env:PATH += ";C:\Program Files\PostgreSQL\18\bin"

# 4. Crear base de datos
psql -U postgres -c "CREATE DATABASE clip_comparador_v2;"

# 5. Restaurar datos desde Railway
.\restore_from_railway.ps1
```

### macOS
```bash
# Usar Homebrew
brew install postgresql@18
brew services start postgresql@18

# Crear base de datos
createdb clip_comparador_v2
```

### Linux
```bash
# Ubuntu/Debian
sudo apt install postgresql-18
sudo systemctl start postgresql

# Crear base de datos
sudo -u postgres createdb clip_comparador_v2
```

---

## 🔍 Verificación de Configuración

### Comando para verificar conexión:
```powershell
$env:PGPASSWORD='TU_PASSWORD'
psql -U postgres -d clip_comparador_v2 -c "SELECT current_database(), version();"
```

### Verificar que Flask usa la BD correcta:
```powershell
# Al iniciar el servidor, debes ver:
🗄️  Database: postgresql://postgres:****@localhost:5432/clip_comparador_v2
```

---

## 📊 Estructura de Base de Datos

### Tablas Principales
- `clients` - Clientes del sistema (multi-tenant)
- `users` - Usuarios por cliente
- `categories` - Categorías con centroides CLIP
- `products` - Productos por categoría
- `images` - Imágenes con embeddings
- `api_keys` - Keys de API (opcional)

### Extensiones PostgreSQL
- `uuid-ossp` - Generación de UUIDs
- `pgcrypto` - Funciones criptográficas

### Tipos de Datos Especiales
- `UUID` - IDs únicos para multi-tenant
- `JSONB` - Configuraciones y metadata
- `TIMESTAMP` - Timestamps con timezone
- `TEXT[]` - Arrays de texto (tags, términos)

---

## 🚀 Migración de Datos

### Desde Railway a Local
```powershell
# Usar script automatizado
.\restore_from_railway.ps1

# O manual con pg_dump
$env:PGPASSWORD='RAILWAY_PASSWORD'
pg_dump -h ballast.proxy.rlwy.net -p 54363 -U postgres -d railway -f backup.sql
psql -U postgres -d clip_comparador_v2 -f backup.sql
```

### De Local a Railway
```powershell
# Backup local
pg_dump -U postgres -d clip_comparador_v2 -f local_backup.sql

# Restaurar en Railway (NO RECOMENDADO - usar Git deploy)
# Es mejor hacer cambios en local y deployar código
```

---

## 📝 Notas Importantes

1. **Nunca uses SQLite** - El sistema lo rechazará con error
2. **Password encoding** - Recuerda encodear caracteres especiales en la URL
3. **Backups regulares** - Usa `pg_dump` para respaldos
4. **Multi-tenant** - Todas las tablas tienen `client_id`
5. **UUIDs como String** - Almacenados como String(36) para compatibilidad

---

## 🆘 Troubleshooting

### Error: "could not translate host name"
- **Causa**: Password con `@` no encodeado
- **Solución**: Cambiar `@` por `%40` en DATABASE_URL

### Error: "DATABASE_URL debe ser PostgreSQL"
- **Causa**: Intentando usar SQLite o URL malformada
- **Solución**: Verificar formato `postgresql://user:pass@host:5432/db`

### Error: "database does not exist"
- **Causa**: BD no creada
- **Solución**: `psql -U postgres -c "CREATE DATABASE clip_comparador_v2;"`

### Error: "password authentication failed"
- **Causa**: Password incorrecta
- **Solución**: Verificar password en `.env.local`

---

**Última actualización**: 17 de Octubre, 2025
**PostgreSQL Versión Mínima**: 15.0
**PostgreSQL Versión Recomendada**: 18.0+
