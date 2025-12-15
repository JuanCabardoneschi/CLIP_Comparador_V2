# CLIP Comparador V2 - Sistema SaaS de Búsqueda Visual

## 📋 Descripción

Sistema SaaS moderno de búsqueda visual inteligente con arquitectura unificada Flask, optimizado para Railway Hobby Plan ($5/mes).

## 🏗️ Arquitectura Unificada

### Backend Flask Completo

- **Puerto:** 5000
- **Funciones:**
  - Panel de administración (clientes, productos, categorías, imágenes)
  - API de búsqueda visual con CLIP (`/api/search`)
  - API externa de inventario (`/api/external/inventory`)
  - Gestión de stock y productos
- **Stack:** Flask 3.x + PostgreSQL + Bootstrap 5 + Cloudinary + CLIP (ViT-B/16)
- **URL Producción:** https://clip-comparador-v2.railway.app

## 📁 Estructura del Proyecto

```
clip_admin_backend/           # Aplicación Flask Unificada
├── app/
│   ├── models/              # Modelos SQLAlchemy
│   ├── blueprints/          # Rutas organizadas por funcionalidad
│   │   ├── api.py           # API de búsqueda visual
│   │   ├── products.py      # CRUD de productos
│   │   ├── inventory.py     # Panel admin de stock
│   │   ├── external_inventory.py  # API externa inventario
│   │   ├── images.py        # Gestión de imágenes
│   │   ├── categories.py    # Gestión de categorías
│   │   └── ...              # Otros módulos
│   ├── utils/               # Utilidades
│   ├── templates/           # Templates Jinja2
│   ├── static/              # CSS, JS, imágenes, widget
│   └── services/            # Cloudinary, Image Manager
├── requirements.txt         # Dependencias Python
└── app.py                   # Aplicación principal Flask

shared/                      # Recursos compartidos
├── database/                # Scripts de inicialización
└── docker/                  # Dockerfiles

docs/                        # Documentación
├── API_INVENTARIO_EXTERNA.md
├── TOOLS_REFERENCE.md
├── SETUP_POSTGRES_LOCAL.md
└── ...                      # Más documentación

tools/                       # Herramientas de mantenimiento
├── diagnostics/             # Scripts de diagnóstico
├── maintenance/             # Scripts de limpieza
├── migrations/              # Migraciones manuales
└── sync/                    # Sincronización Railway ↔ Local
```

## 🚀 Tecnologías Principales

### Backend Admin

- **Framework:** Flask 3.x con blueprint architecture
- **Base de Datos:** PostgreSQL 15+ con SQLAlchemy ORM
- **Extensiones DB:** pgvector (búsqueda vectorial), uuid-ossp
- **Autenticación:** Flask-Login (admin) + API Keys (externa)
- **Frontend:** Bootstrap 5 + Jinja2 templates
- **Storage:** Cloudinary para imágenes
- **Cache:** Cache en memoria con TTL (no requiere Redis)

### IA/ML

- **Modelo:** CLIP (ViT-B/16) optimizado para CPU
- **Función:** Embeddings visuales para búsqueda por similitud
- **Vectores:** pgvector para búsqueda eficiente de similitud coseno
- **Centroides:** Detección automática de categoría por centroide

### Atributos Dinámicos

- **Sistema JSONB:** Metadata flexible de productos sin schema fijo
- **Tipos soportados:** text, number, list (multi-select), date, boolean
- **Configuración:** Por cliente, con validación y ordenamiento

## 🔧 Instalación y Configuración

### Prerrequisitos

- Python 3.10+
- PostgreSQL 15+ con extensión pgvector (REQUERIDO - no usar SQLite)
- Cuenta Cloudinary (tier gratuito suficiente)

### Setup Local

#### 1. Instalar PostgreSQL

```bash
# Windows: Descargar de https://www.postgresql.org/download/
# Verificar instalación:
psql --version

# Ejecutar script de setup:
.\setup_postgres.ps1
```

#### 2. Configurar Entorno

```bash
# Copiar template de configuración
cp .env.local.example .env.local

# Editar .env.local con tus credenciales:
# - DATABASE_URL (PostgreSQL local)
# - CLOUDINARY_* (credenciales de Cloudinary)
# - FLASK_SECRET_KEY
```

#### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

#### 4. Inicializar Base de Datos

```bash
python setup_local_postgres.py
```

#### 5. Ejecutar Aplicación

```bash
# Opción 1: Script rápido
.\start.ps1

# Opción 2: Manual
cd clip_admin_backend
python app.py
```

Acceso: http://localhost:5000

### Variables de Entorno

```bash
# Base de datos (REQUERIDO)
DATABASE_URL=postgresql://postgres:password@localhost:5432/clip_comparador_v2

# Flask (REQUERIDO)
FLASK_SECRET_KEY=tu_clave_secreta_muy_larga_y_segura
JWT_SECRET_KEY=otra_clave_secreta_para_jwt

# Cloudinary (REQUERIDO para imágenes)
CLOUDINARY_CLOUD_NAME=tu_cloud_name
CLOUDINARY_API_KEY=tu_api_key
CLOUDINARY_API_SECRET=tu_api_secret

# Opcional
FLASK_ENV=development
FLASK_DEBUG=1
```

## 🎯 Características Principales

### ✅ Multi-tenancy SaaS

- Aislamiento completo por cliente con UUID
- API keys únicas por cliente (`clip_xxxx...`)
- Rate limiting personalizable
- Analytics individuales por cliente

### ✅ Búsqueda Visual con CLIP

- Embeddings de 512 dimensiones (ViT-B/16)
- Búsqueda por similitud coseno con pgvector
- Detección automática de categoría por centroide
- Optimización configurable

### ✅ Atributos Dinámicos de Productos

- Sistema JSONB flexible sin schema fijo
- Configuración por cliente
- Tipos: text, number, list, date, boolean
- Multi-select para atributos tipo lista
- Validación y ordenamiento

### ✅ Gestión de Inventario (Nuevo - Octubre 2025)

#### Panel de Administración de Stock

- **Ruta:** `/inventory/`
- **Características:**
  - Dashboard con estadísticas (total, sin stock, bajo stock, disponible)
  - Filtros por categoría, búsqueda, nivel de stock
  - Ajuste inline con botones +/-
  - Establecer stock absoluto
  - Indicadores visuales (🔴 sin stock, 🟡 ≤10, 🟢 >10)
  - Updates en tiempo real con AJAX

#### API Externa de Inventario

- **Autenticación:** API Key vía header `X-API-Key`
- **Endpoints:**
  - `POST /api/external/inventory/reduce-stock` - Reducir stock (post-venta)
  - `GET /api/external/inventory/check-stock` - Consultar disponibilidad
  - `POST /api/external/inventory/bulk-check-stock` - Consultas masivas

**Documentación completa:** [docs/API_INVENTARIO_EXTERNA.md](docs/API_INVENTARIO_EXTERNA.md)

**Ejemplo de uso:**

```python
import requests

headers = {
    "X-API-Key": "clip_tu_api_key_aqui",
    "Content-Type": "application/json"
}

# Reducir stock después de una venta
response = requests.post(
    "https://tu-dominio.railway.app/api/external/inventory/reduce-stock",
    headers=headers,
    json={"sku": "PROD-001", "quantity": 1, "reason": "Venta POS"}
)
```

### ✅ Optimización Railway Hobby Plan

- Uso mínimo de memoria (<512MB)
- CPU only (sin GPU necesaria)
- Cache inteligente en memoria
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
- **Servicios:** 1 Flask app + PostgreSQL
- **Deployment:** Auto desde push a GitHub main
- **URL:** https://clip-comparador-v2.railway.app

### Variables en Railway

Configurar en Railway Dashboard:
- `DATABASE_URL` (auto-generada por PostgreSQL plugin)
- `FLASK_SECRET_KEY`
- `CLOUDINARY_*` (3 variables)

### Scripts de Deploy Disponibles

#### Deploy Interactivo (Recomendado)

```powershell
.\deploy_to_railway.ps1
```

**Características:**
- Guía paso a paso con validaciones
- Selector de tipo de commit (feat/fix/refactor/etc.)
- Verificación de tests locales
- Vista previa de cambios
- Confirmación antes de push
- Información post-deploy y rollback

#### Deploy Rápido

```powershell
# Con mensaje directo
.\quick_deploy.ps1 -Type "fix" -Message "corregir búsqueda de colores"

# Interactivo simple
.\quick_deploy.ps1
```

### Comandos Railway CLI

```bash
# Deploy manual (alternativa)
railway up

# Ver logs en tiempo real
railway logs

# Conectar a BD
railway connect postgresql
```

### Proceso de Deploy

1. **Local:** Hacer cambios y testear
2. **Deploy:** Ejecutar `.\deploy_to_railway.ps1`
3. **Railway:** Auto-build y deploy (2-5 min)
4. **Verificar:** Logs en Railway Dashboard
5. **Rollback:** Si hay problemas, revertir desde Dashboard

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

- [ ] Detección multi-producto con CLIP
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
| Performance | Básica | Cache inteligente + optimizaciones |

---

## 📞 Soporte

Para dudas o problemas:

1. Ver [docs/TOOLS_REFERENCE.md](docs/TOOLS_REFERENCE.md) primero
2. Revisar [BACKLOG_MEJORAS.md](BACKLOG_MEJORAS.md)
3. Consultar documentación en `docs/`

---

> 💡 **Nota:** Este es el sistema V2 completamente refactorizado. La V1 está disponible en el workspace original para referencia.

**Fecha última actualización:** 15 de Diciembre, 2025
