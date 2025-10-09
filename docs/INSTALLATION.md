# CLIP Comparador V2 - Guía de Instalación

## 🚀 Instalación Local

### Prerrequisitos

1. **Python 3.11+**
2. **PostgreSQL 15+** con extensión `pgvector`
3. **Redis 7+**
4. **Cuenta Cloudinary** (tier gratuito)

### Configuración de Base de Datos

#### PostgreSQL con pgvector

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# Instalar pgvector
sudo apt install postgresql-15-pgvector

# macOS con Homebrew
brew install postgresql pgvector

# Windows - usar PostgreSQL installer y compilar pgvector
```

#### Redis

```bash
# Ubuntu/Debian
sudo apt install redis-server

# macOS
brew install redis

# Windows
# Descargar desde https://redis.io/download
```

### Configuración del Proyecto

1. **Clonar y configurar:**

```bash
git clone <repository>
cd clip_comparador_v2

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
```

2. **Variables de entorno:**

```bash
# Copiar template
cp .env.example .env

# Editar .env con tus valores
nano .env
```

3. **Configurar base de datos:**

```bash
# Crear base de datos
createdb clip_comparador_v2

# Inicializar esquema y datos demo
python shared/database/init_db.py
```

### Ejecutar en Desarrollo

#### Terminal 1 - Backend Admin:
```bash
cd clip_admin_backend
python app.py
```

#### Terminal 2 - Search API:
```bash
cd clip_search_api
python main.py
```

### URLs de Desarrollo

- **Backend Admin:** http://localhost:5000
- **Search API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## 🌐 Deployment en Railway

### Configuración Railway

1. **Crear proyecto en Railway**
2. **Agregar PostgreSQL y Redis**
3. **Configurar dos servicios:**

#### Servicio 1: Backend Admin
- Dockerfile: `shared/docker/Dockerfile.admin`
- Puerto: 5000
- Variables de entorno: Ver `.env.example`

#### Servicio 2: Search API
- Dockerfile: `shared/docker/Dockerfile.search`
- Puerto: 8000
- Variables de entorno: Ver `.env.example`

### Variables de Entorno Railway

```bash
# Base de datos (automáticas)
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}

# Backend Admin
FLASK_SECRET_KEY=<generar-secreto-fuerte>
JWT_SECRET_KEY=<generar-jwt-secreto>
CLOUDINARY_CLOUD_NAME=<tu-cloud-name>
CLOUDINARY_API_KEY=<tu-api-key>
CLOUDINARY_API_SECRET=<tu-api-secret>

# Search API
API_TITLE=CLIP Search API
API_VERSION=2.0.0
CORS_ORIGINS=*
MAX_UPLOAD_SIZE=10485760
ENABLE_REDIS_CACHE=true
```

### Inicializar en Railway

```bash
# Conectar a Railway DB y ejecutar
railway run python shared/database/init_db.py
```

## 🔧 Configuración Avanzada

### Optimización PostgreSQL

```sql
-- En postgresql.conf
shared_preload_libraries = 'vector'
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
```

### Configuración Redis

```bash
# En redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
```

### Cloudinary Setup

1. Crear cuenta en [Cloudinary](https://cloudinary.com)
2. Obtener credenciales del Dashboard
3. Configurar en `.env`

## 🧪 Testing

```bash
# Tests Backend Admin
cd clip_admin_backend
python -m pytest tests/

# Tests Search API
cd clip_search_api
python -m pytest tests/
```

## 📊 Monitoreo

### Logs

```bash
# Backend Admin
tail -f logs/admin.log

# Search API  
tail -f logs/api.log
```

### Métricas

- Acceder a `/health` en ambos servicios
- Revisar logs de PostgreSQL y Redis
- Monitorear uso de memoria y CPU

## 🚨 Troubleshooting

### Problemas Comunes

#### Error de pgvector
```bash
# Verificar extensión
psql -d clip_comparador_v2 -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### Error de memoria CLIP
```bash
# Reducir workers en Railway
API_WORKERS=1
```

#### Error de conexión Redis
```bash
# Verificar URL de conexión
redis-cli ping
```

### Logs de Errores

#### Backend Admin
- Verificar logs Flask
- Revisar conexión PostgreSQL
- Validar credenciales Cloudinary

#### Search API
- Verificar carga de modelo CLIP
- Revisar conexión Redis
- Validar permisos API keys

## 📈 Escalabilidad

### Optimizaciones

1. **Base de Datos:**
   - Índices adicionales para queries frecuentes
   - Particionamiento por cliente
   - Read replicas

2. **Cache:**
   - Cache de embeddings en Redis
   - CDN para imágenes (Cloudinary)
   - Cache de resultados de búsqueda

3. **API:**
   - Load balancer
   - Rate limiting por cliente
   - Monitoreo y alertas

### Límites Railway Hobby

- **Memoria:** 512MB por servicio
- **CPU:** Compartido
- **Storage:** 5GB total
- **Bandwidth:** 100GB/mes

Para mayor capacidad, actualizar a Railway Pro.