# CLIP Comparador V2 - Sistema SaaS de Búsqueda Visual

> **ACTUALIZACIÓN NOVIEMBRE 2025**: Migrado a **BLIP-2** para búsqueda visual multimodal unificada

## 📋 Descripción

Sistema SaaS moderno de búsqueda visual inteligente con arquitectura unificada Flask + **BLIP-2**, optimizado para Railway Pro Plan ($20/mes).

## 🚀 Nueva Arquitectura BLIP-2

### ¿Qué cambió?

**ANTES (hasta Oct 2025):**
- CLIP ViT-B/16 para embeddings (512D)
- MiniLM-L12 para normalización de queries
- 2 modelos separados (~1.2 GB RAM)

**AHORA (Nov 2025):**
- **BLIP-2 OPT-2.7B** para TODO (embeddings + NLU)
- 1 modelo unificado (~7 GB RAM)
- Mejor comprensión multimodal
- Embeddings 256D (más eficientes)

### Ventajas de BLIP-2

✅ **Sistema Unificado**: 1 modelo vs 2 modelos
✅ **Mejor NLU**: Comprende contexto visual + texto simultáneamente
✅ **Embeddings Superiores**: ViT-L/14 (mejor que ViT-B/16)
✅ **Preparado para Futuro**: Soporta generación, VQA, captioning
✅ **Mismo Costo**: $20/mes en Railway Pro (dentro del crédito incluido)

## 🏗️ Arquitectura

### Backend Flask Unificado

- **Puerto:** 5000
- **Funciones:**
  - Panel de administración (clientes, productos, categorías)
  - API de búsqueda visual con BLIP-2 (`/api/search`)
  - API externa de inventario (`/api/external/inventory`)
  - Gestión de stock y productos
- **Stack:** Flask 3.x + PostgreSQL + Redis + Bootstrap 5 + Cloudinary + **BLIP-2**
- **URL Producción:** https://clip-comparador-v2.railway.app

## 📁 Estructura del Proyecto

```
clip_admin_backend/           # Aplicación Flask Unificada
├── app/
│   ├── models/              # Modelos SQLAlchemy (Client, Product, Category, Image)
│   ├── blueprints/          # Rutas organizadas por funcionalidad
│   │   ├── api.py           # API de búsqueda visual con BLIP-2
│   │   ├── products.py      # CRUD de productos con atributos dinámicos
│   │   ├── inventory.py     # Panel admin de stock
│   │   └── ...              # Otros módulos
│   ├── utils/
│   │   ├── blip2_embeddings.py  # Sistema BLIP-2 unificado (NUEVO)
│   │   ├── api_auth.py      # Decorador @require_api_key
│   │   └── ...              # Utilidades
│   ├── templates/           # Templates Jinja2 + Bootstrap 5
│   ├── static/              # CSS, JS, imágenes, widget
│   └── services/            # Cloudinary, Image Manager
├── migrations/              # Alembic migrations
├── requirements.txt         # Dependencias Python
└── app.py                   # Aplicación principal Flask

shared/                      # Recursos compartidos
├── database/                # Scripts de inicialización
└── docker/                  # Dockerfiles

docs/                        # Documentación
├── BLIP2_MIGRATION_PLAN.md  # Plan de migración a BLIP-2 (NUEVO)
├── API_INVENTARIO_EXTERNA.md
├── TOOLS_REFERENCE.md
└── ...
```

## 🔧 Setup Local

### 1. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 2. PostgreSQL Local (REQUERIDO)

```powershell
# Instalar PostgreSQL: https://www.postgresql.org/download/
.\setup_postgres.ps1
```

### 3. Configurar Entorno

```bash
cp .env.local.example .env.local
# Editar .env.local con credenciales
```

### 4. Inicializar Base de Datos

```bash
python setup_local_postgres.py
```

### 5. Ejecutar Aplicación

```bash
cd clip_admin_backend && python app.py
```

Acceso: http://localhost:5000

## 🔄 Migración a BLIP-2

Si tienes un sistema existente con embeddings CLIP, ejecuta:

### 1. Re-embedding Masivo

```bash
# Backup automático + re-embedding con BLIP-2
python reembed_with_blip2.py

# Solo un cliente
python reembed_with_blip2.py --client-id <CLIENT_ID>

# Dry run (sin guardar)
python reembed_with_blip2.py --dry-run
```

### 2. Recalcular Centroides

```bash
# Recalcular centroides con embeddings BLIP-2
python recalculate_blip2_centroids.py --force
```

### 3. Re-calibrar Thresholds

```bash
# Ejecutar calibración para cada cliente
# (desde panel admin: /calibration)
```

## 🎯 Características Principales

### 🔍 Búsqueda Visual Multimodal (BLIP-2)

- **Upload de imagen**: Usuario sube foto → BLIP-2 encuentra productos similares
- **Búsqueda por texto**: "camisa azul marino" → BLIP-2 entiende y busca
- **Fusión híbrida**: Combina similaridad visual + atributos dinámicos

### 📦 Sistema de Stock (Oct 2025)

- **Panel Admin**: Gestión visual de inventario
- **API Externa**: Integración con ecommerce/POS
  - `POST /api/external/inventory/reduce-stock` - Reducir stock
  - `POST /api/external/inventory/check-stock` - Verificar disponibilidad
  - `POST /api/external/inventory/bulk-check-stock` - Consulta masiva

### 🎨 Atributos Dinámicos por Producto

- **JSONB**: Atributos flexibles sin migraciones
- **Multi-select**: Soporta valores múltiples (ej: colores disponibles)
- **Validación**: Tipos personalizados por cliente

### 🏷️ Multi-tenant SaaS

- **Aislamiento completo**: Cada cliente con su catálogo
- **API Keys individuales**: Rate limiting independiente
- **Analytics**: Tracking por cliente

## 🧪 Testing

```bash
# Tests unitarios
pytest

# Test búsqueda BLIP-2
python test_blip2_search.py

# Test multi-categoría
python test_multi_category.py
```

## 🚀 Deploy en Railway Pro

### Configuración

1. **Upgrade a Pro**: $20/mes
2. **Variables de entorno**:
```env
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SECRET_KEY=...
BLIP2_MODEL=Salesforce/blip2-itm-vit-g
BLIP2_DEVICE=cpu
BLIP2_USE_FP16=true
```

3. **Recursos**:
- RAM: 32 GB disponibles (BLIP-2 usa ~7 GB)
- vCPU: 32 vCPU disponibles
- Storage: 100 GB

### Deploy

```bash
# Railway CLI
railway up

# O push a GitHub (auto-deploy)
git push origin main
```

## 📊 Recursos Railway Pro

### Uso Estimado (100 consultas/día)

| Recurso | Uso | Costo/mes |
|---------|-----|-----------|
| RAM Base | 7 GB × 24h × 30d | $1.16 |
| vCPU | 1.67h × 4 vCPU | $0.02 |
| PostgreSQL | 10 GB | $2.50 |
| **TOTAL** | - | **$3.68** |

**Costo Real**: $20/mes (suscripción incluye $20 de crédito → cubre todo el uso)

## 🛠️ Herramientas Disponibles

Ver [TOOLS_REFERENCE.md](docs/TOOLS_REFERENCE.md) para lista completa:

- `railway_db_tool.py` - Gestión de BD Railway
- `backup_local_db.py` - Backups locales
- `reembed_with_blip2.py` - Re-embedding masivo
- `recalculate_blip2_centroids.py` - Recalcular centroides
- `check_embeddings.py` - Validar embeddings
- `test_*.py` - Scripts de testing

## 📚 Documentación Adicional

- [BLIP2_MIGRATION_PLAN.md](docs/BLIP2_MIGRATION_PLAN.md) - Plan de migración completo
- [API_INVENTARIO_EXTERNA.md](docs/API_INVENTARIO_EXTERNA.md) - API de stock
- [SETUP_POSTGRES_LOCAL.md](docs/SETUP_POSTGRES_LOCAL.md) - Setup PostgreSQL
- [IMAGE_HANDLING_GUIDE.md](docs/IMAGE_HANDLING_GUIDE.md) - Gestión de imágenes
- [TOOLS_REFERENCE.md](docs/TOOLS_REFERENCE.md) - Herramientas disponibles

## 🤝 Contribuir

1. Fork del repositorio
2. Crear branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push al branch (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📝 Changelog

### v2.1.0 (Noviembre 2025) - BLIP-2 Migration

- ✅ Migración completa a BLIP-2 OPT-2.7B
- ✅ Sistema unificado (embeddings + NLU)
- ✅ Embeddings 256D (más eficientes)
- ✅ Scripts de re-embedding y recalibración
- ✅ Railway Pro optimization
- ✅ Documentación actualizada

### v2.0.0 (Octubre 2025)

- ✅ Sistema de inventario externo
- ✅ Panel admin de stock
- ✅ Multi-select para atributos
- ✅ Familias exclusivas configurables
- ✅ Mejoras en detección de categorías

## 📄 Licencia

Propietario - Todos los derechos reservados

## 👤 Autor

**CLIP Comparador V2 Team**

---

**Nota**: Este sistema requiere PostgreSQL (no soporta SQLite). Ver [SETUP_POSTGRES_LOCAL.md](docs/SETUP_POSTGRES_LOCAL.md) para instrucciones de instalación.
