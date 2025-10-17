# Session Summary - CLIP Comparador V2

**Fecha**: 17 de Octubre, 2025
**Repositorio**: https://github.com/JuanCabardoneschi/CLIP_Comparador_V2

---

## 🎯 Estado Actual del Sistema

### ✅ Funcionalidades Implementadas y Funcionando

1. **Sistema de Sensibilidad Personalizada por Cliente**
   - Cada cliente puede tener sus propios umbrales de detección
   - Campos en BD: `category_confidence_threshold` y `product_similarity_threshold`
   - Valores por defecto: 70% categoría, 30% productos
   - UI con sliders en `/clients/<id>` para ajustar valores
   - Endpoint AJAX: `POST /clients/<id>/update-sensitivity`

2. **Detección Visual con CLIP**
   - Detección de categoría usando centroides de embeddings
   - Búsqueda de productos similares dentro de la categoría detectada
   - Filtrado de objetos no comerciales
   - Sistema funcionando correctamente en Railway

3. **Arquitectura**
  - **Backend Admin** (Flask): Servicio único que expone el endpoint `/api/search`
  - Base de datos PostgreSQL en Railway (prod) y local (dev)

---

## 🔑 Credenciales y URLs

### Railway Production
- **Admin URL**: https://clipcomparadorv2-production.up.railway.app
- **Database**: PostgreSQL en Railway (interno)
- **Redis**: Configurado en Railway

### Credenciales de Admin
- **Super Admin**:
  - Usuario: `admin`
  - Password: `admin123`

- **Cliente Demo**:
  - Usuario: `demo`
  - Password: `demo123`
  - Nombre: Demo Fashion Store
  - ID Cliente: `60231500-ca6f-4c46-a960-2e17298fcdb0`

### PostgreSQL Local (✅ CONFIGURADO Y FUNCIONANDO)
- **Usuario**: `postgres`
- **Password**: `Laurana@01`
- **Puerto**: 5432
- **Base de Datos**: `clip_comparador_v2`
- **Estado**: ✅ Instalado, configurado y datos migrados desde Railway
- **Path**: `C:\Program Files\PostgreSQL\18\bin\` (agregado al PATH)
- **Datos**: 1 cliente, 2 usuarios, 12 categorías, 51 productos, 58 imágenes

---

## 📁 Estructura del Proyecto

```
CLIP_Comparador_V2/
├── clip_admin_backend/          # Flask Admin (Puerto 5000)
│   ├── app/
│   │   ├── blueprints/
│   │   │   ├── api.py          # API de búsqueda visual (CRÍTICO)
│   │   │   ├── clients.py      # Gestión de clientes
│   │   │   └── ...
│   │   ├── models/
│   │   │   ├── client.py       # Modelo Client con sensibilidad
│   │   │   └── user.py
│   │   ├── templates/
│   │   │   └── clients/
│   │   │       └── view.html   # UI con sliders de sensibilidad
│   │   └── config.py           # Configuración de entorno
│   └── app.py                  # Punto de entrada Flask
├── (eliminado) clip_search_api/ # FastAPI (no usado; eliminado)
├── docs/
│   ├── SETUP_POSTGRES_LOCAL.md # Guía de instalación PostgreSQL
│   └── SESSION_SUMMARY.md      # Este archivo
├── setup_local_postgres.py     # Script de inicialización BD local
├── setup_postgres.ps1          # Helper PowerShell
├── .env.local.example          # Template para desarrollo local
└── requirements.txt
```

---

## 🔧 Configuración de Entorno

### Variables de Entorno Críticas

#### Producción (Railway)
```env
DATABASE_URL=postgresql://postgres:...@...railway.app:5432/railway
REDIS_URL=redis://...railway.app:6379
SECRET_KEY=...
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
RAILWAY_ENVIRONMENT=production
```

#### Desarrollo Local (.env.local)
```env
DATABASE_URL=postgresql://postgres:Laurana@01@localhost:5432/clip_comparador_v2
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=dev-secret-key-local
# Copiar credenciales de Cloudinary de producción
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

### Sistema de Detección de Entorno
- **Archivo**: `clip_admin_backend/app/config.py`
- **Método**: Detecta automáticamente Railway vs Local
- **Prioridad de carga**:
  1. `.env.local` (desarrollo local) - NO se sube a Git
  2. `.env` (fallback)
  3. Variables de entorno del sistema (Railway)

---

## 🗄️ Base de Datos

### Modelo Client (Crítico)
```python
class Client(db.Model):
    id = db.Column(UUID, primary_key=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    api_key = db.Column(db.String(255), unique=True)
    category_confidence_threshold = db.Column(db.Integer, default=70)  # NUEVO
    product_similarity_threshold = db.Column(db.Integer, default=30)   # NUEVO
    # ... otros campos
```

### Scripts de Base de Datos
1. **add_sensitivity_columns.py** - Agregar columnas de sensibilidad (YA EJECUTADO en Railway)
2. **check_clients_table.py** - Verificar esquema y datos
3. **setup_local_postgres.py** - Inicializar BD local con datos de ejemplo

### Migración Ejecutada en Railway
```sql
ALTER TABLE clients
ADD COLUMN category_confidence_threshold INTEGER DEFAULT 70,
ADD COLUMN product_similarity_threshold INTEGER DEFAULT 30;

UPDATE clients
SET category_confidence_threshold = 70,
    product_similarity_threshold = 30
WHERE category_confidence_threshold IS NULL;
```

---

## 🐛 Errores Corregidos en Esta Sesión

### 1. Error 500 en `/clients/<id>`
- **Causa**: Referencias a `clients.create_api_key` (ruta comentada)
- **Solución**: Comentar modal y botones de API Keys en `view.html`
- **Commit**: `bc408c5`

### 2. Error "name 'threshold' is not defined"
- **Causa**: Variable `threshold` renombrada a `product_similarity_threshold`
- **Solución**: Ya corregido en código actual
- **Estado**: ✅ Funcionando en Railway

### 3. PostgreSQL Local
- **Estado**: Instalado pero necesita configuración
- **Próximos pasos**: Crear BD y ejecutar `setup_local_postgres.py`

---

## 📝 API Endpoints Importantes

### Búsqueda Visual (Flask)
```
POST /api/search
Headers: X-API-Key: <client_api_key>
Body: multipart/form-data
  - image: archivo de imagen
  - limit: número de resultados (default: 5)
```

### Actualizar Sensibilidad
```
POST /clients/<client_id>/update-sensitivity
Headers: Content-Type: application/json
Body: {
  "category_confidence_threshold": 60,
  "product_similarity_threshold": 25
}
```

### Regenerar API Key
```
POST /clients/<client_id>/regenerate-api-key
```

---

## 🔄 Workflow de Desarrollo

### Iniciar Sistema Local (MÉTODO RÁPIDO)
```powershell
# Opción 1: Script completo con validaciones
.\start_local.ps1

# Opción 2: Inicio rápido (3 líneas en 1)
.\start.ps1

# Opción 3: Comando manual
& C:\Personal\CLIP_Comparador_V2\venv\Scripts\Activate.ps1
cd C:\Personal\CLIP_Comparador_V2\clip_admin_backend
python app.py
```

### Primera Configuración (Solo una vez)
```powershell
# 1. Restaurar BD desde Railway
.\restore_from_railway.ps1

# 2. Editar credenciales de Cloudinary
notepad .env.local

# 3. Iniciar sistema
.\start.ps1
```

### Deploy a Railway
```powershell
# 1. Probar localmente
# 2. Commit
git add .
git commit -m "Descripción del cambio"

# 3. Push (deploy automático)
git push
```

---

## 🚨 Problemas Conocidos

1. **Credenciales de Cloudinary Faltantes**: `.env.local` necesita configuración
   - CLOUDINARY_CLOUD_NAME (vacío)
   - CLOUDINARY_API_KEY (vacío)
   - CLOUDINARY_API_SECRET (vacío)
   - Solución: Copiar desde variables de Railway

2. **SQLite**: NO SOPORTADO
   - Sistema requiere PostgreSQL obligatoriamente
   - `config.py` valida y rechaza otras BDs

---

## 📚 Documentación Importante

### Archivos de Referencia
- `docs/SETUP_POSTGRES_LOCAL.md` - Instalación PostgreSQL
- `.github/copilot-instructions.md` - Arquitectura del sistema
- `README.md` - Documentación general

### Commits Importantes
- `38ea243` - UI sliders para sensibilidad por cliente
- `bc408c5` - Fix error 500 en view.html
- `11edbfd` - Setup PostgreSQL local + detección de entorno
- `cfde239` - PostgreSQL obligatorio (sin SQLite)

---

## 🎯 Próximos Pasos

### Inmediatos
1. ✅ Configurar PostgreSQL local correctamente
2. ✅ Crear base de datos `clip_comparador_v2`
3. ✅ Migrar estructura y datos desde Railway
4. ⏳ Obtener credenciales de Cloudinary desde Railway
5. ⏳ Probar sistema en local antes de nuevos deploys

### Pendientes
1. (eliminado) Implementar FastAPI Search API
2. Integrar widget de búsqueda visual en sitios cliente
3. Optimizar rendimiento de embeddings CLIP
4. Implementar analytics de búsquedas

---

## 💡 Notas Técnicas

### CLIP Engine
- Modelo: `openai/clip-vit-base-patch16`
- Detección por centroides de embeddings reales
- Umbrales configurables por cliente
- Filtro de objetos no comerciales

### Sensibilidad por Cliente
- **category_confidence_threshold**: % confianza mínima para detectar categoría (default: 70%)
- **product_similarity_threshold**: % similitud mínima para incluir producto (default: 30%)
- Se dividen por 100.0 antes de usar (valores en BD son enteros 1-100)

### Base de Datos
- **Obligatorio**: PostgreSQL (versión 15+)
- **NO soportado**: SQLite, MySQL, otros
- **Pool de conexiones**: Configurado para Railway
- **Extensiones**: pgvector (para embeddings futuros)

---

## 🔗 Enlaces Útiles

- **PostgreSQL Download**: https://www.postgresql.org/download/windows/
- **Railway Dashboard**: https://railway.app
- **Cloudinary Console**: https://cloudinary.com/console
- **GitHub Repo**: https://github.com/JuanCabardoneschi/CLIP_Comparador_V2

---

**Última actualización**: 17 de Octubre, 2025
**Próximo chat**: Continuar con configuración PostgreSQL local
