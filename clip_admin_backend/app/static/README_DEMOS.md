# 🌐 Demos del Widget CLIP - Guía de Uso

## 📁 Archivos Disponibles

### 1. **demo-store-standalone.html** ⭐ RECOMENDADO
- **Uso**: Demo simplificada optimizada para Railway Production
- **Características**:
  - ✅ Funciona desde `file://` (sin servidor local)
  - ✅ Apunta directamente a Railway Production
  - ✅ Sin selector de entorno (solo Railway)
  - ✅ Datos hardcodeados (no hace fetch)

### 2. **demo-store-clean.html**
- **Uso**: Demo completa con selector de entorno
- **Características**:
  - ✅ Funciona desde `file://` (sin servidor local)
  - ✅ Selector de entorno (Local/Railway)
  - ✅ Por defecto apunta a Railway
  - ✅ Permite cambiar entre entornos

---

## 🚀 Formas de Abrir las Demos

### Opción A: Usando PowerShell Script (Recomendado)

```powershell
# Abrir versión standalone
.\open-demo.ps1 standalone

# Abrir versión clean (con selector de entorno)
.\open-demo.ps1 clean
```

### Opción B: Desde el Explorador de Archivos
1. Navegar a: `C:\Personal\CLIP_Comparador_V2\clip_admin_backend\app\static\`
2. Doble clic en:
   - `demo-store-standalone.html` (más simple)
   - `demo-store-clean.html` (más opciones)

### Opción C: Desde Railway (Online)
- Standalone: https://clipcomparadorv2-production.up.railway.app/static/demo-store-standalone.html
- Clean: https://clipcomparadorv2-production.up.railway.app/static/demo-store-clean.html

---

## ⚠️ Solución de Problemas

### Error: "CORS policy blocked the request"

**Causa**: Los navegadores bloquean peticiones desde `file://` a URLs remotas por seguridad.

**Solución 1: Abrir Chrome sin CORS** (Desarrollo/Testing)
```powershell
Start-Process "chrome.exe" -ArgumentList "--disable-web-security --user-data-dir=C:/temp/chrome-dev file:///C:/Personal/CLIP_Comparador_V2/clip_admin_backend/app/static/demo-store-standalone.html"
```

**Solución 2: Usar Railway Directamente** (Recomendado)
Acceder a: https://clipcomparadorv2-production.up.railway.app/static/demo-store-standalone.html

**Solución 3: Levantar Servidor Local**
```powershell
cd C:\Personal\CLIP_Comparador_V2\clip_admin_backend
python app.py
# Luego abrir: http://localhost:5000/static/demo-store-clean.html
```

### Error: "Failed to load widget script"

**Causa**: Railway puede estar caído o el script no existe.

**Verificación**:
```powershell
# Verificar que Railway esté online
curl https://clipcomparadorv2-production.up.railway.app/health

# Verificar que el script existe
curl https://clipcomparadorv2-production.up.railway.app/static/js/clip-widget-embed-v3.js
```

---

## 🔑 Clientes Configurados

### Goody Store (Demo Fashion)
- **API Key**: `test-api-key-demo-fashion-store-2024`
- **Descripción**: Cliente de prueba con catálogo completo
- **Catálogo**: ~90 productos de moda

### Eve's Store
- **API Key**: `clip_fe117bcd62de8a1e05a214c5`
- **Descripción**: Cliente de producción con catálogo real
- **Catálogo**: Productos reales

---

## 🎯 Casos de Uso

### Caso 1: Testing Rápido de Railway
```powershell
.\open-demo.ps1 standalone
```
Luego:
1. Seleccionar cliente (Goody o Eve)
2. Subir imagen de prueba
3. Verificar resultados

### Caso 2: Comparar Local vs Railway
```powershell
.\open-demo.ps1 clean
```
Luego:
1. Probar en "Production (Railway)"
2. Cambiar a "Development (Local)" (requiere servidor local)
3. Comparar resultados

### Caso 3: Demo para Cliente (Sin Código)
1. Compartir URL: https://clipcomparadorv2-production.up.railway.app/static/demo-store-standalone.html
2. Cliente abre directamente en navegador
3. Funciona inmediatamente sin configuración

---

## 📊 Configuración Técnica

### demo-store-standalone.html
```javascript
window.CLIPWidget = {
    apiKey: 'test-api-key-demo-fashion-store-2024',
    serverUrl: 'https://clipcomparadorv2-production.up.railway.app',
    clientName: 'Goody Store'
};
```

### demo-store-clean.html
```javascript
const environments = {
    local: 'http://localhost:5000',
    railway: 'https://clipcomparadorv2-production.up.railway.app'
};
let currentEnvironment = 'railway'; // Por defecto
```

---

## 🔧 Modificaciones Realizadas (14 Nov 2025)

1. ✅ Cambiado script del widget de ruta relativa a absoluta (Railway)
2. ✅ Por defecto apunta a Railway en ambos archivos
3. ✅ Creado versión standalone sin selector de entorno
4. ✅ Agregado script PowerShell para abrir fácilmente
5. ✅ Documentación completa de uso

---

## 📝 Notas Importantes

- **No requiere servidor local**: Ambos archivos funcionan desde `file://`
- **Widget desde Railway**: Se carga `clip-widget-embed-v3.js` desde Railway
- **API Keys iguales**: Mismas keys en Local y Railway
- **CORS**: Puede requerir Chrome sin security o acceso directo a Railway
- **Producción**: Usar siempre desde Railway para evitar problemas CORS

---

## 🆘 Soporte

Si encuentras problemas:
1. Verificar que Railway esté online: https://clipcomparadorv2-production.up.railway.app/health
2. Revisar consola del navegador (F12)
3. Probar con Chrome sin CORS (ver Solución de Problemas)
4. Como última opción, levantar servidor local

---

**Última actualización**: 14 de Noviembre 2025
