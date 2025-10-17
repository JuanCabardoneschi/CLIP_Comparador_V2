# Resumen de Migración BD Railway → Local
**Fecha**: 17 de Octubre, 2025

## ✅ Tareas Completadas

### 1. PostgreSQL Agregado al PATH
```powershell
$env:PATH += ";C:\Program Files\PostgreSQL\18\bin"
```
- ✅ Ahora puedes ejecutar `psql` directamente desde cualquier ubicación

### 2. Base de Datos Local Creada
- ✅ Nombre: `clip_comparador_v2`
- ✅ Usuario: `postgres`
- ✅ Password: `Laurana@01`
- ✅ Puerto: 5432

### 3. Estructura y Datos Restaurados desde Railway

#### Archivos Exportados
- `railway_schema.sql` (11 KB) - Estructura de tablas
- `railway_data.sql` (2.7 MB) - Datos completos
- `railway_full_backup.sql` (2.7 MB) - Backup completo

#### Datos Migrados
```
Tabla       | Registros
------------|----------
clients     |         1
users       |         2
categories  |        12
products    |        51
images      |        58
api_keys    |         1
```

### 4. Cliente Demo Verificado
```
Nombre: Demo Fashion Store
Email: admin@demo.com
Threshold Categoría: 60%
Threshold Productos: 30%
Estado: Activo
```

### 5. Categorías con Centroides
```
DELANTAL                 → 22 imágenes
CHAQUETAS                →  9 imágenes
CAMISAS HOMBRE- DAMA     →  8 imágenes
CASACAS                  →  5 imágenes
GORROS û GORRAS          →  5 imágenes
(y 7 categorías más)
```

## ⚠️ Pendiente

### Credenciales de Cloudinary
El archivo `.env.local` existe pero necesita las credenciales de Cloudinary:

```bash
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

**Opciones para obtenerlas:**
1. **Railway Dashboard**: https://railway.app → Variables de entorno
2. **Cloudinary Console**: https://cloudinary.com/console
3. **Copiar desde producción**: Acceder a Railway y copiar las variables

## 🚀 Próximos Pasos

### 1. Completar .env.local
```powershell
# Editar el archivo
notepad .env.local

# Agregar las 3 variables de Cloudinary
```

### 2. Probar el Sistema Localmente
```powershell
# Terminal 1 - Activar entorno virtual
& C:/Personal/CLIP_Comparador_V2/venv/Scripts/Activate.ps1

# Terminal 2 - Ejecutar Flask Admin
cd clip_admin_backend
python app.py
```

### 3. Verificar Funcionamiento
- URL Local: http://localhost:5000
- Login Admin: `admin` / `admin123`
- Login Demo: `demo` / `demo123`

## 📊 Estructura de Base de Datos

### Tablas Principales
1. **clients** - Clientes del sistema (multi-tenant)
2. **users** - Usuarios de cada cliente
3. **categories** - Categorías con centroides CLIP
4. **products** - Productos por categoría
5. **images** - Imágenes con embeddings CLIP
6. **api_keys** - Keys para API de búsqueda
7. **image_embeddings** - Vectores de embeddings

### Features Clave
- ✅ UUID como IDs primarios
- ✅ Extensiones: pgcrypto, uuid-ossp
- ✅ Triggers para updated_at automático
- ✅ Constraints de sensibilidad (1-100%)
- ✅ Foreign keys con CASCADE
- ✅ Índices optimizados para centroides

## 🔧 Comandos Útiles

### Conectar a BD Local
```powershell
$env:PGPASSWORD='Laurana@01'
psql -U postgres -d clip_comparador_v2
```

### Consultas Útiles
```sql
-- Ver clientes
SELECT name, email, category_confidence_threshold FROM clients;

-- Ver categorías con embeddings
SELECT name, centroid_image_count FROM categories WHERE centroid_embedding IS NOT NULL;

-- Ver productos por categoría
SELECT c.name, COUNT(p.id) as productos
FROM categories c
LEFT JOIN products p ON c.id = p.category_id
GROUP BY c.name;
```

### Respaldar BD Local
```powershell
$env:PGPASSWORD='Laurana@01'
pg_dump -U postgres -d clip_comparador_v2 -f backup_local_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql
```

## 📝 Notas Técnicas

### PostgreSQL 18.0
- Versión más reciente instalada
- Compatible con Railway (PostgreSQL 17.6)
- Todas las extensiones soportadas

### Credenciales Railway
- Host: `ballast.proxy.rlwy.net`
- Puerto: `54363`
- Base de datos: `railway`
- Usuario: `postgres`

### Sistema Multi-Tenant
- Cada tabla tiene `client_id` (UUID)
- Aislamiento completo de datos
- API Keys individuales por cliente
- Configuraciones personalizadas de sensibilidad

---

**Estado**: ✅ Base de datos local lista y funcional
**Próximo paso**: Agregar credenciales de Cloudinary a `.env.local`
