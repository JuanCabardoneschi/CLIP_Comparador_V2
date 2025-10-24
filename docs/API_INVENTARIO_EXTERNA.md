# API Externa de Inventario - Documentación

## 🔐 Autenticación

Todos los endpoints requieren autenticación con API Key del cliente.

**Header requerido:**
```
X-API-Key: clip_xxxxxxxxxxxxxxxxxxxx
```

Obtén tu API Key desde el panel de administración en "Mi API Key".

---

## 📦 Endpoints Disponibles

### 1. Reducir Stock (POST)

**Endpoint:** `/api/external/inventory/reduce-stock`

**Descripción:** Reduce el stock de un producto (útil para registrar ventas externas).

**Request Body:**
```json
{
  "product_id": "uuid-del-producto",  // O usar "sku" en su lugar
  "quantity": 1,
  "reason": "Venta online #12345"  // Opcional
}
```

**Request Body (con SKU):**
```json
{
  "sku": "PROD-001",
  "quantity": 2,
  "reason": "Venta POS #67890"
}
```

**Response (Éxito - 200):**
```json
{
  "success": true,
  "message": "Stock reducido correctamente",
  "product_id": "uuid",
  "product_name": "Camisa Azul",
  "sku": "PROD-001",
  "old_stock": 10,
  "new_stock": 9,
  "quantity_reduced": 1,
  "reason": "Venta online #12345"
}
```

**Response (Stock Insuficiente - 400):**
```json
{
  "success": false,
  "error": "Stock insuficiente",
  "product_id": "uuid",
  "product_name": "Camisa Azul",
  "requested_quantity": 5,
  "available_stock": 2
}
```

**Response (Producto No Encontrado - 404):**
```json
{
  "success": false,
  "error": "Producto no encontrado",
  "product_id": "uuid",
  "sku": "PROD-001"
}
```

---

### 2. Consultar Stock (GET)

**Endpoint:** `/api/external/inventory/check-stock`

**Descripción:** Consulta el stock actual de un producto.

**Query Parameters:**
- `product_id=uuid` (O `sku=PROD-001`)

**Ejemplo:**
```
GET /api/external/inventory/check-stock?sku=PROD-001
```

**Response (200):**
```json
{
  "success": true,
  "product_id": "uuid",
  "product_name": "Camisa Azul",
  "sku": "PROD-001",
  "stock": 10,
  "is_available": true,
  "price": 29.99
}
```

---

### 3. Consulta Masiva de Stock (POST)

**Endpoint:** `/api/external/inventory/bulk-check-stock`

**Descripción:** Consulta el stock de múltiples productos en una sola llamada.

**Request Body:**
```json
{
  "products": [
    {"product_id": "uuid1"},
    {"sku": "PROD-001"},
    {"sku": "PROD-002"}
  ]
}
```

**Response (200):**
```json
{
  "success": true,
  "total_requested": 3,
  "results": [
    {
      "product_id": "uuid1",
      "product_name": "Producto 1",
      "sku": "SKU-001",
      "stock": 10,
      "is_available": true,
      "price": 29.99
    },
    {
      "product_id": "uuid2",
      "product_name": "Producto 2",
      "sku": "PROD-001",
      "stock": 0,
      "is_available": false,
      "price": 19.99
    },
    {
      "sku": "PROD-002",
      "error": "Producto no encontrado"
    }
  ]
}
```

---

## 💡 Ejemplos de Uso

### JavaScript (Fetch API)
```javascript
// Reducir stock después de una venta
async function registrarVenta(sku, cantidad) {
  const response = await fetch('https://tu-dominio.railway.app/api/external/inventory/reduce-stock', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'clip_tu_api_key_aqui'
    },
    body: JSON.stringify({
      sku: sku,
      quantity: cantidad,
      reason: 'Venta online #' + Date.now()
    })
  });

  const data = await response.json();

  if (data.success) {
    console.log(`Stock reducido: ${data.old_stock} → ${data.new_stock}`);
  } else {
    console.error('Error:', data.error);
  }
}

// Consultar stock antes de mostrar producto
async function verificarDisponibilidad(sku) {
  const response = await fetch(
    `https://tu-dominio.railway.app/api/external/inventory/check-stock?sku=${sku}`,
    {
      headers: {
        'X-API-Key': 'clip_tu_api_key_aqui'
      }
    }
  );

  const data = await response.json();
  return data.is_available;
}
```

### Python (Requests)
```python
import requests

API_KEY = "clip_tu_api_key_aqui"
BASE_URL = "https://tu-dominio.railway.app/api/external/inventory"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Reducir stock
response = requests.post(
    f"{BASE_URL}/reduce-stock",
    headers=headers,
    json={
        "sku": "PROD-001",
        "quantity": 1,
        "reason": "Venta POS"
    }
)

result = response.json()
if result["success"]:
    print(f"Stock actualizado: {result['new_stock']}")
else:
    print(f"Error: {result['error']}")
```

### cURL
```bash
# Reducir stock
curl -X POST https://tu-dominio.railway.app/api/external/inventory/reduce-stock \
  -H "X-API-Key: clip_tu_api_key_aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "PROD-001",
    "quantity": 1,
    "reason": "Venta online"
  }'

# Consultar stock
curl "https://tu-dominio.railway.app/api/external/inventory/check-stock?sku=PROD-001" \
  -H "X-API-Key: clip_tu_api_key_aqui"
```

---

## 🔒 Códigos de Estado HTTP

- **200 OK**: Operación exitosa
- **400 Bad Request**: Parámetros inválidos o stock insuficiente
- **401 Unauthorized**: API Key no proporcionada
- **403 Forbidden**: API Key inválida o cliente inactivo
- **404 Not Found**: Producto no encontrado
- **500 Internal Server Error**: Error del servidor

---

## ⚠️ Consideraciones Importantes

1. **Validación de Stock**: El sistema NO permite stock negativo. Si intentas reducir más unidades de las disponibles, recibirás un error 400.

2. **Identificadores**: Puedes usar `product_id` (UUID) o `sku` (código de producto) indistintamente.

3. **Rate Limiting**: Actualmente no hay límite de requests, pero se recomienda no exceder 100 requests/minuto.

4. **Sincronización**: Los cambios son inmediatos y se reflejan en el panel de administración en tiempo real.

5. **Seguridad**: NUNCA expongas tu API Key en código del lado del cliente (frontend). Usa siempre desde tu backend/servidor.

---

## 📞 Soporte

Si tienes dudas sobre la integración, contacta a soporte técnico.
