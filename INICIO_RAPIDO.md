# 🚀 Inicio Rápido - CLIP Comparador V2 Local

## Comandos de Inicio

### ⚡ Inicio Rápido (Recomendado)
```powershell
.\start_local.ps1
```
Este script valida todo antes de iniciar y muestra información útil.

### 🏃 Inicio Express
```powershell
.\start.ps1
```
Inicia directamente sin validaciones (más rápido).

### 📝 Inicio Manual
```powershell
# Activar entorno virtual
& C:\Personal\CLIP_Comparador_V2\venv\Scripts\Activate.ps1

# Ir al directorio de la app
cd C:\Personal\CLIP_Comparador_V2\clip_admin_backend

# Ejecutar Flask
python app.py
```

---

## 🌐 Acceso al Sistema

Una vez iniciado el servidor:

- **URL**: http://localhost:5000
- **Super Admin**:
  - Usuario: `admin`
  - Password: `admin123`
- **Cliente Demo**:
  - Usuario: `demo`
  - Password: `demo123`

---

## 🛠️ Primera Vez (Configuración Inicial)

Si es tu primera vez ejecutando el sistema:

### 1️⃣ Restaurar Base de Datos desde Railway
```powershell
.\restore_from_railway.ps1
```

### 2️⃣ Configurar Credenciales de Cloudinary
```powershell
notepad .env.local
```
Asegúrate de que estas 3 variables estén configuradas:
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

### 3️⃣ Iniciar el Sistema
```powershell
.\start.ps1
```

---

## 📊 Estado del Sistema

### ✅ Configurado y Funcionando
- PostgreSQL 18.0 local
- Base de datos: `clip_comparador_v2`
- 1 cliente (Demo Fashion Store)
- 2 usuarios (admin + demo)
- 12 categorías con centroides CLIP
- 51 productos
- 58 imágenes

### 🔧 Tecnologías
- **Backend**: Flask 3.0
- **Base de Datos**: PostgreSQL 18.0
- **IA**: CLIP (ViT-B/16) via Transformers
- **Storage**: Cloudinary
- **Cache**: Redis (opcional en desarrollo)

---

## 🆘 Troubleshooting

### Error: "Base de datos no encontrada"
```powershell
.\restore_from_railway.ps1
```

### Error: "Credenciales de Cloudinary faltantes"
```powershell
notepad .env.local
# Agregar las 3 variables de Cloudinary
```

### Error: "PostgreSQL no responde"
```powershell
# Verificar servicio
Get-Service postgresql*

# Si no está corriendo, iniciar:
Start-Service postgresql-x64-18
```

### Error: "Puerto 5000 en uso"
```powershell
# Encontrar y matar proceso
Get-Process -Name python | Stop-Process -Force
```

---

## 📁 Estructura de Archivos Importantes

```
CLIP_Comparador_V2/
├── start.ps1                    # ⚡ Inicio rápido
├── start_local.ps1              # 🔍 Inicio con validaciones
├── restore_from_railway.ps1     # 📦 Restaurar BD desde Railway
├── .env.local                   # ⚙️ Configuración local (NO SUBIR A GIT)
├── .env.local.example           # 📋 Template de configuración
├── clip_admin_backend/
│   └── app.py                   # 🚀 Aplicación Flask principal
├── docs/
│   ├── SESSION_SUMMARY.md       # 📚 Resumen completo de la sesión
│   └── MIGRACION_BD_LOCAL.md    # 📖 Guía de migración de BD
└── requirements.txt             # 📦 Dependencias Python
```

---

## 🎯 Próximos Pasos Después de Iniciar

1. Accede a http://localhost:5000
2. Login con `admin` / `admin123`
3. Explora las secciones:
   - **Dashboard**: Vista general del sistema
   - **Clientes**: Gestión de clientes (Demo Fashion Store)
   - **Categorías**: 12 categorías con centroides CLIP
   - **Productos**: 51 productos catalogados
   - **Imágenes**: 58 imágenes con embeddings
4. Prueba la búsqueda visual con el endpoint `/api/search`

---

## 📞 Soporte

Para más información, consulta:
- `docs/SESSION_SUMMARY.md` - Resumen completo
- `docs/MIGRACION_BD_LOCAL.md` - Detalles de la BD
- `.github/copilot-instructions.md` - Arquitectura del sistema

---

**¡Sistema listo para desarrollo! 🎉**
