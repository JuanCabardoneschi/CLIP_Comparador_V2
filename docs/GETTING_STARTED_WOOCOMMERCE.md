# 🚀 Guía de Inicio: Integración WooCommerce

## Paso 1: Revisar Documentación

Hemos creado los siguientes documentos:

1. **`PLAN_INTEGRACION_WOOCOMMERCE.md`** - Plan completo y detallado
2. **`RESUMEN_WOOCOMMERCE.md`** - Comparación ejecutiva
3. **Este archivo** - Guía práctica de inicio

---

## Paso 2: Configurar Base de Datos

### Crear migración para nueva tabla

```bash
# Desde la raíz del proyecto
cd clip_admin_backend

# Crear migración
python manage.py db migrate -m "Add WooCommerce integration support"

# Revisar migración generada
# Debe crear tabla woocommerce_integrations con todos los campos

# Aplicar migración
python manage.py db upgrade
```

### Verificar tabla creada

```bash
# Local
python local_db_tool.py sql -e "SELECT table_name FROM information_schema.tables WHERE table_name = 'woocommerce_integrations';"

# Railway (cuando esté listo)
python railway_db_tool.py sql -e "SELECT table_name FROM information_schema.tables WHERE table_name = 'woocommerce_integrations';"
```

---

## Paso 3: Registrar Blueprint en App

Editar `clip_admin_backend/app/__init__.py` o donde registres blueprints:

```python
# Importar blueprint
from app.blueprints import woocommerce_setup

# Registrar
app.register_blueprint(woocommerce_setup.bp)
```

O si usas un archivo separado para blueprints (`app/routes.py`):

```python
def register_blueprints(app):
    # ... otros blueprints existentes

    # WooCommerce
    from app.blueprints import woocommerce_setup
    app.register_blueprint(woocommerce_setup.bp)
```

---

## Paso 4: Crear Tienda de Prueba WooCommerce

### Opción A: Local con Docker (Recomendado)

```bash
# Crear docker-compose.yml para WooCommerce
docker-compose up -d

# Acceder a http://localhost:8080
# Completar instalación de WordPress + WooCommerce
```

**docker-compose.yml ejemplo:**
```yaml
version: '3.8'

services:
  wordpress:
    image: wordpress:latest
    ports:
      - "8080:80"
    environment:
      WORDPRESS_DB_HOST: db
      WORDPRESS_DB_USER: wordpress
      WORDPRESS_DB_PASSWORD: wordpress
      WORDPRESS_DB_NAME: wordpress
    volumes:
      - wordpress_data:/var/www/html

  db:
    image: mysql:5.7
    environment:
      MYSQL_DATABASE: wordpress
      MYSQL_USER: wordpress
      MYSQL_PASSWORD: wordpress
      MYSQL_ROOT_PASSWORD: rootpass
    volumes:
      - db_data:/var/lib/mysql

  woocommerce:
    image: wordpress:latest
    depends_on:
      - wordpress
    entrypoint: /bin/bash -c "wp plugin install woocommerce --activate"

volumes:
  wordpress_data:
  db_data:
```

### Opción B: Hosting Gratuito

1. Crear cuenta en [InstaWP](https://instawp.com/) o [TasteWP](https://tastewp.com/)
2. Instalar WooCommerce plugin
3. Generar productos de prueba

---

## Paso 5: Configurar WooCommerce REST API

### En tu tienda WooCommerce:

1. **Habilitar Permalinks:**
   - Ir a: `Settings → Permalinks`
   - Seleccionar: "Post name" o cualquier opción excepto "Plain"
   - Guardar cambios

2. **Generar Consumer Keys:**
   - Ir a: `WooCommerce → Settings → Advanced → REST API`
   - Click: "Add key"
   - Descripción: `CLIP Comparador Test`
   - Usuario: Seleccionar admin
   - Permisos: `Read/Write`
   - Click "Generate API Key"
   - **⚠️ COPIAR Y GUARDAR:**
     - Consumer Key (ck_...)
     - Consumer Secret (cs_...)

---

## Paso 6: Probar Conexión Manualmente

### Con cURL:

```bash
# Reemplazar con tus datos
STORE_URL="http://localhost:8080"
CONSUMER_KEY="ck_xxxxxxxxxxxxx"
CONSUMER_SECRET="cs_xxxxxxxxxxxxx"

# Test básico
curl -u "$CONSUMER_KEY:$CONSUMER_SECRET" \
  "$STORE_URL/wp-json/wc/v3/system_status"

# Listar productos
curl -u "$CONSUMER_KEY:$CONSUMER_SECRET" \
  "$STORE_URL/wp-json/wc/v3/products"
```

### Con Postman:

1. Crear nueva request: `GET {store_url}/wp-json/wc/v3/system_status`
2. Authorization: "Basic Auth"
3. Username: `ck_xxxxxxxxxxxxx`
4. Password: `cs_xxxxxxxxxxxxx`
5. Send

---

## Paso 7: Probar Formulario de Conexión

### Iniciar servidor local:

```bash
cd clip_admin_backend
python app.py
```

### Acceder al formulario:

```
http://localhost:5000/woocommerce/connect
```

### Completar formulario:

1. **URL de Tienda**: `http://localhost:8080` (o tu URL de prueba)
2. **Consumer Key**: Pegar el generado
3. **Consumer Secret**: Pegar el generado
4. Click "Probar Conexión"
5. Si es exitoso, click "Guardar Integración"

### Verificar en base de datos:

```bash
# Ver integración creada
python local_db_tool.py sql -e "SELECT id, store_url, store_name, is_active FROM woocommerce_integrations;"

# Ver cliente asociado
python local_db_tool.py sql -e "SELECT id, name, integration_type, api_key FROM clients WHERE integration_type = 'woocommerce';"
```

---

## Paso 8: Próximos Desarrollos

Una vez confirmado que el setup básico funciona:

### 1. WooCommerceSyncService

```python
# clip_admin_backend/app/services/woocommerce_sync_service.py

class WooCommerceSyncService:
    """Servicio de sincronización similar a TiendanubeSyncService"""

    def __init__(self, integration: WooCommerceIntegration):
        self.integration = integration
        self.client = WooCommerceAPIClient(...)

    def full_sync(self):
        """Sincronización completa"""
        self.sync_categories()
        self.sync_products()
        self.process_embeddings()

    def sync_categories(self):
        """Sincronizar categorías desde WooCommerce"""
        pass

    def sync_products(self):
        """Sincronizar productos con imágenes"""
        pass

    def process_embeddings(self):
        """Generar embeddings CLIP"""
        pass
```

### 2. Webhook Receiver

```python
# clip_admin_backend/app/blueprints/woocommerce_webhooks.py

@bp.route('/api/webhooks/woocommerce', methods=['POST'])
def receive_webhook():
    """Recibe y procesa webhooks de WooCommerce"""

    # Validar HMAC
    # Procesar evento
    # Actualizar producto/categoría

    pass
```

### 3. Plugin WordPress

```php
<?php
/**
 * Plugin Name: CLIP Comparador Widget
 * Description: Visual search widget for WooCommerce
 * Version: 1.0.0
 */

// Auto-inyectar widget en páginas de producto
add_action('woocommerce_after_single_product_summary', 'clip_comparador_widget');

function clip_comparador_widget() {
    $api_key = get_option('clip_comparador_api_key');
    if (!$api_key) return;

    echo '<div id="clip-widget" data-api-key="' . esc_attr($api_key) . '"></div>';
    echo '<script src="https://clipcomparadorv2-production.up.railway.app/static/widget.js"></script>';
}
```

---

## 📝 Checklist de Progreso

### Setup Inicial (Ya completado)
- [x] Crear modelo `WooCommerceIntegration`
- [x] Crear cliente API `WooCommerceAPIClient`
- [x] Crear blueprint `woocommerce_setup.py`
- [x] Crear template `connect_form.html`
- [x] Documentación completa

### Testing Local (Hacer ahora)
- [ ] Crear migración de base de datos
- [ ] Aplicar migración
- [ ] Registrar blueprint en app
- [ ] Crear tienda WooCommerce de prueba
- [ ] Generar Consumer Keys
- [ ] Probar conexión con cURL/Postman
- [ ] Probar formulario de conexión
- [ ] Verificar integración guardada en DB

### Desarrollo Completo (Siguiente fase)
- [ ] Implementar WooCommerceSyncService
- [ ] Mapeo de productos WooCommerce → Sistema
- [ ] Procesamiento de imágenes + embeddings
- [ ] Webhook receiver con validación HMAC
- [ ] Registro automático de webhooks
- [ ] Plugin WordPress básico
- [ ] Documentación de instalación para usuarios

---

## 🆘 Troubleshooting

### Error: "Cannot connect to WooCommerce API"
- ✅ Verificar que la URL sea correcta (http/https)
- ✅ Verificar que Consumer Key/Secret sean válidos
- ✅ Verificar permalinks habilitados en WordPress
- ✅ Verificar que WooCommerce esté instalado y activo

### Error: "Table woocommerce_integrations doesn't exist"
- ✅ Ejecutar migración: `python manage.py db upgrade`
- ✅ Verificar tabla creada con local_db_tool.py

### Error: "Blueprint not found"
- ✅ Verificar import en app/__init__.py
- ✅ Verificar que el archivo woocommerce_setup.py esté en blueprints/

---

## 📞 Siguiente Reunión

Temas a discutir:
1. Validar que el setup básico funcione correctamente
2. Priorizar features (¿sync completo primero o webhooks?)
3. Decidir estrategia de widget (¿plugin obligatorio o shortcode manual?)
4. Definir modelo de negocio (¿gratis o premium?)

---

**Última actualización**: 14 de Enero de 2026
**Estado**: 🟢 Listo para testing inicial
