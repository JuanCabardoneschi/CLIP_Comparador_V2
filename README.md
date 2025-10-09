# CLIP Comparador V2 - Sistema SaaS de Búsqueda Visual

## 🎯 Descripción
Sistema SaaS moderno de búsqueda visual inteligente con arquitectura dual optimizada para Railway Hobby Plan ($5/mes).

## 🏗️ Arquitectura Dual

### Módulo 1: Backend Admin (Flask)
- **Puerto:** 5000
- **Función:** Gestión de clientes, productos, categorías e imágenes
- **Stack:** Flask 3.x + PostgreSQL + Redis + Bootstrap 5 + Cloudinary
- **URL:** admin.clip-comparador.railway.app

### Módulo 2: Search API (FastAPI)
- **Puerto:** 8000
- **Función:** API de búsqueda visual con CLIP
- **Stack:** FastAPI + CLIP (ViT-B/16) + PostgreSQL (readonly) + Redis
- **URL:** api.clip-comparador.railway.app

## 📁 Estructura del Proyecto

```
clip_admin_backend/           # Módulo Backend Admin
├── app/
│   ├── models/              # Modelos SQLAlchemy
│   ├── blueprints/          # Rutas organizadas por funcionalidad
│   ├── static/              # CSS, JS, imágenes
│   ├── templates/           # Templates Jinja2
│   └── utils/               # Utilidades
├── migrations/              # Migraciones de base de datos
├── requirements.txt         # Dependencias específicas
└── app.py                   # Aplicación principal Flask

clip_search_api/             # Módulo Search API
├── app/
│   ├── core/               # CLIP Engine + Search Engine
│   ├── middleware/         # Autenticación + Rate Limiting
│   ├── models/             # Modelos Pydantic
│   └── utils/              # Database + Utilidades
├── requirements.txt        # Dependencias específicas
└── main.py                 # Aplicación principal FastAPI

shared/                      # Recursos compartidos
├── database/               # Scripts de inicialización
├── docker/                 # Dockerfiles
└── config/                 # Configuraciones comunes

docs/                       # Documentación
├── api/                    # Documentación de API
└── deployment/             # Guías de despliegue
```

## 🚀 Tecnologías Principales

### Backend Admin
- **Framework:** Flask 3.x con factory pattern
- **Base de Datos:** PostgreSQL con SQLAlchemy ORM
- **Autenticación:** Flask-Login + JWT
- **Frontend:** Bootstrap 5 + Jinja2 templates
- **Storage:** Cloudinary para imágenes
- **Cache:** Redis para sesiones y cache

### Search API
- **Framework:** FastAPI con async/await
- **IA:** CLIP (ViT-B/16) optimizado para CPU
- **Base de Datos:** PostgreSQL (acceso readonly)
- **Autenticación:** API Keys con rate limiting
- **Cache:** Redis para resultados y embeddings
- **Vectores:** pgvector para búsqueda eficiente

## 📦 Instalación y Configuración

### Prerrequisitos
- Python 3.11+
- PostgreSQL 15+ con extensión pgvector
- Redis 7+
- Cuenta Cloudinary (tier gratuito)

### Variables de Entorno
```bash
# Base de datos compartida
DATABASE_URL=postgresql://user:password@localhost/clip_comparador_v2
REDIS_URL=redis://localhost:6379

# Backend Admin
FLASK_SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_secret
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Search API
API_TITLE=CLIP Search API
API_VERSION=2.0.0
CORS_ORIGINS=*
MAX_UPLOAD_SIZE=10485760
ENABLE_REDIS_CACHE=true
```

### Instalación
```bash
# Clonar e instalar dependencias
pip install -r requirements.txt

# Inicializar base de datos
python shared/database/init_db.py

# Ejecutar Backend Admin
cd clip_admin_backend && python app.py

# Ejecutar Search API (en otra terminal)
cd clip_search_api && python main.py
```

## 🌐 Deployment en Railway

### Configuración Railway
- **Plan:** Hobby ($5/mes)
- **Base de datos:** PostgreSQL compartida
- **Redis:** Instancia compartida
- **Servicios:** 2 independientes

### URLs de Producción
- **Admin Panel:** https://admin.clip-comparador.railway.app
- **Search API:** https://api.clip-comparador.railway.app
- **API Docs:** https://api.clip-comparador.railway.app/docs

## 🔑 Características Principales

### Multi-tenancy
- Aislamiento completo por cliente
- API keys únicas por cliente
- Rate limiting personalizable
- Analytics individuales

### Optimización Railway
- Uso mínimo de memoria (512MB)
- CPU only (sin GPU)
- Cache inteligente
- Conexiones optimizadas

### Seguridad
- Autenticación JWT
- API keys con hash SHA-256
- Rate limiting global e individual
- Whitelist de IPs
- Validación de archivos

## 📊 Modelo de Negocio SaaS

### Planes
- **Starter:** 1000 búsquedas/mes - Gratis
- **Professional:** 10,000 búsquedas/mes - $29/mes
- **Enterprise:** Ilimitado - $99/mes

### Monetización
- API keys por suscripción
- Rate limiting automático
- Analytics detallados
- Soporte técnico

## 📈 Escalabilidad

### Horizontal
- Múltiples instancias de Search API
- Load balancer automático
- Cache distribuido

### Vertical
- Upgrade automático de Railway
- Optimización de embeddings
- Índices de base de datos

## 🔧 Desarrollo

### Testing
```bash
# Tests Backend Admin
cd clip_admin_backend && python -m pytest

# Tests Search API
cd clip_search_api && python -m pytest
```

### Linting
```bash
# Formatear código
black .
isort .
flake8 .
```

## 📚 Documentación Técnica

- [Especificación Completa](./CLIP_COMPARADOR_V2_SPECIFICATION.md)
- [API Reference](./docs/api/)
- [Deployment Guide](./docs/deployment/)

---

## 🆚 Comparación V1 vs V2

| Característica | V1 | V2 |
|---------------|----|----|
| Arquitectura | Monolítica | Dual (Admin + API) |
| Tenancy | Single | Multi-tenant |
| Autenticación | Básica | JWT + API Keys |
| Escalabilidad | Limitada | Horizontal |
| Deployment | Manual | Railway automático |
| Costo | Variable | $5/mes fijo |
| Performance | Básica | Optimizada + Cache |

---

> 💡 **Nota:** Este es el sistema V2 completamente nuevo. La V1 está disponible en el workspace original para referencia.
