# CLIP Comparador V2 - Sistema SaaS de Búsqueda Visual# CLIP Comparador V2 - Sistema SaaS de B├║squeda Visual



## 📋 Descripción## ­ƒÄ» Descripci├│n

Sistema SaaS moderno de búsqueda visual inteligente con arquitectura unificada Flask, optimizado para Railway Hobby Plan ($5/mes).Sistema SaaS moderno de b├║squeda visual inteligente con arquitectura dual optimizada para Railway Hobby Plan ($5/mes).



## 🏗️ Arquitectura Unificada## ­ƒÅù´©Å Arquitectura Dual



### Backend Flask Completo### M├│dulo 1: Backend Admin (Flask)

- **Puerto:** 5000- **Puerto:** 5000

- **Funciones:**- **Funci├│n:** Gesti├│n de clientes, productos, categor├¡as e im├ígenes

  - Panel de administración (clientes, productos, categorías, imágenes)- **Stack:** Flask 3.x + PostgreSQL + Redis + Bootstrap 5 + Cloudinary

  - API de búsqueda visual con CLIP (`/api/search`)- **URL:** admin.clip-comparador.railway.app

  - API externa de inventario (`/api/external/inventory`)

  - Gestión de stock y productos### M├│dulo 2: Search API (FastAPI)

- **Stack:** Flask 3.x + PostgreSQL + Redis + Bootstrap 5 + Cloudinary + CLIP (ViT-B/16)- **Puerto:** 8000

- **URL Producción:** https://clip-comparador-v2.railway.app- **Funci├│n:** API de b├║squeda visual con CLIP

- **Stack:** FastAPI + CLIP (ViT-B/16) + PostgreSQL (readonly) + Redis

## 📁 Estructura del Proyecto- **URL:** api.clip-comparador.railway.app



```## ­ƒôü Estructura del Proyecto

clip_admin_backend/           # Aplicación Flask Unificada

├── app/```

│   ├── models/              # Modelos SQLAlchemy (Client, Product, Category, Image)clip_admin_backend/           # M├│dulo Backend Admin

│   ├── blueprints/          # Rutas organizadas por funcionalidadÔö£ÔöÇÔöÇ app/

│   │   ├── api.py           # API de búsqueda visual (/api/search)Ôöé   Ôö£ÔöÇÔöÇ models/              # Modelos SQLAlchemy

│   │   ├── products.py      # CRUD de productos con atributos dinámicosÔöé   Ôö£ÔöÇÔöÇ blueprints/          # Rutas organizadas por funcionalidad

│   │   ├── inventory.py     # Panel admin de stock (nuevo oct 2025)Ôöé   Ôö£ÔöÇÔöÇ static/              # CSS, JS, im├ígenes

│   │   ├── external_inventory.py  # API externa inventario (nuevo oct 2025)Ôöé   Ôö£ÔöÇÔöÇ templates/           # Templates Jinja2

│   │   ├── images.py        # Gestión de imágenesÔöé   ÔööÔöÇÔöÇ utils/               # Utilidades

│   │   ├── categories.py    # Gestión de categoríasÔö£ÔöÇÔöÇ migrations/              # Migraciones de base de datos

│   │   └── ...              # Otros módulosÔö£ÔöÇÔöÇ requirements.txt         # Dependencias espec├¡ficas

│   ├── utils/               ÔööÔöÇÔöÇ app.py                   # Aplicaci├│n principal Flask

│   │   ├── api_auth.py      # Decorador @require_api_key (nuevo oct 2025)

│   │   └── ...              # Utilidadesclip_search_api/             # M├│dulo Search API

│   ├── templates/           # Templates Jinja2 + Bootstrap 5Ôö£ÔöÇÔöÇ app/

│   ├── static/              # CSS, JS, imágenes, widgetÔöé   Ôö£ÔöÇÔöÇ core/               # CLIP Engine + Search Engine

│   └── services/            # Cloudinary, Image ManagerÔöé   Ôö£ÔöÇÔöÇ middleware/         # Autenticaci├│n + Rate Limiting

├── migrations/              # Alembic migrationsÔöé   Ôö£ÔöÇÔöÇ models/             # Modelos Pydantic

├── requirements.txt         # Dependencias PythonÔöé   ÔööÔöÇÔöÇ utils/              # Database + Utilidades

└── app.py                   # Aplicación principal FlaskÔö£ÔöÇÔöÇ requirements.txt        # Dependencias espec├¡ficas

ÔööÔöÇÔöÇ main.py                 # Aplicaci├│n principal FastAPI

shared/                      # Recursos compartidos

├── database/                # Scripts de inicializaciónshared/                      # Recursos compartidos

└── docker/                  # DockerfilesÔö£ÔöÇÔöÇ database/               # Scripts de inicializaci├│n

Ôö£ÔöÇÔöÇ docker/                 # Dockerfiles

docs/                        # DocumentaciónÔööÔöÇÔöÇ config/                 # Configuraciones comunes

├── API_INVENTARIO_EXTERNA.md  # API de stock (nuevo oct 2025)

├── TOOLS_REFERENCE.md       # Referencia de herramientasdocs/                       # Documentaci├│n

├── SETUP_POSTGRES_LOCAL.md  # Setup PostgreSQL localÔö£ÔöÇÔöÇ api/                    # Documentaci├│n de API

└── ...                      # Más documentaciónÔööÔöÇÔöÇ deployment/             # Gu├¡as de despliegue

```

tools/                       # Herramientas de mantenimiento

├── diagnostics/             # Scripts de diagnóstico## ­ƒÜÇ Tecnolog├¡as Principales

├── maintenance/             # Scripts de limpieza

├── migrations/              # Migraciones manuales### Backend Admin

└── sync/                    # Sincronización Railway ↔ Local- **Framework:** Flask 3.x con factory pattern

```- **Base de Datos:** PostgreSQL con SQLAlchemy ORM

- **Autenticaci├│n:** Flask-Login + JWT

## 🚀 Tecnologías Principales- **Frontend:** Bootstrap 5 + Jinja2 templates

- **Storage:** Cloudinary para im├ígenes

### Backend- **Cache:** Redis para sesiones y cache

- **Framework:** Flask 3.x con blueprint architecture

- **Base de Datos:** PostgreSQL 15+ con SQLAlchemy ORM### Search API

- **Extensiones DB:** pgvector (búsqueda vectorial), uuid-ossp- **Framework:** FastAPI con async/await

- **Autenticación:** Flask-Login (admin) + API Keys (externa)- **IA:** CLIP (ViT-B/16) optimizado para CPU

- **Frontend:** Bootstrap 5 + Jinja2 templates- **Base de Datos:** PostgreSQL (acceso readonly)

- **Storage:** Cloudinary para imágenes- **Autenticaci├│n:** API Keys con rate limiting

- **Cache:** Redis para sesiones y embeddings- **Cache:** Redis para resultados y embeddings

- **Vectores:** pgvector para b├║squeda eficiente

### IA/ML

- **Modelo:** CLIP (ViT-B/16) optimizado para CPU## ­ƒôª Instalaci├│n y Configuraci├│n

- **Función:** Embeddings visuales para búsqueda por similitud

- **Vectores:** pgvector para búsqueda eficiente de similitud coseno### Prerrequisitos

- **Centroides:** Detección automática de categoría por centroide- Python 3.11+

- PostgreSQL 15+ con extensi├│n pgvector

### Atributos Dinámicos- Redis 7+

- **Sistema JSONB:** Metadata flexible de productos sin schema fijo- Cuenta Cloudinary (tier gratuito)

- **Tipos soportados:** text, number, list (multi-select), date, boolean

- **Configuración:** Por cliente, con validación y ordenamiento### Variables de Entorno

```bash

## 🔧 Instalación y Configuración# Base de datos compartida

DATABASE_URL=postgresql://user:password@localhost/clip_comparador_v2

### PrerrequisitosREDIS_URL=redis://localhost:6379

- Python 3.10+

- PostgreSQL 15+ con extensión pgvector (REQUERIDO - no usar SQLite)# Backend Admin

- Redis 7+FLASK_SECRET_KEY=your_secret_key

- Cuenta Cloudinary (tier gratuito suficiente)JWT_SECRET_KEY=your_jwt_secret

CLOUDINARY_CLOUD_NAME=your_cloud_name

### Setup LocalCLOUDINARY_API_KEY=your_api_key

CLOUDINARY_API_SECRET=your_api_secret

#### 1. Instalar PostgreSQL

```bash# Search API

# Windows: Descargar de https://www.postgresql.org/download/API_TITLE=CLIP Search API

# Verificar instalación:API_VERSION=2.0.0

psql --versionCORS_ORIGINS=*

MAX_UPLOAD_SIZE=10485760

# Ejecutar script de setupENABLE_REDIS_CACHE=true

.\setup_postgres.ps1```

```

### Instalaci├│n

#### 2. Configurar Entorno```bash

```bash# Clonar e instalar dependencias

# Copiar template de configuraciónpip install -r requirements.txt

cp .env.local.example .env.local

# Inicializar base de datos

# Editar .env.local con tus credenciales:python shared/database/init_db.py

# - DATABASE_URL (PostgreSQL local)

# - CLOUDINARY_* (credenciales de Cloudinary)# Ejecutar Backend Admin

# - FLASK_SECRET_KEYcd clip_admin_backend && python app.py

```

# Ejecutar Search API (en otra terminal)

#### 3. Instalar Dependenciascd clip_search_api && python main.py

```bash```

pip install -r requirements.txt

```## ­ƒîÉ Deployment en Railway



#### 4. Inicializar Base de Datos### Configuraci├│n Railway

```bash- **Plan:** Hobby ($5/mes)

python setup_local_postgres.py- **Base de datos:** PostgreSQL compartida

```- **Redis:** Instancia compartida

- **Servicios:** 2 independientes

#### 5. Ejecutar Aplicación

```bash### URLs de Producci├│n

# Opción 1: Script rápido- **Admin Panel:** https://admin.clip-comparador.railway.app

.\start.ps1- **Search API:** https://api.clip-comparador.railway.app

- **API Docs:** https://api.clip-comparador.railway.app/docs

# Opción 2: Con validaciones

.\start_local.ps1## ­ƒöæ Caracter├¡sticas Principales



# Opción 3: Manual### Multi-tenancy

cd clip_admin_backend- Aislamiento completo por cliente

python app.py- API keys ├║nicas por cliente

```- Rate limiting personalizable

- Analytics individuales

Acceso: http://localhost:5000

### Optimizaci├│n Railway

### Variables de Entorno- Uso m├¡nimo de memoria (512MB)

- CPU only (sin GPU)

```bash- Cache inteligente

# Base de datos (REQUERIDO)- Conexiones optimizadas

DATABASE_URL=postgresql://postgres:password@localhost:5432/clip_comparador_v2

### Seguridad

# Redis (REQUERIDO)- Autenticaci├│n JWT

REDIS_URL=redis://localhost:6379- API keys con hash SHA-256

- Rate limiting global e individual

# Flask (REQUERIDO)- Whitelist de IPs

FLASK_SECRET_KEY=tu_clave_secreta_muy_larga_y_segura- Validaci├│n de archivos

JWT_SECRET_KEY=otra_clave_secreta_para_jwt

## ­ƒôè Modelo de Negocio SaaS

# Cloudinary (REQUERIDO para imágenes)

CLOUDINARY_CLOUD_NAME=tu_cloud_name### Planes

CLOUDINARY_API_KEY=tu_api_key- **Starter:** 1000 b├║squedas/mes - Gratis

CLOUDINARY_API_SECRET=tu_api_secret- **Professional:** 10,000 b├║squedas/mes - $29/mes

- **Enterprise:** Ilimitado - $99/mes

# Opcional

FLASK_ENV=development### Monetizaci├│n

FLASK_DEBUG=1- API keys por suscripci├│n

```- Rate limiting autom├ítico

- Analytics detallados

## 🎯 Características Principales- Soporte t├®cnico



### ✅ Multi-tenancy SaaS## ­ƒôê Escalabilidad

- Aislamiento completo por cliente con UUID

- API keys únicas por cliente (`clip_xxxx...`)### Horizontal

- Rate limiting personalizable- M├║ltiples instancias de Search API

- Analytics individuales por cliente- Load balancer autom├ítico

- Cache distribuido

### ✅ Búsqueda Visual con CLIP

- Embeddings de 512 dimensiones (ViT-B/16)### Vertical

- Búsqueda por similitud coseno con pgvector- Upgrade autom├ítico de Railway

- Detección automática de categoría por centroide- Optimizaci├│n de embeddings

- Optimización configurable (sensitivity sliders)- ├ìndices de base de datos

- Cache de embeddings en Redis

## ­ƒöº Desarrollo

### ✅ Atributos Dinámicos de Productos

- Sistema JSONB flexible sin schema fijo### Testing

- Configuración por cliente```bash

- Tipos: text, number, list, date, boolean# Tests Backend Admin

- Multi-select para atributos tipo listacd clip_admin_backend && python -m pytest

- Validación y ordenamiento

# Tests Search API

### ✅ Gestión de Inventario (Nuevo - Octubre 2025)cd clip_search_api && python -m pytest

```

#### Panel de Administración de Stock

- **Ruta:** `/inventory/`### Linting

- **Características:**```bash

  - Dashboard con estadísticas (total, sin stock, bajo stock, disponible)# Formatear c├│digo

  - Filtros por categoría, búsqueda, nivel de stockblack .

  - Ajuste inline con botones +/-isort .

  - Establecer stock absolutoflake8 .

  - Indicadores visuales (🔴 sin stock, 🟡 ≤10, 🟢 >10)```

  - Updates en tiempo real con AJAX

## ­ƒôÜ Documentaci├│n T├®cnica

#### API Externa de Inventario

- **Autenticación:** API Key vía header `X-API-Key`- [Especificaci├│n Completa](./CLIP_COMPARADOR_V2_SPECIFICATION.md)

- **Endpoints:**- [API Reference](./docs/api/)

  - `POST /api/external/inventory/reduce-stock` - Reducir stock (post-venta)- [Deployment Guide](./docs/deployment/)

  - `GET /api/external/inventory/check-stock` - Consultar disponibilidad

  - `POST /api/external/inventory/bulk-check-stock` - Consultas masivas---



**Documentación completa:** [docs/API_INVENTARIO_EXTERNA.md](docs/API_INVENTARIO_EXTERNA.md)## ­ƒåÜ Comparaci├│n V1 vs V2



**Ejemplo de uso:**| Caracter├¡stica | V1 | V2 |

```python|---------------|----|----|

import requests| Arquitectura | Monol├¡tica | Dual (Admin + API) |

| Tenancy | Single | Multi-tenant |

headers = {| Autenticaci├│n | B├ísica | JWT + API Keys |

    "X-API-Key": "clip_tu_api_key_aqui",| Escalabilidad | Limitada | Horizontal |

    "Content-Type": "application/json"| Deployment | Manual | Railway autom├ítico |

}| Costo | Variable | $5/mes fijo |

| Performance | B├ísica | Optimizada + Cache |

# Reducir stock después de una venta

response = requests.post(---

    "https://tu-dominio.railway.app/api/external/inventory/reduce-stock",

    headers=headers,> ­ƒÆí **Nota:** Este es el sistema V2 completamente nuevo. La V1 est├í disponible en el workspace original para referencia.

    json={"sku": "PROD-001", "quantity": 1, "reason": "Venta POS"}
)
```

### ✅ Optimización Railway Hobby Plan
- Uso mínimo de memoria (<512MB)
- CPU only (sin GPU necesaria)
- Cache inteligente en Redis
- Conexiones optimizadas a PostgreSQL
- Auto-deploy desde GitHub

### ✅ Seguridad
- Flask-Login para panel admin
- API Keys con decorador `@require_api_key`
- Rate limiting por cliente
- Validación de archivos (tipo, tamaño)
- Transacciones atómicas (stock no puede ser negativo)

## 🛠️ Herramientas de Desarrollo

### Scripts Principales (Raíz)
- `railway_db_tool.py` - Gestión completa de BD Railway
- `backup_local_db.py` - Backup de BD local
- `restore_from_railway.ps1` - Restaurar desde Railway
- `setup_local_postgres.py` - Setup inicial BD local
- `check_embeddings.py` - Verificar embeddings locales
- `check_prod_embeddings.py` - Verificar embeddings en Railway

**Ver referencia completa:** [docs/TOOLS_REFERENCE.md](docs/TOOLS_REFERENCE.md)

### Testing
```bash
# Ejecutar tests locales
cd clip_admin_backend
python -m pytest

# Verificar errores
python -m flake8 app/
```

## 🚢 Deployment en Railway

### Configuración
- **Plan:** Hobby ($5/mes)
- **Servicios:** 1 Flask app + PostgreSQL + Redis
- **Deployment:** Auto desde push a GitHub main
- **URL:** https://clip-comparador-v2.railway.app

### Variables en Railway
Configurar en Railway Dashboard:
- `DATABASE_URL` (auto-generada por PostgreSQL plugin)
- `REDIS_URL` (auto-generada por Redis plugin)
- `FLASK_SECRET_KEY`
- `CLOUDINARY_*` (3 variables)

### Comandos Railway CLI
```bash
# Deploy manual
railway up

# Ver logs
railway logs

# Conectar a BD
railway connect postgresql
```

## 📊 Roadmap

### ✅ Completado (Octubre 2025)
- [x] Arquitectura unificada Flask
- [x] Multi-tenant SaaS
- [x] CLIP visual search con centroides
- [x] Atributos dinámicos JSONB
- [x] Sistema de inventario dual (admin panel + API externa)
- [x] Auto-recálculo de centroides en CRUD
- [x] Deployment Railway con auto-deploy

### 🔜 Próximos Pasos
- [ ] Detección multi-producto con CLIP (zero-shot multi-categoría)
- [ ] Historial de cambios de stock (audit log)
- [ ] Notificaciones de stock crítico
- [ ] Analytics avanzados por cliente
- [ ] Exportación de catálogos

## 📚 Documentación Adicional

- [API de Inventario Externa](./docs/API_INVENTARIO_EXTERNA.md)
- [Referencia de Herramientas](./docs/TOOLS_REFERENCE.md)
- [Setup PostgreSQL Local](./docs/SETUP_POSTGRES_LOCAL.md)
- [Guía de Manejo de Imágenes](./docs/IMAGE_HANDLING_GUIDE.md)
- [Backlog de Mejoras](./BACKLOG_MEJORAS.md)

## 🆚 Comparación V1 vs V2

| Característica | V1 | V2 |
|---------------|----|----|
| Arquitectura | FastAPI + Flask separados | Flask unificado |
| Tenancy | Single | Multi-tenant |
| Autenticación | Básica | Flask-Login + API Keys |
| Inventario | ❌ No | ✅ Panel + API externa |
| Atributos | Fijos | Dinámicos JSONB |
| Deployment | Manual | Railway auto-deploy |
| Costo | Variable | $5/mes fijo |
| Centroides | Manual | Auto-recálculo |
| Performance | Básica | Cache Redis + optimizaciones |

---

## 📞 Soporte

Para dudas o problemas:
1. Ver [docs/TOOLS_REFERENCE.md](docs/TOOLS_REFERENCE.md) primero
2. Revisar [BACKLOG_MEJORAS.md](BACKLOG_MEJORAS.md)
3. Consultar documentación en `docs/`

---

> 💡 **Nota:** Este es el sistema V2 completamente refactorizado. La V1 está disponible en el workspace original para referencia.

**Fecha última actualización:** 24 de Octubre, 2025
