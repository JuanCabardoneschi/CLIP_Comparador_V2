# 📋 Guía: Crear Cliente - SuperAdmin Panel

> **Actualización:** SuperAdmin ahora puede crear clientes con 3 tipos de integración:
> - **Standalone** (sin integración)
> - **TiendaNube** (con integración automática)
> - **WooCommerce** (con integración automática)

---

## 📖 Visión General

El formulario de creación de cliente en SuperAdmin es ahora **dinámico y adaptativo**. Cuando seleccionas un tipo de integración, el formulario automáticamente muestra los campos necesarios para esa integración.

```
┌─────────────────────────────────────────────────┐
│  CREAR NUEVO CLIENTE (SuperAdmin)               │
├─────────────────────────────────────────────────┤
│                                                 │
│  Información del Cliente:                       │
│  ├─ Nombre de la Empresa * ........................
│  ├─ Email de Contacto * ........................
│  ├─ Industria/Rubro ............................
│  └─ Tipo de Integración * ......................
│                                                 │
│  [Si Standalone]                               │
│  └─ (Sin campos adicionales)                    │
│                                                 │
│  [Si TiendaNube]                                │
│  ├─ URL de la Tienda * .........................
│  ├─ Token de Autenticación * ...................
│  └─ [Probar Conexión] ← Validación AJAX        │
│                                                 │
│  [Si WooCommerce]                               │
│  ├─ URL de la Tienda * .........................
│  ├─ Consumer Key * .............................
│  ├─ Consumer Secret * ...........................
│  └─ [Probar Conexión] ← Validación AJAX        │
│                                                 │
│  Usuario Administrador:                         │
│  ├─ Nombre Completo * .........................
│  ├─ Email de Login * ...........................
│  ├─ Contraseña * ...............................
│  └─ Confirmar Contraseña * .....................
│                                                 │
│                 [Cancelar] [Crear Cliente]     │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Flujo de Creación de Cliente

### 1. **Acceder al Formulario**
- SuperAdmin → Dashboard → Clientes → "Nuevo Cliente"
- O: SuperAdmin → Clientes (listado) → "Nuevo Cliente"

### 2. **Completar Información del Cliente**
```
┌─────────────────────┬──────────────────────────┐
│ Campo               │ Valor Ejemplo            │
├─────────────────────┼──────────────────────────┤
│ Nombre              │ Goody Shop SRL           │
│ Email               │ contacto@goodyshop.com   │
│ Industria           │ Moda y Accesorios        │
│ Tipo de Integración │ WooCommerce [dropdown]   │
└─────────────────────┴──────────────────────────┘
```

### 3. **Seleccionar Tipo de Integración**

El dropdown tiene 3 opciones:

#### **Opción A: Standalone**
- ✅ Sin integración externa
- ✅ Carga manual de productos
- ✅ Control total del catálogo
- ⏭️ Sin campos adicionales necesarios

#### **Opción B: TiendaNube**
- ✅ Sincronización automática de productos
- ✅ Webhooks en tiempo real
- ✅ Actualización de stock automática
- ⏭️ Requiere: URL + Token

#### **Opción C: WooCommerce**
- ✅ Sincronización automática de productos
- ✅ Webhooks en tiempo real
- ✅ Actualización de stock automática
- ⏭️ Requiere: URL + Consumer Key + Consumer Secret

### 4. **Completar Credenciales de Integración (si aplica)**

#### **Si seleccionaste TiendaNube:**

```
┌────────────────────────────────────────┐
│ CONFIGURACIÓN TIENDANUBE               │
├────────────────────────────────────────┤
│                                        │
│ URL de la Tienda TiendaNube *         │
│ ┌────────────────────────────────────┐ │
│ │ https://mitienda.mitiendanube.com  │ │
│ └────────────────────────────────────┘ │
│ Forma: https://nomdre.mitiendanube.com │
│                                        │
│ Token de Autenticación *              │
│ ┌────────────────────────────────────┐ │
│ │ ••••••••••••••••••••••••••••••••   │ │
│ └────────────────────────────────────┘ │
│ (Campo protegido - contraseña)         │
│                                        │
│ [Probar Conexión TiendaNube]           │
│ ↓ (Si hace clic sin completar)         │
│ ⚠️  "Por favor completa todos los..."  │
│                                        │
│ ↓ (Si prueba con credenciales inválidas)
│ ❌ "Error en TiendaNube: ..."          │
│                                        │
│ ↓ (Si credenciales son válidas)        │
│ ✅ "Conexión exitosa con TiendaNube..." │
│                                        │
└────────────────────────────────────────┘
```

#### **Si seleccionaste WooCommerce:**

```
┌─────────────────────────────────────────────┐
│ CONFIGURACIÓN WOOCOMMERCE                   │
├─────────────────────────────────────────────┤
│                                             │
│ URL de la Tienda *                         │
│ ┌─────────────────────────────────────────┐ │
│ │ https://goodyshop.com                   │ │
│ └─────────────────────────────────────────┘ │
│ Forma: https://mitienda.com                │
│                                             │
│ Consumer Key *                              │
│ ┌─────────────────────────────────────────┐ │
│ │ ••••••••••••••••••••••••••••••••••   │ │
│ └─────────────────────────────────────────┘ │
│ (Campo protegido - contraseña)              │
│                                             │
│ Consumer Secret *                           │
│ ┌─────────────────────────────────────────┐ │
│ │ ••••••••••••••••••••••••••••••••••   │ │
│ └─────────────────────────────────────────┘ │
│ (Campo protegido - contraseña)              │
│                                             │
│ [Probar Conexión WooCommerce]               │
│ ↓ (Si prueba con credenciales válidas)     │
│ ✅ "Conexión exitosa con WooCommerce..."   │
│                                             │
└─────────────────────────────────────────────┘
```

### 5. **Probar Conexión (Opcional pero Recomendado)**

Después de completar las credenciales de integración:

1. Haz clic en **"Probar Conexión [TiendaNube/WooCommerce]"**
2. El botón cambiará a "Probando..." durante 2-5 segundos
3. Verás un mensaje de éxito o error:
   - ✅ **Éxito**: "Conexión exitosa con [plataforma]: [store info]"
   - ❌ **Error**: "Error al validar: [razón específica]"

**¿Qué valida el test?**
- ✅ URL correcta y accesible
- ✅ Credenciales válidas
- ✅ Permisos API suficientes
- ✅ Conexión HTTPS funcional (WooCommerce)

### 6. **Crear Usuario Administrador**

```
┌──────────────────────────────────────────┐
│ USUARIO ADMINISTRADOR                    │
├──────────────────────────────────────────┤
│                                          │
│ Nombre Completo *                       │
│ ┌──────────────────────────────────────┐│
│ │ Juan Pérez Martínez                  ││
│ └──────────────────────────────────────┘│
│                                          │
│ Email de Login *                         │
│ ┌──────────────────────────────────────┐│
│ │ juan.perez@goodyshop.com             ││
│ └──────────────────────────────────────┘│
│ (Debe ser único en el sistema)           │
│                                          │
│ Contraseña *                             │
│ ┌──────────────────────────────────────┐│
│ │ ••••••••••                           ││
│ └──────────────────────────────────────┘│
│ (Mínimo 6 caracteres)                    │
│                                          │
│ Confirmar Contraseña *                  │
│ ┌──────────────────────────────────────┐│
│ │ ••••••••••                           ││
│ └──────────────────────────────────────┘│
│                                          │
│ ⚠️  IMPORTANTE: Esta contraseña no se   │
│    mostrará nuevamente                   │
│                                          │
└──────────────────────────────────────────┘
```

### 7. **Crear Cliente**

Haz clic en **"Crear Cliente y Usuario"**

**El sistema realizará:**
1. ✅ Validar todos los campos obligatorios
2. ✅ Verificar que no exista cliente con ese email
3. ✅ Verificar que no exista usuario con ese email de login
4. ✅ Generar automáticamente:
   - UUID único para el cliente
   - API Key segura (ej: `clip_abc123def456...`)
   - Slug único (ej: `goody-shop`)
5. ✅ Crear cliente en BD con tipo de integración
6. ✅ Crear usuario administrador del cliente
7. ✅ Guardar credenciales de integración (encriptadas si aplica)
8. ✅ Redirigir a página de detalles del cliente

---

## 💾 Datos Guardados en la BD

### **Tabla: `clients`**
```sql
{
  id:                    "550e8400-e29b-41d4-a716-446655440000",
  name:                  "Goody Shop SRL",
  slug:                  "goody-shop",
  email:                 "contacto@goodyshop.com",
  industry:              "fashion",
  api_key:               "clip_abc123def456...",

  -- INTEGRACIÓN
  integration_type:      "woocommerce",  -- o "standalone", "tiendanube"
  integration_config:    {
    "store_url": "https://goodyshop.com",
    "consumer_key": "[ENCRIPTADO]",      -- Solo para WooCommerce
    "consumer_secret": "[ENCRIPTADO]"    -- Solo para WooCommerce
  },

  is_active:             true,
  created_at:            "2026-01-14 15:30:00",
  updated_at:            "2026-01-14 15:30:00"
}
```

### **Tabla: `users`**
```sql
{
  id:                    "550e8400-e29b-41d4-a716-446655440001",
  email:                 "juan.perez@goodyshop.com",
  full_name:             "Juan Pérez Martínez",
  password_hash:         "[HASH BCRYPT]",

  -- RELACIONES
  client_id:             "550e8400-e29b-41d4-a716-446655440000",  -- FK a clients
  role:                  "STORE_ADMIN",

  is_active:             true,
  created_at:            "2026-01-14 15:30:00",
  updated_at:            "2026-01-14 15:30:00"
}
```

### **Tabla: `woocommerce_integrations` (si es WooCommerce)**
```sql
{
  id:                           "550e8400-e29b-41d4-a716-446655440002",
  client_id:                    "550e8400-e29b-41d4-a716-446655440000",
  store_url:                    "https://goodyshop.com",
  consumer_key_encrypted:       "[AES-128 ENCRIPTADO]",
  consumer_secret_encrypted:    "[AES-128 ENCRIPTADO]",

  -- METADATA
  store_name:                   "Goody Shop",
  wc_version:                   "8.5.0",
  is_active:                    true,

  -- SINCRONIZACIÓN
  last_sync_products:           "2026-01-14 15:35:00",
  last_sync_categories:         "2026-01-14 15:35:00",
  sync_status:                  "idle",

  created_at:                   "2026-01-14 15:30:00",
  updated_at:                   "2026-01-14 15:30:00"
}
```

---

## 📊 Panel de Control Después de Crear

Después de crear el cliente, el SuperAdmin ve:

```
┌───────────────────────────────────────────────────────┐
│ DETALLES DEL CLIENTE: Goody Shop SRL                  │
├───────────────────────────────────────────────────────┤
│                                                       │
│ Información del Cliente:                             │
│ ├─ Nombre: Goody Shop SRL                            │
│ ├─ Email: contacto@goodyshop.com                     │
│ ├─ Slug: goody-shop                                  │
│ ├─ Industria: Moda y Accesorios                      │
│ ├─ Estado: ✅ Activo                                 │
│ ├─ Registrado: 14/01/2026                            │
│ │                                                     │
│ ├─ API Key: clip_abc123def456...                     │
│ │         [👁️ Mostrar] [📋 Copiar] [🔄 Regenerar]   │
│ │                                                     │
│ └─ Tipo de Integración: 🔗 WooCommerce               │
│    └─ URL: https://goodyshop.com                     │
│                                                       │
│ Usuarios (1):                                         │
│ ├─ Juan Pérez Martínez (juan.perez@goodyshop.com)   │
│ │  └─ Rol: STORE_ADMIN                               │
│ │                                                     │
│ └─ [+ Agregar usuario]                               │
│                                                       │
│ Acciones:                                             │
│ ├─ [✏️  Editar]                                       │
│ ├─ [🗑️  Eliminar]                                     │
│ ├─ [🔗 Integración WooCommerce]                       │
│ │  └─ [🔄 Re-sincronizar]                            │
│ │  └─ [⚙️  Configuración]                             │
│ └─ [📊 Productos y Categorías]                       │
│                                                       │
└───────────────────────────────────────────────────────┘
```

---

## 🔐 Seguridad

### **Credenciales Encriptadas**

Para **TiendaNube** y **WooCommerce**, las credenciales se guardan **encriptadas**:

```python
# En el backend:
from app.models.woocommerce_integration import WooCommerceIntegration

# Al guardar:
integration = WooCommerceIntegration(
    client_id=client.id,
    store_url="https://goodyshop.com"
)
integration.set_consumer_key("ck_...")        # Encripta antes de guardar
integration.set_consumer_secret("cs_...")    # Encripta antes de guardar
db.session.add(integration)
db.session.commit()

# En la BD:
SELECT consumer_key_encrypted FROM woocommerce_integrations
-- Resultado: "gAAAAABlu...encrypted_bytes..."

# Al usar:
consumer_key = integration.get_consumer_key()  # Desencripta del almacenamiento
# Se descarta inmediatamente después de usar
```

### **Niveles de Seguridad**

1. **En Tránsito**: HTTPS (TLS 1.2+)
2. **En Formulario**: Campo tipo password (puntos)
3. **En BD**: Fernet AES-128 encriptado
4. **En Memoria**: Solo cuando se usa, luego descartado
5. **En Log**: Nunca se loguean credenciales

---

## 🧪 Ejemplo: Crear Cliente WooCommerce

### **Paso 1: Acceder a Crear Cliente**
```
SuperAdmin → Clientes → Nuevo Cliente
```

### **Paso 2: Completar Información Básica**
```
Nombre: Goody Shop SRL
Email: contacto@goodyshop.com
Industria: Moda y Accesorios
Tipo de Integración: [dropdown] → Seleccionar "WooCommerce"
```

### **Paso 3: Formulario se Adapta**
```
(Las secciones de TiendaNube desaparecen)
(La sección de WooCommerce aparece automáticamente)
```

### **Paso 4: Completar Credenciales WooCommerce**
```
URL de la Tienda: https://goodyshop.com
Consumer Key: ck_0123456789abcdef...
Consumer Secret: cs_abcdef0123456789...
```

### **Paso 5: Probar Conexión (Recomendado)**
```
Haz clic en "Probar Conexión WooCommerce"
↓
[Probando...]
↓
✅ "Conexión exitosa con WooCommerce: Goody Shop"
```

### **Paso 6: Crear Usuario Administrador**
```
Nombre Completo: Juan Pérez Martínez
Email de Login: juan.perez@goodyshop.com
Contraseña: [mínimo 6 caracteres]
Confirmar Contraseña: [igual a la anterior]
```

### **Paso 7: Crear Cliente**
```
Haz clic en "Crear Cliente y Usuario"
↓
[Validando...]
↓
✅ Múltiples mensajes de éxito:
   - "✅ Cliente 'Goody Shop SRL' creado exitosamente"
   - "🔑 API Key: clip_abc123def456..."
   - "👤 Usuario Administrador creado:"
   - "📧 Email: juan.perez@goodyshop.com"
   - "🔐 Contraseña: [mostrada una sola vez]"
   - "🔗 Integración WooCommerce: https://goodyshop.com"
```

### **Paso 8: Ver Detalles del Cliente**
```
(Redirigido automáticamente a página de detalles)
↓
Se muestra todo lo creado:
- Cliente con API Key
- Usuario administrador
- Tipo de integración: WooCommerce
- URL de la tienda
```

---

## ❌ Errores Comunes

### **Error: "Ya existe un cliente con ese email"**
- ✓ Usa un email único para cada cliente

### **Error: "Ya existe un usuario con ese email de login"**
- ✓ Los emails de login deben ser únicos en el sistema

### **Error: "La URL debe comenzar con http:// o https://"**
- ✗ `goodyshop.com` ← Incorrecto
- ✓ `https://goodyshop.com` ← Correcto

### **Error: "Conexión exitosa con WooCommerce" pero luego falla**
- Verificar que:
  - Consumer Key y Secret no tengan espacios en blanco
  - Permisos REST API están habilitados en WordPress
  - URL es la correcta (incluir dominio exacto)
  - Certificado SSL es válido (HTTPS)

### **Error: "Las contraseñas no coinciden"**
- ✓ Asegúrate que ambos campos sean idénticos

---

## 📚 Recursos Relacionados

- [Guía Conectar Goody Shop WooCommerce](./GUIA_CONECTAR_GOODY_SHOP.md)
- [Estructura BD WooCommerce](./ESTRUCTURA_BD_WOOCOMMERCE.md)
- [Estado de Integración WooCommerce](./ESTADO_INTEGRACION_WOOCOMMERCE.md)
- [API Inventario Externo](./API_INVENTARIO_EXTERNA.md)

---

**Última actualización:** 14 de enero de 2026
**Versión:** 2.0 (Con soporte dinámico de 3 tipos de integración)
