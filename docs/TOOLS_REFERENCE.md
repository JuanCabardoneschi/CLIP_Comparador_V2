# Guía de Herramientas y Scripts - CLIP Comparador V2

##  Propósito

Este documento es una referencia rápida de todas las herramientas, scripts y comandos disponibles en el proyecto. **Consulta este archivo antes de crear nuevas herramientas o scripts similares.**

---

##  Organización de Scripts

### Scripts en Raíz del Proyecto
Scripts principales de uso frecuente.

### Scripts en `tools/`
Herramientas de mantenimiento, diagnóstico y migraciones.

### Scripts PowerShell (*.ps1)
Scripts de automatización para Windows.

---

##  Gestión de Base de Datos

### Railway (Producción)

#### `railway_db_tool.py` - Herramienta Completa de BD Railway
**Ubicación**: Raíz del proyecto

**Propósito**: Punto único para modificaciones en la BD de producción Railway.

**Uso**:
```bash
# Ver conteos de todas las tablas
python railway_db_tool.py counts

# Arreglar imágenes pendientes de embedding
python railway_db_tool.py fix-pending-images --yes

# Ejecutar SQL directo
python railway_db_tool.py sql -e "SELECT * FROM clients;" --yes

# Ejecutar archivo SQL
python railway_db_tool.py sql -f script.sql --yes

# Ver todas las opciones
python railway_db_tool.py --help
```

**Características**:
-  Conexión directa a Railway (ballast.proxy.rlwy.net:54363)
-  Modo seguro por defecto (ROLLBACK sin --yes)
-  Múltiples comandos: counts, sql, fix-pending-images
-  Soporta SQL inline (-e) o desde archivo (-f)

**Conexión**:
```python
host = 'ballast.proxy.rlwy.net'
port = 54363
database = 'railway'
user = 'postgres'
password = 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
```

#### `check_prod_embeddings.py` - Verificar Embeddings en Railway
**Propósito**: Verificar estado de embeddings en producción.

**Uso**:
```bash
python check_prod_embeddings.py
```

**Output**: Estado de embeddings por cliente y categoría.

---

### PostgreSQL Local

#### `backup_local_db.py` - Backup BD Local
**Propósito**: Crear backup de la base de datos local.

**Uso**:
```bash
python backup_local_db.py
```

**Output**: `backups/local_<timestamp>.dump`

**Características**:
- Lee DATABASE_URL de `.env.local`
- Usa pg_dump con formato custom (-Fc)
- Timestamp automático
- Guarda en carpeta `backups/`

#### `restore_from_railway.ps1` - Restaurar desde Railway
**Propósito**: Restaurar BD local desde Railway.

**Uso**:
```powershell
.\restore_from_railway.ps1
```

**Pasos**:
1. Pregunta si eliminar BD local existente
2. Crea BD local limpia
3. Descarga dump de Railway
4. Restaura a local
5. Valida extensiones

#### `setup_local_postgres.py` - Setup Inicial BD Local
**Propósito**: Configurar BD local desde cero.

**Uso**:
```bash
python setup_local_postgres.py
```

**Acciones**:
- Crea base de datos
- Instala extensiones (pgvector, uuid-ossp)
- Ejecuta migraciones
- Carga datos demo opcionales

#### `setup_postgres.ps1` - Setup PostgreSQL Completo
**Propósito**: Validar instalación PostgreSQL y configurar BD.

**Uso**:
```powershell
.\setup_postgres.ps1
```

**Validaciones**:
- PostgreSQL instalado
- Servicio corriendo
- pgvector disponible
- BD creada
- Extensiones instaladas

---

## 🔍 Diagnóstico y Verificación

### `check_embeddings.py` - Verificar Embeddings Locales
**Propósito**: Verificar estado de embeddings en BD local.

**Uso**:
```bash
python check_embeddings.py
```

**Output**:
- Cliente encontrado
- Categorías con/sin centroides
- Productos con/sin embeddings
- Resumen de estado

### `check_clients_id.py` - Verificar IDs de Clientes
**Propósito**: Listar todos los clientes y sus IDs.

**Uso**:
```bash
python check_clients_id.py
```

**Output**: Tabla con ID, nombre, API key de cada cliente.

---

## 🚀 Inicio y Ejecución

### `start.ps1` - Inicio Rápido
**Propósito**: Iniciar aplicación Flask directamente.

**Uso**:
```powershell
.\start.ps1
```

**Acciones**:
- Activa entorno virtual
- Va a clip_admin_backend
- Ejecuta python app.py

### `start_local.ps1` - Inicio con Validaciones
**Propósito**: Iniciar aplicación con validaciones previas.

**Uso**:
```powershell
.\start_local.ps1
```

**Validaciones**:
- PostgreSQL corriendo
- BD existe
- .env.local configurado
- Dependencias instaladas
- Muestra información útil

---

## 🔑 Patrones y Convenciones

### Conexión a Railway

```python
# Siempre usar estas credenciales
host = 'ballast.proxy.rlwy.net'
port = 54363
database = 'railway'
user = 'postgres'
password = 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
```

### Conexión Local

```python
# Leer de .env.local
from dotenv import load_dotenv
load_dotenv('.env.local')
db_url = os.getenv("DATABASE_URL")
# postgresql://postgres:Laurana@01@localhost:5432/clip_comparador_v2
```

### Backups

**Naming**: `<tipo>_<timestamp>.dump`
- `local_20251024_123456.dump`
- `railway_20251024_123456.dump`

**Ubicación**: `backups/` en raíz del proyecto

**Formato**: Custom format (-Fc) de pg_dump

---

## 💡 Tips Importantes

### Antes de Crear un Nuevo Script

1. **Busca primero**: `railway_db_tool.py` puede hacer lo que necesitas
2. **Revisa tools/**: Puede que ya exista una herramienta similar
3. **Consulta este archivo**: Para mantener consistencia

### Para Modificar Railway

1. **Siempre usa railway_db_tool.py** para cambios en producción
2. **Modo seguro por defecto**: Sin `--yes` hace ROLLBACK
3. **Test primero en local**: Restaura con `restore_from_railway.ps1` y prueba

### Para Backups

1. **Backup antes de cambios grandes**: `python backup_local_db.py`
2. **Backups regulares de Railway**: Usar railway_db_tool.py
3. **Guarda en carpeta backups/**: Ya está en .gitignore

---

## 📚 Recursos Relacionados

- [README.md](../README.md) - Documentación completa
- [INICIO_RAPIDO.md](../INICIO_RAPIDO.md) - Guía de inicio
- [docs/INSTALLATION.md](./INSTALLATION.md) - Instalación
- [docs/SETUP_POSTGRES_LOCAL.md](./SETUP_POSTGRES_LOCAL.md) - Setup PostgreSQL

---

**Fecha última actualización**: 24 de Octubre, 2025
