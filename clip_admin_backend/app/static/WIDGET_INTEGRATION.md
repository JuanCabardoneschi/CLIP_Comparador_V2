# 🎯 CLIP Widget - Integración Simple (Solo 3 Líneas)

## 📄 Demos Standalone

### 🛍️ Goody Store (Demo Fashion)
- **Archivo**: `goody-store-demo.html`
- **API Key**: `test-api-key-demo-fashion-store-2024`
- **Acceso directo**: https://clipcomparadorv2-production.up.railway.app/static/goody-store-demo.html
- **Local**: `file:///C:/Personal/CLIP_Comparador_V2/clip_admin_backend/app/static/goody-store-demo.html`

### 👗 Eve's Store
- **Archivo**: `eve-store-demo.html`
- **API Key**: `clip_fe117bcd62de8a1e05a214c5`
- **Acceso directo**: https://clipcomparadorv2-production.up.railway.app/static/eve-store-demo.html
- **Local**: `file:///C:/Personal/CLIP_Comparador_V2/clip_admin_backend/app/static/eve-store-demo.html`

---

## 🚀 Integración en Cualquier Página Web

Para integrar el widget en **cualquier página web existente**, solo copia y pega estas 3 líneas:

### Para Goody Store:
```html
<script>
    window.CLIPWidget = {
        apiKey: 'test-api-key-demo-fashion-store-2024',
        serverUrl: 'https://clipcomparadorv2-production.up.railway.app'
    };
</script>
<div id="clip-widget"></div>
<script src="https://clipcomparadorv2-production.up.railway.app/static/js/clip-widget-button.js"></script>
```

### Para Eve's Store:
```html
<script>
    window.CLIPWidget = {
        apiKey: 'clip_fe117bcd62de8a1e05a214c5',
        serverUrl: 'https://clipcomparadorv2-production.up.railway.app'
    };
</script>
<div id="clip-widget"></div>
<script src="https://clipcomparadorv2-production.up.railway.app/static/js/clip-widget-button.js"></script>
```

## 🎯 ¿Cómo Funciona?

1. **El cliente pega las 3 líneas** en su página web
2. **Se renderiza un botón flotante** "🔍 Buscar con IA" (esquina inferior derecha)
3. **Click en el botón** → Redirige a `/widget/search?api_key=...&return_url=...`
4. **Página de búsqueda completa** con toda la funcionalidad (imagen + texto)
5. **Botón "Volver a la tienda"** → Regresa a la página original del cliente

---

## ✅ Características

- ✅ **Solo 3 líneas de código**
- ✅ **Sin dependencias** (todo incluido en el widget)
- ✅ **Responsive** (se adapta a cualquier tamaño)
- ✅ **Plug & Play** (copiar y pegar)
- ✅ **Funciona desde file://** (sin servidor)
- ✅ **Funciona desde cualquier dominio**
- ✅ **Producción Railway**

---

## 🎨 Personalización (Opcional)

Si quieres personalizar el estilo, puedes agregar CSS adicional:

```html
<style>
    #clip-widget {
        max-width: 1200px;
        margin: 2rem auto;
    }
</style>
```

---

## 📦 Archivos Incluidos

```
clip_admin_backend/app/static/
├── eve-store-demo.html          ← Demo standalone Eve's Store
├── goody-store-demo.html        ← Demo standalone Goody Store
└── js/
    └── clip-widget-embed-v3.js  ← Widget completo (Railway)
```

---

## 🔧 Uso Local (Testing)

### Opción 1: Abrir directamente desde el explorador
1. Navegar a: `C:\Personal\CLIP_Comparador_V2\clip_admin_backend\app\static\`
2. Doble clic en:
   - `eve-store-demo.html`
   - `goody-store-demo.html`

### Opción 2: Desde PowerShell
```powershell
# Eve's Store
Start-Process "file:///C:/Personal/CLIP_Comparador_V2/clip_admin_backend/app/static/eve-store-demo.html"

# Goody Store
Start-Process "file:///C:/Personal/CLIP_Comparador_V2/clip_admin_backend/app/static/goody-store-demo.html"
```

### Opción 3: Desde Railway (Producción)
- Eve's Store: https://clipcomparadorv2-production.up.railway.app/static/eve-store-demo.html
- Goody Store: https://clipcomparadorv2-production.up.railway.app/static/goody-store-demo.html

---

## ⚠️ Notas Importantes

1. **CORS**: El widget carga desde Railway, puede tener problemas CORS desde `file://`
2. **Solución CORS**: Mejor acceder directamente desde Railway (URLs arriba)
3. **API Keys**: Mismas keys en local y Railway (producción)
4. **Script del widget**: Siempre carga desde Railway (`https://clipcomparadorv2-production.up.railway.app/static/js/clip-widget-embed-v3.js`)

---

## 🎯 Ejemplo de Integración en WordPress, Shopify, etc.

### WordPress:
1. Ir a **Páginas** → **Editar página**
2. Agregar bloque **HTML Personalizado**
3. Pegar las 3 líneas del widget
4. Publicar

### Shopify:
1. Ir a **Online Store** → **Pages** → **Add page**
2. Click en **Show HTML**
3. Pegar las 3 líneas del widget
4. Save

### HTML Estático:
1. Abrir tu archivo `.html`
2. Pegar las 3 líneas donde quieras que aparezca el widget
3. Guardar y abrir en navegador

---

## 📞 Soporte

Si el widget no carga:
1. Verificar que Railway esté online: https://clipcomparadorv2-production.up.railway.app/health
2. Abrir consola del navegador (F12) y revisar errores
3. Verificar que la API key sea correcta

---

**Última actualización**: 14 de Noviembre 2025
