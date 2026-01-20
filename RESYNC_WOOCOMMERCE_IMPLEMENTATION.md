# Re-sincronización WooCommerce - Implementación

## Descripción
Botón "Re-sincronizar" en admin que reutiliza la rutina de sincronización inicial (creación) sin afectar el cliente ni integración.

## Estrategia
- **Mantiene**: Cliente (ID, API key), Integración WooCommerce
- **Borra**: Productos, categorías e imágenes
- **Ejecuta**: La misma función `start_full_sync()` de la creación
- **Resultado**: Catálogo consistente, fresh, sin código duplicado

## Cambios implementados

### 1. Backend: Nuevo endpoint resync
**Archivo**: `clip_admin_backend/app/blueprints/woocommerce_setup.py`
- **Ruta**: `POST /woocommerce/resync/<client_id>`
- **Body JSON**:
  ```json
  {
    "delete_mode": "soft"  // "soft" o "hard"
  }
  ```
- **Respuesta**: 202 (Accepted - iniciado en background)
  ```json
  {
    "success": true,
    "message": "Resincronización iniciada en segundo plano",
    "client_id": "...",
    "delete_mode": "soft"
  }
  ```
- **Flujo**:
  1. Valida cliente e integración WooCommerce
  2. Inicia thread background (no bloquea UI)
  3. Borra productos/categorías/imágenes (soft o hard)
  4. Ejecuta `start_full_sync()` igual que la creación
  5. Genera embeddings y webhooks

### 2. Ruta en admin de cliente
**Archivo**: `clip_admin_backend/app/blueprints/clients.py`
- **Ruta**: `GET /clients/<client_id>/woocommerce-admin`
- **Función**: `woocommerce_admin()`
- **Renderiza**: Template `woocommerce/admin_panel.html` con estadísticas

### 3. Template UI
**Archivo**: `clip_admin_backend/app/templates/woocommerce/admin_panel.html`
- Información de tienda (URL, versión WC/WP, moneda)
- Estadísticas: productos, categorías, imágenes, procesadas
- **Botón principal**: "Re-sincronizar Ahora" con confirmación
- **Botón secundario**: "Vista Previa" (placeholder para dry-run futuro)
- Progress bar simulada (0-100%)
- Resultado final con conteos

### 4. Link en panel de cliente
**Archivo**: `clip_admin_backend/app/templates/clients/view.html`
- Agregado link "Panel WooCommerce" en sección de integración WooCommerce
- Visible solo para clientes con integración WooCommerce activa

## Cómo usar

### Desde admin
1. Ir a "Clientes" → seleccionar cliente WooCommerce
2. Hacer click en botón "Panel WooCommerce"
3. En nuevo panel, click en "Re-sincronizar Ahora"
4. Confirmar en diálogo
5. Esperar progreso (simula 0-100% mientras backend procesa)
6. Refrescar página para ver cambios

### Desde código
```python
POST /woocommerce/resync/client-id-aqui
{
  "delete_mode": "soft"  # o "hard" para borrado completo
}
```

Respuesta inmediata (job enqueued en background):
```json
{
  "success": true,
  "message": "Resincronización iniciada en segundo plano",
  "client_id": "...",
  "delete_mode": "soft"
}
```

## Características

### Borrado suave (soft delete)
- Marca `is_active = False` en productos
- Los datos se mantienen en BD (auditoría)
- Menos destructivo, fácil de revertir

### Borrado duro (hard delete)
- Elimina completamente: productos, categorías, imágenes
- Limpia totalmente, comienza fresh
- Irreversible (pero dados los webhooks, se repoblaría igual)

### Background + No bloqueante
- Usa threading para no bloquear la UI
- Respuesta 202 inmediata
- Frontend simula progreso mientras backend trabaja

### Reutilización de código
- Usa `start_full_sync()` idéntico a creación
- No hay lógica duplicada
- Consistencia garantizada
- Webhooks registrados automáticamente

## Testing

Verificación de sintaxis completada:
```
✓ app/blueprints/woocommerce_setup.py
✓ app/blueprints/clients.py
✓ Template admin_panel.html
```

## Próximos pasos (opcional)

1. **Dry-run en UI**: Botón "Vista Previa" que muestra qué haría sin ejecutar
2. **Job status endpoint**: `GET /jobs/{job_id}/status` para polling preciso
3. **Webhooks test**: Disparar webhook de prueba después de resync
4. **Filtrado selectivo**: Resync solo productos/categorías (no imágenes)
5. **Horario automático**: Resync scheduled (ej: nightly)
