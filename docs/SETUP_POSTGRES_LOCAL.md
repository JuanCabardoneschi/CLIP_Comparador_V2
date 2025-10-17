# Setup PostgreSQL Local para Desarrollo

## 1. Descargar e Instalar PostgreSQL

### Descargar
- Ve a: https://www.postgresql.org/download/windows/
- Descarga el instalador de PostgreSQL 15 o 16 (recomendado)
- Ejecuta el instalador

### Durante la Instalación
1. **Componentes**: Instala todo (PostgreSQL Server, pgAdmin 4, Stack Builder, Command Line Tools)
2. **Puerto**: Deja el puerto por defecto `5432`
3. **Superusuario**: Establece una contraseña para el usuario `postgres` (guárdala bien)
4. **Locale**: Deja el por defecto o elige Spanish_Spain.1252

### Verificar Instalación
Después de instalar, abre PowerShell y verifica:
```powershell
# Agregar PostgreSQL al PATH (ajusta la versión)
$env:Path += ";C:\Program Files\PostgreSQL\15\bin"

# Verificar
psql --version
```

## 2. Crear Base de Datos Local

Una vez instalado PostgreSQL:

```powershell
# Conectar como superusuario postgres
psql -U postgres

# Dentro de psql, crear la base de datos:
CREATE DATABASE clip_comparador_v2;

# Crear usuario para la aplicación (opcional, más seguro)
CREATE USER clip_admin WITH PASSWORD 'tu_password_seguro';
GRANT ALL PRIVILEGES ON DATABASE clip_comparador_v2 TO clip_admin;

# Salir
\q
```

## 3. Configurar Variables de Entorno Local

Crear archivo `.env.local` en la raíz del proyecto con:

```env
# Base de datos local PostgreSQL
DATABASE_URL=postgresql://postgres:tu_password@localhost:5432/clip_comparador_v2

# O si creaste el usuario clip_admin:
# DATABASE_URL=postgresql://clip_admin:tu_password_seguro@localhost:5432/clip_comparador_v2

# Resto de configuración (copiar de .env o .env.example)
SECRET_KEY=tu-secret-key-local
FLASK_ENV=development
FLASK_DEBUG=True

# Cloudinary (usar las mismas credenciales)
CLOUDINARY_CLOUD_NAME=tu_cloud_name
CLOUDINARY_API_KEY=tu_api_key
CLOUDINARY_API_SECRET=tu_api_secret

# Redis local (si lo tienes instalado)
REDIS_URL=redis://localhost:6379/0
# O comentar si no tienes Redis local
```

## 4. Inicializar la Base de Datos

Ejecutar el script de inicialización:

```powershell
# Asegurarse de que el venv esté activado
.\.venv\Scripts\Activate.ps1

# Cargar variables de entorno local
$env:DATABASE_URL="postgresql://postgres:tu_password@localhost:5432/clip_comparador_v2"

# Ejecutar script de inicialización
python init_local_db.py
```

## 5. Workflow de Desarrollo

### Desarrollo Local
```powershell
# 1. Activar venv
.\.venv\Scripts\Activate.ps1

# 2. Usar DB local
$env:DATABASE_URL="postgresql://postgres:tu_password@localhost:5432/clip_comparador_v2"

# 3. Correr Flask
cd clip_admin_backend
python app.py
```

### Subir a Railway
```powershell
# 1. Testear localmente primero
# 2. Hacer commit
git add .
git commit -m "Feature tested locally"

# 3. Push (activa deploy automático en Railway)
git push
```

## 6. Herramientas Útiles

### pgAdmin 4
- Interfaz gráfica para gestionar PostgreSQL
- Se instala automáticamente con PostgreSQL
- URL: http://localhost:5432 (o el puerto configurado)

### Comandos psql útiles
```sql
-- Conectar a la base de datos
psql -U postgres -d clip_comparador_v2

-- Listar tablas
\dt

-- Describir tabla
\d nombre_tabla

-- Ver datos
SELECT * FROM clients;

-- Salir
\q
```

## 7. Troubleshooting

### Error: "password authentication failed"
- Verifica la contraseña en DATABASE_URL
- Resetea la contraseña del usuario en psql

### Error: "could not connect to server"
- Verifica que PostgreSQL esté corriendo:
  ```powershell
  Get-Service postgresql*
  ```
- Inicia el servicio si está detenido:
  ```powershell
  Start-Service postgresql-x64-15
  ```

### Error: "database does not exist"
- Crea la base de datos manualmente con psql
- O ejecuta el script de inicialización

## 8. Estrategia de Ramas (Opcional)

Si quieres separar desarrollo de producción:

```powershell
# Crear rama de desarrollo
git checkout -b develop

# Trabajar en develop
# ... hacer cambios ...
git add .
git commit -m "Feature XYZ"

# Cuando esté probado, mergear a main
git checkout main
git merge develop
git push  # Esto despliega a Railway
```

Por ahora, trabajar directo en `main` está bien si pruebas localmente antes de push.
