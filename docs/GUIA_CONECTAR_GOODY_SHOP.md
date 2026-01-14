# 🚀 Guía Rápida: Conectar Goody Shop a CLIP Comparador

## ✅ Estructuras BD Creadas

Las tablas y modelos necesarios ya están listos en Railway:

- ✅ Tabla `woocommerce_integrations` (creada)
- ✅ Modelo SQLAlchemy `WooCommerceIntegration` (actualizado)
- ✅ Blueprint `woocommerce_setup.py` (disponible)
- ✅ Cliente API `WooCommerceAPIClient` (disponible)
- ✅ Encriptación de credenciales (configurada)

---

## 📋 Datos Necesarios de Goody Shop

Para conectar la tienda, necesitas que el admin de Goody Shop genere en su panel de WooCommerce:

### Ubicación en WordPress
```
WooCommerce → Ajustes → Avanzado → REST API → Añadir Clave
```

### Información a Proporcionar

```
1. URL de la tienda
   → https://goodyshop.com.ar

2. Consumer Key (ck_...)
   → (Generada automáticamente en WP Admin)
   → Formato: 49 caracteres alfanuméricos

3. Consumer Secret (cs_...)
   → (Generada automáticamente en WP Admin)
   → Formato: 49 caracteres alfanuméricos

4. Descripción (recomendado)
   → "CLIP Comparador - Búsqueda Visual"
   → Permisos: Lectura/Escritura
```

---

## 🔧 Pasos para Generar las Claves

### En el Panel de WordPress de Goody Shop:

1. **Ir a WooCommerce**
   - Menú lateral → click en "WooCommerce"

2. **Ir a Ajustes**
   - Click en "Ajustes" (Settings)

3. **Ir a Avanzado**
   - Pestaña superior → "Avanzado" (Advanced)

4. **Ir a REST API**
   - Sub-pestaña → "REST API"

5. **Crear Clave**
   - Click en "Añadir Clave" (Add Key)

6. **Completar Formulario**
   ```
   Descripción: CLIP Comparador - Búsqueda Visual
   Usuario: (seleccionar admin de la tienda)
   Permisos: Lectura/Escritura
   ```

7. **Copiar Claves**
   ⚠️ **IMPORTANTE**: Copia ambas claves ahora, solo se muestran UNA VEZ:
   ```
   Consumer Key:    ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   Consumer Secret: cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

## 💾 Guardar Información

```
URL de Goody Shop:  https://goodyshop.com.ar
Consumer Key:       ck_xxxxxxxxxxxxx
Consumer Secret:    cs_xxxxxxxxxxxxx
```

---

## 📡 Endpoints Listos para Usar

Una vez tengas las credenciales, puedes usar estos endpoints:

### 1. Test de Conexión
```bash
POST /api/woocommerce/test-connection
Content-Type: application/json

{
  "store_url": "https://goodyshop.com.ar",
  "consumer_key": "ck_xxx...",
  "consumer_secret": "cs_xxx..."
}

# Response
{
  "success": true,
  "message": "Conexión exitosa",
  "store_info": {
    "name": "Goody Shop",
    "version": "8.5.2",
    "timezone": "America/Argentina/Buenos_Aires",
    "currency": "ARS"
  }
}
```

### 2. Guardar Integración
```bash
POST /api/woocommerce/save-integration
Content-Type: application/json
Authorization: Bearer <API_KEY_CLIENTE>

{
  "store_url": "https://goodyshop.com.ar",
  "consumer_key": "ck_xxx...",
  "consumer_secret": "cs_xxx...",
  "widget_method": "plugin"  # o "shortcode" o "manual"
}

# Response
{
  "success": true,
  "integration_id": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "message": "Integración guardada exitosamente",
  "next_steps": [
    "Sincronizar productos",
    "Instalar plugin de widget",
    "Configurar categorías"
  ]
}
```

### 3. Listar Integraciones
```bash
GET /api/woocommerce/integrations
Authorization: Bearer <API_KEY_CLIENTE>

# Response
{
  "success": true,
  "integrations": [
    {
      "id": "...",
      "store_url": "https://goodyshop.com.ar",
      "store_name": "Goody Shop",
      "is_active": true,
      "last_sync_at": "2026-01-14T15:45:00",
      "sync_status": "completed",
      "products_count": 342,
      "categories_count": 12
    }
  ]
}
```

### 4. Sincronizar Productos
```bash
POST /api/woocommerce/<integration_id>/sync
Authorization: Bearer <API_KEY_CLIENTE>

# Response
{
  "success": true,
  "sync_status": "in_progress",
  "message": "Sincronización iniciada...",
  "estimated_time": "5-10 minutos"
}
```

---

## 🔐 Seguridad: Qué Sucede con las Credenciales

### En la Base de Datos (Railway)
```
consumer_key:    "gAAAAABk1234567890...abcdef..." ← ENCRIPTADO
consumer_secret: "gAAAAABk1234567890...zyxwvu..." ← ENCRIPTADO
```

### En la API
- Las credenciales se desencriptan **en memoria**
- Se usan SOLO para hacer llamadas a WooCommerce
- **NUNCA** se devuelven en respuestas a clientes
- **NUNCA** se guardan en logs

### En Transit
```
Cliente → CLIP API (HTTPS/SSL)
          ↓
       Backend encripta credenciales
          ↓
       Base de datos (encriptadas)
          ↓
       Cuando se necesita:
       Backend desencripta → llamada a WC → descarta en memoria
```

---

## 📦 Estructura de Datos Guardada

Cuando conectes Goody Shop, se creará este registro en `woocommerce_integrations`:

```json
{
  "id": "uuid-único",
  "client_id": "uuid-cliente-goody",
  "store_url": "https://goodyshop.com.ar",
  "store_name": "Goody Shop",
  "store_email": "contacto@goodyshop.com.ar",
  "consumer_key": "ENCRIPTADO",
  "consumer_secret": "ENCRIPTADO",
  "api_version": "v3",
  "use_ssl": true,
  "webhook_ids": {},
  "widget_method": "plugin",
  "is_active": true,
  "installed_at": "2026-01-14T10:30:00",
  "last_sync_at": null,
  "sync_status": "pending",
  "sync_error": null,
  "wc_version": "8.5.2",
  "wp_version": "6.4.3",
  "timezone": "America/Argentina/Buenos_Aires",
  "currency": "ARS",
  "created_at": "2026-01-14T10:30:00",
  "updated_at": "2026-01-14T10:30:00"
}
```

---

## ✅ Checklist Antes de Conectar

- [ ] Acceder al panel de WordPress de Goody Shop
- [ ] Generar Consumer Key y Secret en WooCommerce → Settings → Advanced → REST API
- [ ] Copiar ambas claves (se muestran UNA SOLA VEZ)
- [ ] Tener la URL exacta: `https://goodyshop.com.ar`
- [ ] Probar conexión con POST a `/api/woocommerce/test-connection`
- [ ] Si todo ✅, guardar integración con POST a `/api/woocommerce/save-integration`
- [ ] Sincronizar productos con POST a `/api/woocommerce/<id>/sync`

---

## 🆘 Troubleshooting

### Error: "Invalid credentials"
```
Solución:
- Verificar que las claves se copiaron completas
- Asegurar que tengan permisos de Lectura/Escritura
- Generar nuevas claves si es necesario
```

### Error: "Store URL not accessible"
```
Solución:
- Verificar que la URL sea accesible desde internet
- Asegurar que tiene https://
- Verificar que no tenga trailing slash (/)
```

### Error: "REST API not enabled"
```
Solución:
- Ir a WooCommerce → Ajustes → Advanced
- Verificar que REST API esté habilitada
- Si no aparece la opción, actualizar WooCommerce
```

---

## 📞 Soporte

Si algo no funciona:
1. Revisar que las claves estén bien copiadas
2. Verificar los logs en: `/var/log/woocommerce_sync.log`
3. Ejecutar test con: `python test_woocommerce_connection.py`

---

**Fecha**: 14 de Enero de 2026
**Estado**: 🚀 Listo para conectar
**Próximo paso**: Obtener credenciales de Goody Shop
