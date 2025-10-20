# 📸 Guía Oficial de Manejo de Imágenes

**Fecha**: 20 Octubre 2025  
**Versión**: 2.0 (Post FASE 3)

---

## 🎯 Regla de Oro

> **SIEMPRE usar propiedades del modelo `Image`**  
> **NUNCA llamar métodos de managers para obtener URLs**

---

## ✅ Patrón CORRECTO

### Para Mostrar Imágenes en UI

```python
from app.models.image import Image

# ✅ CORRECTO - Usar propiedad del modelo
image = Image.query.get(image_id)
url = image.display_url        # Para mostrar en pantalla
thumbnail = image.thumbnail_url # Para thumbnails
medium = image.medium_url       # Para tamaño mediano
```

### En Templates Jinja2

```html
<!-- ✅ CORRECTO -->
<img src="{{ image.display_url }}" alt="{{ image.alt_text }}">
<img src="{{ image.thumbnail_url }}" alt="{{ image.alt_text }}">
```

### En API Responses

```python
# ✅ CORRECTO
results = [{
    "id": image.id,
    "url": image.display_url,
    "thumbnail": image.thumbnail_url
} for image in images]
```

---

## ❌ Patrones INCORRECTOS (Deprecados)

### ⚠️ NO usar ImageManager.get_image_url()

```python
from app.services.image_manager import image_manager

# ❌ DEPRECADO - Emitirá warning
url = image_manager.get_image_url(image)
```

**Reemplazar con:**
```python
# ✅ CORRECTO
url = image.display_url
```

### ⚠️ NO usar CloudinaryManager.get_image_url()

```python
from app.services.cloudinary_manager import cloudinary_manager

# ❌ DEPRECADO - Emitirá warning
url = cloudinary_manager.get_image_url(image)
```

**Reemplazar con:**
```python
# ✅ CORRECTO
url = image.display_url
```

---

## 📋 Propiedades Disponibles del Modelo Image

### `image.display_url`
**Uso**: Imagen principal para mostrar en pantalla  
**Retorna**: `str` - URL de Cloudinary o placeholder  
**Ejemplo**:
```python
# Vista de producto
<img src="{{ product.primary_image.display_url }}" alt="{{ product.name }}">
```

### `image.thumbnail_url`
**Uso**: Thumbnail para listados y previsualizaciones  
**Retorna**: `str` - URL de Cloudinary o placeholder  
**Ejemplo**:
```python
# Galería de productos
{% for product in products %}
    <img src="{{ product.primary_image.thumbnail_url }}">
{% endfor %}
```

### `image.medium_url`
**Uso**: Tamaño mediano para detalles  
**Retorna**: `str` - URL de Cloudinary o placeholder  
**Ejemplo**:
```python
# Modal de preview
<img src="{{ image.medium_url }}" alt="Preview">
```

---

## 🏗️ Arquitectura de Manejo de Imágenes

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND / TEMPLATES                        │
│  Usa: image.display_url, image.thumbnail_url                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MODELO IMAGE (models/image.py)                │
│  @property display_url → return self.cloudinary_url              │
│  @property thumbnail_url → return self.cloudinary_url            │
│  @property medium_url → return self.cloudinary_url               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              CAMPO cloudinary_url (Base de Datos)                │
│  Contiene: https://res.cloudinary.com/.../image.jpg              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Responsabilidades Claras

### Modelo `Image` (models/image.py)
**Qué HACE**:
- ✅ Proveer URLs para frontend vía `@property`
- ✅ Definir relaciones con Product, Client
- ✅ Validar estructura de datos

**Qué NO hace**:
- ❌ Subir archivos
- ❌ Procesar imágenes
- ❌ Interactuar con Cloudinary API

### `ImageManager` (services/image_manager.py)
**Qué HACE**:
- ✅ `upload_from_file()` - Subir desde archivo
- ✅ `upload_from_url()` - Subir desde URL
- ✅ `delete_image()` - Eliminar imagen
- ✅ `get_image_base64()` - Para embeddings CLIP
- ✅ `process_image()` - Resize, optimize, etc

**Qué NO hace**:
- ❌ ~~`get_image_url()`~~ → **DEPRECADO** (usar `image.display_url`)

### `CloudinaryManager` (services/cloudinary_manager.py)
**Qué HACE**:
- ✅ `upload()` - Upload a Cloudinary
- ✅ `delete()` - Delete de Cloudinary
- ✅ `test_connection()` - Verificar conexión
- ✅ Gestionar API de Cloudinary

**Qué NO hace**:
- ❌ ~~`get_image_url()`~~ → **DEPRECADO** (usar `image.display_url`)
- ❌ ~~`get_image_base64()`~~ → **DEPRECADO** (Cloudinary usa URLs)

---

## 🚀 Migración de Código Existente

### Antes (Patrón Antiguo)
```python
from app.services.image_manager import image_manager

def view_product(product_id):
    product = Product.query.get(product_id)
    image = product.primary_image
    
    # ❌ Antiguo
    image_url = image_manager.get_image_url(image)
    
    return render_template('product.html', image_url=image_url)
```

### Después (Patrón Nuevo)
```python
def view_product(product_id):
    product = Product.query.get(product_id)
    image = product.primary_image
    
    # ✅ Nuevo - más simple y directo
    image_url = image.display_url
    
    return render_template('product.html', image_url=image_url)
```

O mejor aún, pasar el objeto directamente:
```python
def view_product(product_id):
    product = Product.query.get(product_id)
    
    # ✅ Mejor - el template accede directamente a la propiedad
    return render_template('product.html', product=product)
```

Template:
```html
<img src="{{ product.primary_image.display_url }}" alt="{{ product.name }}">
```

---

## ⚠️ Warnings de Deprecación

A partir de hoy (20 Oct 2025), llamar a los métodos deprecados emitirá:

```
DeprecationWarning: ImageManager.get_image_url() está deprecado. 
Usar image.display_url directamente. 
Este método será eliminado en futuras versiones.
```

**Timeline de eliminación:**
- ✅ **Hoy**: Métodos deprecados con warnings
- 🔄 **+1 semana**: Revisión de warnings en logs
- 🗑️ **+2 semanas**: Eliminación definitiva de métodos

---

## 📚 Ejemplos de Casos de Uso

### 1. Listado de Productos
```python
# products/index.html
{% for product in products %}
<div class="product-card">
    <img src="{{ product.primary_image.thumbnail_url }}" 
         alt="{{ product.name }}">
    <h3>{{ product.name }}</h3>
</div>
{% endfor %}
```

### 2. API de Búsqueda
```python
# api.py - Search endpoint
results = [{
    "product_id": product.id,
    "name": product.name,
    "image_url": product.primary_image.display_url,  # ✅
    "similarity": similarity
} for product in matching_products]
```

### 3. Widget Embed
```javascript
// clip-widget-embed.js
results.forEach(item => {
    const img = document.createElement('img');
    img.src = item.image_url;  // Ya viene desde backend como image.display_url
    resultsContainer.appendChild(img);
});
```

---

## 🔍 Verificación y Testing

### Verificar que no hay uso de métodos deprecados

```bash
# Buscar llamadas a get_image_url() en el código
grep -r "get_image_url" --include="*.py" clip_admin_backend/

# Verificar warnings en logs de Railway
# Revisar: https://railway.app/project/.../deployments/latest/logs
```

### Test de migración
```python
# test_image_properties.py
def test_image_display_url():
    image = Image.query.first()
    
    # ✅ Verificar que la propiedad funciona
    assert image.display_url is not None
    assert image.display_url.startswith('https://')
    
def test_deprecated_warning():
    image = Image.query.first()
    
    # ⚠️ Verificar que emite warning
    with pytest.warns(DeprecationWarning):
        url = image_manager.get_image_url(image)
```

---

## 📖 Referencias

- **Modelo Image**: `clip_admin_backend/app/models/image.py`
- **ImageManager**: `clip_admin_backend/app/services/image_manager.py`
- **CloudinaryManager**: `clip_admin_backend/app/services/cloudinary_manager.py`
- **Auditoría Arquitectónica**: `docs/ARCHITECTURAL_AUDIT_2025-10-20.md`
- **Resumen de Refactor**: `REFACTOR_SUMMARY.md`

---

**Última Actualización**: 20 Octubre 2025  
**Próxima Revisión**: 3 Noviembre 2025 (verificar eliminación de métodos deprecados)
