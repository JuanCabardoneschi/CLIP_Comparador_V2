# 🚂 VARIABLES DE ENTORNO PARA RAILWAY

## Variables que DEBES configurar en Railway Dashboard:

### 🗄️ Base de Datos
```
DATABASE_URL = postgresql://postgres:TU_PASSWORD@ballast.proxy.rlwy.net:54363/railway
```

### ☁️ Cloudinary
```
CLOUDINARY_CLOUD_NAME = tu-cloud-name
CLOUDINARY_API_KEY = tu-api-key  
CLOUDINARY_API_SECRET = tu-api-secret
```

### 🔐 Flask Security
```
SECRET_KEY = una-clave-super-segura-de-32-caracteres-minimo
```

### ⚙️ Configuración Flask
```
FLASK_ENV = production
FLASK_DEBUG = False
```

### 🤖 CLIP
```
CLIP_MODEL_NAME = ViT-B/16
```

## 📋 Cómo configurar en Railway:

1. Ve a tu proyecto en railway.app
2. Click en "Variables" 
3. Agrega cada variable una por una
4. Click "Deploy" después de agregar todas

## ✅ Variables opcionales:
```
LOG_LEVEL = INFO
PORT = 5000  (Railway lo configura automáticamente)
```