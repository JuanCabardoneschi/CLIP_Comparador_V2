# 🗄️ Estructura de Base de Datos - WooCommerce Integration

## ✅ Resumen de Cambios Realizados

Se ha creado la estructura completa en Railway para almacenar integraciones con WooCommerce de forma segura y escalable.

---

## 📊 Tabla: `woocommerce_integrations`

### Descripción
Tabla para almacenar integraciones con tiendas WooCommerce. Cada registro representa una tienda conectada a través de la REST API.

### Estructura

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| **id** | UUID | NO | Identificador único (PK) |
| **client_id** | UUID | NO | Referencia al cliente (FK → clients.id) |
| **store_url** | VARCHAR(500) | NO | URL única de la tienda (UNIQUE) |
| **store_name** | VARCHAR(255) | SÍ | Nombre de la tienda |
| **store_email** | VARCHAR(255) | SÍ | Email de contacto de la tienda |
| **consumer_key** | TEXT | NO | 🔒 Consumer Key encriptado (ck_...) |
| **consumer_secret** | TEXT | NO | 🔒 Consumer Secret encriptado (cs_...) |
| **api_version** | VARCHAR(10) | NO | Versión de API (default: 'v3') |
| **use_ssl** | BOOLEAN | NO | ¿Usar HTTPS? (default: TRUE) |
| **webhook_ids** | JSONB | SÍ | Registro de webhooks registrados |
| **webhook_secret** | VARCHAR(100) | SÍ | Secret para validar webhooks |
| **widget_method** | VARCHAR(50) | SÍ | Método instalación: 'plugin', 'shortcode', 'manual' |
| **is_active** | BOOLEAN | NO | ¿Integración activa? (default: TRUE) |
| **installed_at** | TIMESTAMP | NO | Fecha de instalación |
| **uninstalled_at** | TIMESTAMP | SÍ | Fecha de desinstalación |
| **last_sync_at** | TIMESTAMP | SÍ | Última sincronización de productos |
| **sync_status** | VARCHAR(50) | SÍ | Estado: pending, in_progress, completed, error |
| **sync_error** | TEXT | SÍ | Mensaje de error si la sincronización falló |
| **wc_version** | VARCHAR(20) | SÍ | Versión de WooCommerce instalada |
| **wp_version** | VARCHAR(20) | SÍ | Versión de WordPress |
| **timezone** | VARCHAR(50) | SÍ | Zona horaria de la tienda |
| **currency** | VARCHAR(10) | SÍ | Moneda de la tienda (ej: ARS, USD) |
| **created_at** | TIMESTAMP | NO | Fecha de creación |
| **updated_at** | TIMESTAMP | NO | Última actualización |

### Restricciones

#### Primary Key
- `id` (UUID)

#### Foreign Keys
- `client_id` → `clients.id` (ON DELETE CASCADE)
  - Esto garantiza que si un cliente se elimina, todas sus integraciones WC se eliminan automáticamente

#### Unique
- `store_url` - Cada tienda solo puede estar conectada una vez

### Índices

```
✅ woocommerce_integrations_pkey             (PRIMARY KEY)
✅ woocommerce_integrations_store_url_key    (UNIQUE)
✅ idx_woocommerce_integrations_client_id    (FK lookup)
✅ idx_woocommerce_integrations_store_url    (Búsqueda por URL)
✅ idx_woocommerce_integrations_is_active    (Filtro activos/inactivos)
```

---

## 🔒 Seguridad: Encriptación de Credenciales

### Consumer Keys Encriptados
Las claves `consumer_key` y `consumer_secret` se **SIEMPRE** almacenan encriptadas usando Fernet (AES-128).

```python
# Ejemplo de uso en el código:

# ✅ CORRECTO - Encriptar antes de guardar
integration = WooCommerceIntegration(...)
integration.set_consumer_key(ck)      # Encripta automáticamente
integration.set_consumer_secret(cs)   # Encripta automáticamente
db.session.add(integration)
db.session.commit()

# ✅ CORRECTO - Desencriptar cuando se necesita
ck = integration.get_consumer_key()    # Desencripta automáticamente
cs = integration.get_consumer_secret() # Desencripta automáticamente

# ❌ NUNCA hacer esto
integration.consumer_key = ck  # ¡NO! Guardaría en texto plano
```

### Clave de Encriptación
- **Variable de Entorno**: `TOKEN_ENCRYPTION_KEY`
- **Ubicación en Railway**: Variables de entorno del servicio
- **Fallback**: Se genera dinámicamente (NO usar en producción)

---

## 📋 Relación con Otras Tablas

### Diagrama de Relaciones

```
┌─────────────────┐
│ clients         │
│ ─────────────── │
│ id (UUID) [PK]  │
│ name            │
│ email           │
│ ...             │
└────────┬────────┘
         │
         │ 1:N (un cliente puede tener
         │      múltiples tiendas WC)
         │
         ▼
┌──────────────────────────────────┐
│ woocommerce_integrations         │
│ ────────────────────────────────  │
│ id (UUID) [PK]                   │
│ client_id (UUID) [FK] ◄──────────┤ Vincula al cliente
│ store_url (UNIQUE)               │
│ consumer_key (ENCRYPTED)         │
│ consumer_secret (ENCRYPTED)      │
│ ...                              │
└──────────────────────────────────┘
         │
         │ 1:N (una tienda WC tiene
         │      múltiples productos)
         │
         ▼
┌──────────────────────┐
│ products             │
│ ──────────────────── │
│ id (UUID) [PK]       │
│ client_id (UUID) [FK]│
│ name                 │
│ external_id          │ ← ID del producto en WC
│ ...                  │
└──────────────────────┘
```

---

## 🔄 Flujo de Integración

### 1. Admin de Tienda WooCommerce Crea API Key

En WordPress (WooCommerce → Ajustes → Avanzado → REST API):
```
Consumer Key: ck_xxxxxxxxxxxxxxxxxxxxx (49 caracteres)
Consumer Secret: cs_xxxxxxxxxxxxxxxxxxxxx (49 caracteres)
```

### 2. Admin conecta la tienda en CLIP Panel

```
POST /api/woocommerce/connect
{
    "store_url": "https://goodyshop.com.ar",
    "consumer_key": "ck_xxx...",
    "consumer_secret": "cs_xxx..."
}
```

### 3. Backend valida y guarda

```python
# app/blueprints/woocommerce_setup.py

integration = WooCommerceIntegration(
    client_id=current_user.client_id,
    store_url="https://goodyshop.com.ar",
    store_name="Goody Shop"
)

# ✅ Encriptación automática
integration.set_consumer_key("ck_xxx...")
integration.set_consumer_secret("cs_xxx...")

db.session.add(integration)
db.session.commit()
```

### 4. Base de datos (Railway)

Valores en la BD:
```
consumer_key:    "gAAAAABk1234567890...abcdef..." (encriptado)
consumer_secret: "gAAAAABk1234567890...zyxwvu..." (encriptado)
```

### 5. Cuando se necesita usar las credenciales

```python
# Desencriptar automáticamente
ck = integration.get_consumer_key()
cs = integration.get_consumer_secret()

# Usar para hacer llamadas a la API de WooCommerce
wc_client = WooCommerceAPIClient(
    store_url=integration.store_url,
    consumer_key=ck,
    consumer_secret=cs
)
```

---

## 📝 Ejemplo de Registro Completo

```json
{
  "id": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "client_id": "11111111-2222-3333-4444-555555555555",
  "store_url": "https://goodyshop.com.ar",
  "store_name": "Goody Shop",
  "store_email": "contacto@goodyshop.com.ar",
  "consumer_key": "gAAAAABk1234567890...",  // ENCRIPTADO
  "consumer_secret": "gAAAAABk0987654321...", // ENCRIPTADO
  "api_version": "v3",
  "use_ssl": true,
  "webhook_ids": {
    "product.created": 123,
    "product.updated": 124,
    "product.deleted": 125
  },
  "webhook_secret": "webhook_secret_123abc",
  "widget_method": "plugin",
  "is_active": true,
  "installed_at": "2026-01-14T10:30:00",
  "uninstalled_at": null,
  "last_sync_at": "2026-01-14T15:45:00",
  "sync_status": "completed",
  "sync_error": null,
  "wc_version": "8.5.2",
  "wp_version": "6.4.3",
  "timezone": "America/Argentina/Buenos_Aires",
  "currency": "ARS",
  "created_at": "2026-01-14T10:30:00",
  "updated_at": "2026-01-14T15:45:00"
}
```

---

## ✅ Checklist de Verificación

- [x] Tabla `woocommerce_integrations` creada en Railway
- [x] Primary Key configurado (id: UUID)
- [x] Foreign Key a `clients.id` con ON DELETE CASCADE
- [x] Constraint UNIQUE en `store_url`
- [x] Índices para búsquedas rápidas (client_id, store_url, is_active)
- [x] Columnas de encriptación (consumer_key, consumer_secret) como TEXT
- [x] JSONB para webhooks_ids (flexible para webhooks futuros)
- [x] Columnas de auditoría (created_at, updated_at)
- [x] Columnas de estado de sincronización (sync_status, sync_error, last_sync_at)
- [x] Campos opcionales (SÍ) para metadatos (wc_version, wp_version, timezone, currency)
- [x] Modelo SQLAlchemy actualizado a UUID
- [x] Modelo exportado en `app/models/__init__.py`

---

## 🚀 Próximos Pasos

1. **Completar blueprints**:
   - ✅ `woocommerce_setup.py` - Endpoints de conexión
   - ⏳ `woocommerce_webhooks.py` - Receptor de webhooks
   - ⏳ `woocommerce_admin.py` - Panel de administración

2. **Implementar servicios**:
   - ✅ `WooCommerceAPIClient` - Cliente REST
   - ⏳ `WooCommerceSyncService` - Sincronización de datos

3. **Probar con cliente real**:
   - [ ] Conectar tienda Goody Shop
   - [ ] Sincronizar productos
   - [ ] Validar encriptación

---

## 🛠️ Comandos Útiles

### Verificar estructura en Railway

```bash
# Ver toda la tabla
python railway_db_tool.py sql -e "SELECT * FROM woocommerce_integrations LIMIT 1;"

# Ver estructura de columnas
python railway_db_tool.py sql -e "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'woocommerce_integrations';"

# Ver índices
python railway_db_tool.py sql -e "SELECT indexname FROM pg_indexes WHERE tablename = 'woocommerce_integrations';"

# Ver restricciones
python railway_db_tool.py sql -e "SELECT constraint_name FROM information_schema.table_constraints WHERE table_name = 'woocommerce_integrations';"
```

### Eliminar tabla (si es necesario)

```bash
# ⚠️ SOLO EN DESARROLLO
python railway_db_tool.py sql -e "DROP TABLE IF EXISTS woocommerce_integrations CASCADE;" --yes
```

---

**Fecha**: 14 de Enero de 2026
**Estado**: ✅ Completado
**Versión**: 1.0
