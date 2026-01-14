# 🎯 SuperAdmin Panel - Cliente Dinámico con 3 Tipos de Integración

## 📊 Diagrama Visual de la Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                      SUPERADMIN PANEL                           │
│                                                                 │
│  Crear Nuevo Cliente                                            │
│  ├─ Tipo de Integración [Dropdown]                             │
│  │  ├─ Standalone       (sin integración)                      │
│  │  ├─ TiendaNube       (URL + Token)                          │
│  │  └─ WooCommerce      (URL + Consumer Key + Secret)          │
│  │                                                              │
│  └─ Formulario Dinámico                                         │
│     ├─ [Si Standalone]   → Sin campos adicionales              │
│     ├─ [Si TiendaNube]   → Campos TN + Validación AJAX         │
│     └─ [Si WooCommerce]  → Campos WC + Validación AJAX         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    VALIDACIÓN BACKEND                           │
│                                                                 │
│  POST /api/clients/validate-integration                         │
│  ├─ TiendaNube: Verificar URL + Token válidos                  │
│  ├─ WooCommerce: Verificar URL + CK + CS válidos               │
│  └─ Respuesta: { success: bool, message: string }              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                   GUARDAR EN BD                                 │
│                                                                 │
│  ✓ Tabla: clients                                               │
│    ├─ id, name, email, industry (siempre)                      │
│    ├─ integration_type (NUEVO)                                 │
│    └─ integration_config (NUEVO)                               │
│                                                                 │
│  ✓ Tabla: users (administrador)                                │
│    └─ client_id (FK)                                           │
│                                                                 │
│  ✓ Tabla: woocommerce_integrations (si WC)                     │
│    ├─ consumer_key_encrypted (AES-128)                         │
│    └─ consumer_secret_encrypted (AES-128)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flujo Interactivo Completo

### **Escenario 1: Crear Cliente Standalone**

```
┌─────────────────────────────────────────┐
│ 1. Formulario de Creación de Cliente    │
├─────────────────────────────────────────┤
│ Nombre: Mi Tienda                       │
│ Email: contacto@mitienda.com            │
│ Industria: Retail                       │
│ Tipo: [Dropdown] → Standalone           │
│                   (sin cambios visuales)│
│                                         │
│ ✓ Completa usuario admin                │
│ [Crear Cliente] ──────────────────────┐ │
└─────────────────────────────────────────┘ │
                                             │
   ┌─────────────────────────────────────┐  │
   │ 2. BD: clients table                │  │
   ├─────────────────────────────────────┤  │
   │ id: uuid                            │  │
   │ name: "Mi Tienda"                   │  │
   │ integration_type: "standalone"      │  │
   │ integration_config: {}              │  │
   │ api_key: "clip_abc123..."           │  │
   └─────────────────────────────────────┘  │
                                             │
   ┌─────────────────────────────────────┐  │
   │ 3. BD: users table                  │  │
   ├─────────────────────────────────────┤  │
   │ client_id: (FK a clients)           │  │
   │ email: "admin@mitienda.com"         │  │
   │ password_hash: bcrypt               │  │
   └─────────────────────────────────────┘  │
                                             └──► ✅ Cliente Creado
```

### **Escenario 2: Crear Cliente TiendaNube**

```
┌─────────────────────────────────────────────┐
│ 1. Formulario Dinámico                      │
├─────────────────────────────────────────────┤
│ Nombre: Goody Shop                          │
│ Email: contact@goodyshop.com                │
│ Industria: Moda                             │
│ Tipo: [Dropdown] → TiendaNube               │
│                                             │
│ [Aparecen campos TiendaNube automáticamente]
│                                             │
│ URL de Tienda: https://goodyshop.tn.com   │
│ Token: [PASSWORD FIELD]                     │
│ [Probar Conexión TiendaNube]                │
│   └──► ✅ "Conexión exitosa"                │
│                                             │
│ ✓ Completa usuario admin                    │
│ [Crear Cliente] ──────────────────────────┐ │
└─────────────────────────────────────────────┘ │
                                                 │
   ┌──────────────────────────────────────────┐ │
   │ 2. BD: clients table                     │ │
   ├──────────────────────────────────────────┤ │
   │ integration_type: "tiendanube"           │ │
   │ integration_config: {                    │ │
   │   "store_url": "https://...",            │ │
   │   "access_token": "..."                  │ │
   │ }                                        │ │
   └──────────────────────────────────────────┘ │
                                                 │
   ┌──────────────────────────────────────────┐ │
   │ 3. Webhook Setup (después del create)    │ │
   ├──────────────────────────────────────────┤ │
   │ Registrar webhooks en TiendaNube         │ │
   │ ├─ product.created                       │ │
   │ ├─ product.updated                       │ │
   │ └─ product.deleted                       │ │
   └──────────────────────────────────────────┘ │
                                                 └──► ✅ Cliente Creado
```

### **Escenario 3: Crear Cliente WooCommerce**

```
┌──────────────────────────────────────────────────┐
│ 1. Formulario Dinámico                           │
├──────────────────────────────────────────────────┤
│ Nombre: Goody Shop SRL                           │
│ Email: contacto@goodyshop.com                    │
│ Industria: Moda y Accesorios                    │
│ Tipo: [Dropdown] → WooCommerce                   │
│                                                  │
│ [Aparecen campos WooCommerce automáticamente]   │
│                                                  │
│ URL de Tienda: https://goodyshop.com           │
│ Consumer Key: [PASSWORD FIELD]                   │
│ Consumer Secret: [PASSWORD FIELD]                │
│ [Probar Conexión WooCommerce]                    │
│   ├─ Conecta a: https://goodyshop.com/wp-json  │
│   ├─ Usa: HTTP Basic Auth                       │
│   ├─ Valida: GET /wp-json/wc/v3/system/status   │
│   └──► ✅ "Conexión exitosa"                    │
│                                                  │
│ ✓ Completa usuario admin                        │
│ [Crear Cliente] ──────────────────────────────┐ │
└──────────────────────────────────────────────────┘ │
                                                      │
   ┌────────────────────────────────────────────────┐ │
   │ 2. BD: clients table                           │ │
   ├────────────────────────────────────────────────┤ │
   │ integration_type: "woocommerce"                │ │
   │ integration_config: {                          │ │
   │   "store_url": "https://goodyshop.com"         │ │
   │ }                                              │ │
   └────────────────────────────────────────────────┘ │
                                                      │
   ┌────────────────────────────────────────────────┐ │
   │ 3. BD: woocommerce_integrations table          │ │
   ├────────────────────────────────────────────────┤ │
   │ id: uuid                                       │ │
   │ client_id: (FK)                                │ │
   │ store_url: "https://goodyshop.com"             │ │
   │ consumer_key_encrypted: [AES-128]              │ │
   │ consumer_secret_encrypted: [AES-128]           │ │
   │ is_active: true                                │ │
   │ last_sync_products: null (pendiente)           │ │
   │ (23 columnas más de metadatos)                 │ │
   └────────────────────────────────────────────────┘ │
                                                      │
   ┌────────────────────────────────────────────────┐ │
   │ 4. Webhook Setup (después del create)          │ │
   ├────────────────────────────────────────────────┤ │
   │ Registrar webhooks en WooCommerce              │ │
   │ ├─ product.created                             │ │
   │ ├─ product.updated                             │ │
   │ └─ product.deleted                             │ │
   │ (Incluir: X-WC-Webhook-Signature para validar) │ │
   └────────────────────────────────────────────────┘ │
                                                      │
   ┌────────────────────────────────────────────────┐ │
   │ 5. Iniciar Sincronización (asincrónico)        │ │
   ├────────────────────────────────────────────────┤ │
   │ Queue Job: sync_woocommerce_products           │ │
   │ ├─ Descargar categorías                        │ │
   │ ├─ Descargar productos                         │ │
   │ ├─ Generar embeddings CLIP                     │ │
   │ └─ Calcular centroides                         │ │
   └────────────────────────────────────────────────┘ │
                                                      └──► ✅ Cliente Creado
```

---

## 📋 Comparativa de Tipos de Integración

```
┌────────────────┬──────────────┬──────────────┬────────────────┐
│ Característica │  Standalone  │  TiendaNube  │ WooCommerce    │
├────────────────┼──────────────┼──────────────┼────────────────┤
│ Sincronización │      ❌      │      ✅      │       ✅       │
│ Webhooks       │      ❌      │      ✅      │       ✅       │
│ Actualización  │    Manual    │   Automática │   Automática   │
│ Credenciales   │      -       │  URL + Token │  URL + CK + CS │
│ Complejidad    │    Baja      │    Media     │     Media      │
│ Mantenimiento  │    Alto      │    Bajo      │     Bajo       │
│ Costo Servidor │    Bajo      │   Bajo-Medio │   Bajo-Medio   │
│ Setup Inicial  │    1 min     │    5 min     │    10 min      │
└────────────────┴──────────────┴──────────────┴────────────────┘
```

---

## 🔐 Seguridad - Flujo de Credenciales

```
┌─────────────────────────────────────────────────────────────┐
│ 1. USUARIO INGRESA CREDENCIALES                             │
│    WooCommerce Consumer Key y Secret                        │
│    [En campo type="password" - se muestra como puntos]      │
└─────────────────────────────────────────────────────────────┘
                            ↓ (HTTPS)
┌─────────────────────────────────────────────────────────────┐
│ 2. BACKEND RECIBE DATOS EN MEMORIA                          │
│    - request.form.get("wc_consumer_key")                    │
│    - Datos en RAM (nunca en log)                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. ENCRIPTACIÓN (Fernet AES-128)                            │
│    key = ENV["TOKEN_ENCRYPTION_KEY"]                       │
│    cipher_key = Fernet(key)                                 │
│    encrypted = cipher_key.encrypt(consumer_key.encode())    │
│                                                             │
│    Resultado: gAAAAABlu9VX3F...muy_largo...                │
└─────────────────────────────────────────────────────────────┘
                            ↓ (INSERT en BD)
┌─────────────────────────────────────────────────────────────┐
│ 4. ALMACENAMIENTO EN BD (Encriptado)                        │
│    INSERT INTO woocommerce_integrations                     │
│    (consumer_key_encrypted, consumer_secret_encrypted)      │
│    VALUES ('gAAAAAB...', 'gAAAAAB...')                      │
│                                                             │
│    Si alguien accede a la BD, ve: [ENCRYPTED]              │
└─────────────────────────────────────────────────────────────┘
                            ↓ (Cuando se necesita usar)
┌─────────────────────────────────────────────────────────────┐
│ 5. DESENCRIPTACIÓN EN MEMORIA                               │
│    key = ENV["TOKEN_ENCRYPTION_KEY"]                       │
│    cipher_key = Fernet(key)                                 │
│    plain = cipher_key.decrypt(encrypted_bytes)              │
│    consumer_key = plain.decode()                            │
│                                                             │
│    Temporal en RAM - se descarta inmediatamente             │
└─────────────────────────────────────────────────────────────┘
                            ↓ (Usar en API)
┌─────────────────────────────────────────────────────────────┐
│ 6. API REQUEST A WOOCOMMERCE                                │
│    GET /wp-json/wc/v3/products                              │
│    Headers: Authorization: Basic [base64(ck:cs)]            │
│    (HTTPS - encriptado en tránsito)                         │
└─────────────────────────────────────────────────────────────┘
                            ↓ (Respuesta)
┌─────────────────────────────────────────────────────────────┐
│ 7. DESCARTE DE CREDENCIALES                                 │
│    La variable `consumer_key` se descarta                   │
│    Python GC recolecta memoria                              │
│    ✅ Credencial nunca quedó en log o archivo              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 UI/UX - Mockup de Formulario

```
┌──────────────────────────────────────────────────────────────────┐
│ ✎  CREAR NUEVO CLIENTE                              ← ← Volver   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────┐  ┌──────────────────┐  │
│  │ Información del Cliente            │  │ Información      │  │
│  ├────────────────────────────────────┤  ├──────────────────┤  │
│  │                                    │  │ Incluye:         │  │
│  │ 🏢 Nombre de la Empresa *          │  │ • Panel dedicado │  │
│  │ ┌──────────────────────────────────┐ │ • API keys       │  │
│  │ │ Goody Shop SRL                   │ │ • Catálogo       │  │
│  │ └──────────────────────────────────┘ │ • Analytics      │  │
│  │                                    │  │ • Búsqueda CLIP  │  │
│  │ 📧 Email de Contacto *             │  │                  │  │
│  │ ┌──────────────────────────────────┐ │ 📌 Slug:         │  │
│  │ │ contacto@goodyshop.com           │ │ ┌───────────────┐│  │
│  │ └──────────────────────────────────┘ │ │ goody-shop    ││  │
│  │                                    │  │ └───────────────┘│  │
│  │ 💼 Industria/Rubro                 │  │                  │  │
│  │ ┌──────────────────────────────────┐ │ Tipos:           │  │
│  │ │ [Moda y Accesorios         ▼]   │ │ • ☐ Standalone  │  │
│  │ └──────────────────────────────────┘ │ • 🔗 TiendaNube │  │
│  │                                    │  │ • 📦 WooCommerce │  │
│  │ 🔗 Tipo de Integración *           │  │                  │  │
│  │ ┌──────────────────────────────────┐ │  │
│  │ │ [WooCommerce               ▼]   │ │  │
│  │ └──────────────────────────────────┘ │  │
│  │  Sincronización automática de      │  │  │
│  │  productos desde WordPress          │  │  │
│  │                                    │  │  │
│  ├────────────────────────────────────┤  │  │
│  │ ⚙️  CONFIGURACIÓN WOOCOMMERCE      │  │  │
│  ├────────────────────────────────────┤  │  │
│  │                                    │  │  │
│  │ 🌐 URL de la Tienda *              │  │  │
│  │ ┌──────────────────────────────────┐ │  │
│  │ │ https://goodyshop.com            │ │  │
│  │ └──────────────────────────────────┘ │  │
│  │                                    │  │  │
│  │ 🔑 Consumer Key *                  │  │  │
│  │ ┌──────────────────────────────────┐ │  │
│  │ │ •••••••••••••••••••••••••••••   │ │  │
│  │ └──────────────────────────────────┘ │  │
│  │                                    │  │  │
│  │ 🔑 Consumer Secret *               │  │  │
│  │ ┌──────────────────────────────────┐ │  │
│  │ │ •••••••••••••••••••••••••••••   │ │  │
│  │ └──────────────────────────────────┘ │  │
│  │                                    │  │  │
│  │ [✓ Probar Conexión WooCommerce]    │  │  │
│  │ ✅ "Conexión exitosa con..."      │  │  │
│  │                                    │  │  │
│  ├────────────────────────────────────┤  │  │
│  │ 👤 Usuario Administrador           │  │  │
│  ├────────────────────────────────────┤  │  │
│  │                                    │  │  │
│  │ 👤 Nombre Completo *               │  │  │
│  │ ┌──────────────────────────────────┐ │  │
│  │ │ Juan Pérez Martínez              │ │  │
│  │ └──────────────────────────────────┘ │  │
│  │                                    │  │  │
│  │ 📧 Email de Login *                │  │  │
│  │ ┌──────────────────────────────────┐ │  │
│  │ │ juan.perez@goodyshop.com         │ │  │
│  │ └──────────────────────────────────┘ │  │
│  │                                    │  │  │
│  │ 🔐 Contraseña *                    │  │  │
│  │ ┌──────────────────────────────────┐ │  │
│  │ │ •••••••••                        │ │  │
│  │ └──────────────────────────────────┘ │  │
│  │                                    │  │  │
│  │ 🔐 Confirmar Contraseña *          │  │  │
│  │ ┌──────────────────────────────────┐ │  │
│  │ │ •••••••••                        │ │  │
│  │ └──────────────────────────────────┘ │  │
│  │                                    │  │  │
│  │ [Cancelar]  [✓ Crear Cliente]      │  │  │
│  │                                    │  └──────────────────┘
│  └────────────────────────────────────┘
│
└──────────────────────────────────────────────────────────────────┘
```

---

## 📈 Flujo de Datos

```
USUARIO SuperAdmin
       │
       ▼
┌─────────────────────────────────────┐
│ Interfaz Web (create.html)          │
│ ├─ Formulario dinámico              │
│ ├─ Validación JavaScript            │
│ └─ AJAX calls                       │
└─────────────────────────────────────┘
       │
       ├──► POST /clients/create
       │    ├─ Validación backend
       │    ├─ Guardar en BD
       │    └─ Redirect /clients/{id}
       │
       ├──► POST /api/clients/validate-integration
       │    ├─ Validar TN o WC
       │    └─ JSON response
       │
       ▼
┌─────────────────────────────────────┐
│ Flask Backend (clients.py)          │
│ ├─ Route /clients/create            │
│ ├─ Route /api/clients/validate...   │
│ └─ Lógica de validación             │
└─────────────────────────────────────┘
       │
       ├──► SQLAlchemy ORM
       │
       ▼
┌─────────────────────────────────────┐
│ PostgreSQL (Railway)                │
│ ├─ INSERT INTO clients              │
│ ├─ INSERT INTO users                │
│ ├─ INSERT INTO woocommerce_...      │
│ └─ COMMIT                           │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Encriptación (Fernet AES-128)       │
│ └─ Consumer Key + Secret             │
└─────────────────────────────────────┘
```

---

## ✨ Características Destacadas

### **1. Formulario Dinámico**
```javascript
// JavaScript
const integrationType = document.getElementById('integration_type').value;

if (integrationType === 'woocommerce') {
    document.getElementById('woocommerce_section').style.display = 'block';
} else {
    document.getElementById('woocommerce_section').style.display = 'none';
}
```

### **2. Validación AJAX**
```javascript
fetch('/api/clients/validate-integration', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        integration_type: 'woocommerce',
        store_url: 'https://goodyshop.com',
        consumer_key: 'ck_...',
        consumer_secret: 'cs_...'
    })
})
```

### **3. Encriptación Backend**
```python
from cryptography.fernet import Fernet

key = os.environ['TOKEN_ENCRYPTION_KEY']
cipher = Fernet(key)
encrypted = cipher.encrypt(consumer_key.encode())
```

### **4. Manejo de Errores**
```python
try:
    # Validar credenciales
    api_client = WooCommerceAPIClient(url, key, secret)
    result = api_client.test_connection()

    if result['success']:
        return jsonify({'success': True, 'message': '✅ ...'})
    else:
        return jsonify({'success': False, 'message': '❌ ...'}), 400
except Exception as e:
    return jsonify({'success': False, 'message': f'❌ Error: {str(e)}'}), 500
```

---

## 🎓 Cómo Usar (Para Usuarios)

### **Crear Cliente Standalone**
1. Dashboard → Clientes → Nuevo Cliente
2. Completa: Nombre, Email, Industria
3. Tipo: Standalone
4. Crea usuario admin
5. ¡Listo!

### **Crear Cliente TiendaNube**
1. Dashboard → Clientes → Nuevo Cliente
2. Completa: Nombre, Email, Industria
3. Tipo: TiendaNube
4. URL + Token de TiendaNube
5. [Probar Conexión]
6. Crea usuario admin
7. ¡Listo!

### **Crear Cliente WooCommerce**
1. Dashboard → Clientes → Nuevo Cliente
2. Completa: Nombre, Email, Industria
3. Tipo: WooCommerce
4. URL, Consumer Key, Consumer Secret
5. [Probar Conexión]
6. Crea usuario admin
7. ¡Listo!

---

## 📊 Estadísticas

| Métrica | Valor |
|---------|-------|
| Líneas de código modificadas | ~450 |
| Nuevas rutas AJAX | 1 |
| Campos dinámicos agregados | 3 (URL, Key, Secret) |
| Botones de validación | 2 (TN, WC) |
| Tablas BD modificadas | 3 (clients, woocommerce_integrations, users) |
| Documentos creados | 2 (Guía + Resumen) |
| Commits realizados | 4 |

---

**Última actualización:** 14 de enero de 2026
**Versión:** 2.0 - SuperAdmin Dinámico
**Estado:** ✅ Producción
