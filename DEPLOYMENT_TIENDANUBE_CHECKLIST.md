# Checklist de Deployment - Integración Tiendanube

## 📋 Pre-Deployment

### 1. Variable de Entorno Critical
```bash
TOKEN_ENCRYPTION_KEY=IXBEpZ56PjbIpKLP6CH8Ijjc14nWLJzuI1XjDV4-6ic=
```
**⚠️ IMPORTANTE**: Configurar esta variable en Railway ANTES de deployar.

**Pasos en Railway**:
1. Ir a proyecto Railway
2. Seleccionar servicio `clip_admin_backend`
3. Variables → Raw Editor
4. Agregar: `TOKEN_ENCRYPTION_KEY=IXBEpZ56PjbIpKLP6CH8Ijjc14nWLJzuI1XjDV4-6ic=`
5. Guardar cambios

### 2. Verificar Variables Tiendanube Existentes
Asegurar que estas variables ya existen en Railway:
- `TIENDANUBE_CLIENT_ID`
- `TIENDANUBE_CLIENT_SECRET`
- `TIENDANUBE_REDIRECT_URI` (debe apuntar a Railway: `https://clip-comparador-v2-production.up.railway.app/tiendanube/oauth/callback`)

## 🚀 Deployment Steps

### 1. Verificar Código Local
```powershell
# Activar venv
& C:/Personal/CLIP_Comparador_V2/venv/Scripts/Activate.ps1

# Verificar que Flask carga sin errores
cd clip_admin_backend
python app.py
```
**Verificar**:
- ✓ Blueprint tiendanube_webhooks registrado
- ✓ Sin errores de importación
- ✓ App inicia correctamente

### 2. Commit y Push
```powershell
git add .
git commit -m "feat: Implementar webhooks Tiendanube con HMAC verification"
git push origin main
```

### 3. Deploy a Railway
Railway debería auto-deployar al detectar el push.

Alternativamente, usar:
```powershell
.\quick_deploy.ps1
```

### 4. Verificar Deployment
1. Ir a Railway Dashboard
2. Verificar que el build fue exitoso
3. Verificar logs del contenedor:
   - ✓ Blueprint tiendanube_webhooks registrado
   - ✓ Sin errores de cryptography
   - ✓ App corriendo en puerto asignado

## 🧪 Prueba Completa

### Pre-requisitos
- App deployada en Railway
- Variable TOKEN_ENCRYPTION_KEY configurada
- testclip.mitiendanube.com sin la app instalada (desinstalar si está)

### Flujo de Prueba End-to-End

#### 1. Instalación
1. Ir a Tiendanube Partner Dashboard
2. Ir a tu aplicación
3. Hacer clic en "Instalar en tienda de prueba"
4. Seleccionar testclip.mitiendanube.com
5. Autorizar permisos

**Verificar**:
- ✓ Callback exitoso: `https://clip-comparador-v2-production.up.railway.app/tiendanube/oauth/callback?code=...`
- ✓ Cliente creado en BD con:
  - `integration_type = 'tiendanube'`
  - `is_read_only = True`
  - `api_key` generado
- ✓ TiendanubeIntegration creado con:
  - `access_token` encriptado
  - `webhook_ids` con 8 webhooks registrados
  - `script_id` o `fallback_menu_link` configurado
- ✓ Sync inicial disparado (puede tomar minutos)

#### 2. Verificar Sync Inicial
```sql
-- Conectar a Railway DB
python railway_db_tool.py sql -e "
SELECT
    i.store_id,
    i.store_name,
    i.sync_status,
    i.last_sync_at,
    c.name as client_name,
    (SELECT COUNT(*) FROM categories WHERE client_id = c.id) as cats,
    (SELECT COUNT(*) FROM products WHERE client_id = c.id) as prods,
    (SELECT COUNT(*) FROM images WHERE product_id IN (SELECT id FROM products WHERE client_id = c.id)) as imgs
FROM tiendanube_integrations i
JOIN clients c ON i.client_id = c.id
WHERE i.is_active = TRUE
" --yes
```

**Verificar**:
- ✓ `sync_status = 'completed'`
- ✓ Categorías importadas (> 0)
- ✓ Productos importados (> 0)
- ✓ Imágenes importadas (> 0)

#### 3. Verificar Embeddings
```sql
python railway_db_tool.py sql -e "
SELECT
    COUNT(*) as total_images,
    COUNT(CASE WHEN clip_embedding IS NOT NULL THEN 1 END) as with_embeddings,
    COUNT(CASE WHEN is_processed = TRUE THEN 1 END) as processed
FROM images
WHERE product_id IN (
    SELECT id FROM products
    WHERE client_id = (
        SELECT client_id FROM tiendanube_integrations WHERE is_active = TRUE LIMIT 1
    )
)
" --yes
```

**Verificar**:
- ✓ `with_embeddings > 0`
- ✓ `processed = total_images` (o cercano)

#### 4. Verificar Centroides
```sql
python railway_db_tool.py sql -e "
SELECT
    name,
    (CASE WHEN centroid_embedding IS NOT NULL THEN 'SÍ' ELSE 'NO' END) as tiene_centroide
FROM categories
WHERE client_id = (
    SELECT client_id FROM tiendanube_integrations WHERE is_active = TRUE LIMIT 1
)
ORDER BY name
" --yes
```

**Verificar**:
- ✓ Categorías con productos tienen centroide

#### 5. Probar Webhooks

**5.1. Crear Producto en Tiendanube**
1. Ir a testclip.mitiendanube.com/admin/products
2. Crear nuevo producto con imagen
3. Guardar

**Verificar en logs Railway**:
```
Webhook recibido: product/created para product_id=xxx
Producto created: [nombre] (id=xxx)
```

**Verificar en BD**:
```sql
python railway_db_tool.py sql -e "
SELECT name, external_id, sync_status, last_sync_at
FROM products
WHERE client_id = (SELECT client_id FROM tiendanube_integrations WHERE is_active = TRUE LIMIT 1)
ORDER BY last_sync_at DESC
LIMIT 5
" --yes
```

**5.2. Actualizar Producto**
1. Editar el producto recién creado
2. Cambiar nombre o agregar imagen
3. Guardar

**Verificar**:
- ✓ Webhook `product/updated` recibido
- ✓ Producto actualizado en BD
- ✓ Nuevas imágenes procesadas

**5.3. Eliminar Producto**
1. Eliminar el producto de prueba
2. Verificar webhook

**Verificar**:
```sql
python railway_db_tool.py sql -e "
SELECT name, external_id, sync_status, is_active
FROM products
WHERE external_id = 'xxx'
" --yes
```
- ✓ `is_active = FALSE`
- ✓ `sync_status = 'deleted'`

#### 6. Verificar Widget/Enlace
1. Ir a testclip.mitiendanube.com (storefront)
2. Buscar el widget o enlace de búsqueda visual

**Si script_id existe**:
- ✓ Widget debe aparecer en la tienda
- ✓ Abrir widget y verificar que funciona

**Si fallback_menu_link**:
- ✓ Enlace en menú de navegación
- ✓ Clic debe abrir modal de búsqueda

#### 7. Probar API de Búsqueda
```bash
# Obtener API key del cliente Tiendanube
API_KEY=$(python railway_db_tool.py sql -e "
SELECT api_key FROM clients
WHERE id = (SELECT client_id FROM tiendanube_integrations WHERE is_active = TRUE LIMIT 1)
" --yes | tail -n 1)

# Probar búsqueda visual
curl -X POST https://clip-comparador-v2-production.up.railway.app/api/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    "top_k": 5
  }'
```

**Verificar respuesta**:
```json
{
  "success": true,
  "results": [
    {
      "product_id": "...",
      "name": "...",
      "price": 123.45,
      "similarity": 0.98,
      "image_url": "...",
      "category": "..."
    }
  ]
}
```

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError: cryptography"
**Solución**: Verificar que `requirements.txt` incluye `cryptography==41.0.7`

### Error: "Invalid signature" en webhooks
**Solución**:
1. Verificar que `TIENDANUBE_CLIENT_SECRET` en Railway es correcto
2. Revisar logs para ver firma recibida vs esperada
3. Verificar que el body se lee como bytes: `request.data`

### Error: "Integration not found" en webhook
**Solución**:
1. Verificar que `X-Linked-Nube-Info-Id` header está presente
2. Verificar que existe `TiendanubeIntegration` con ese `store_id` y `is_active = TRUE`

### Sync se queda en "in_progress"
**Solución**:
1. Revisar logs de Railway para ver errores
2. Verificar que el `access_token` es válido
3. Probar manualmente: `python railway_db_tool.py sql -e "UPDATE tiendanube_integrations SET sync_status = 'pending' WHERE sync_status = 'in_progress'" --yes`

### Productos sin embeddings
**Solución**:
1. Verificar que las imágenes tienen `base64_data` poblado
2. Revisar logs del procesamiento CLIP
3. Re-procesar: Llamar a `/api/admin/tiendanube/integrations/<id>/sync` con `full_sync=true`

## 📊 Verificación Final

Lista de comprobación completa:

- [ ] Variable TOKEN_ENCRYPTION_KEY configurada en Railway
- [ ] App deployada sin errores
- [ ] Blueprint tiendanube_webhooks registrado
- [ ] Instalación OAuth exitosa
- [ ] Cliente y TiendanubeIntegration creados
- [ ] Webhooks registrados (8 eventos)
- [ ] Widget/enlace creado
- [ ] Sync inicial completado
- [ ] Categorías importadas con centroides
- [ ] Productos importados con imágenes Base64
- [ ] Embeddings CLIP generados
- [ ] Webhook product/created funciona
- [ ] Webhook product/updated funciona
- [ ] Webhook product/deleted funciona
- [ ] API de búsqueda responde correctamente
- [ ] Widget/enlace funciona en storefront

## 🎉 Success Criteria

La integración está completa cuando:
1. ✅ OAuth flow completo funciona
2. ✅ Sync inicial importa todos los datos
3. ✅ Embeddings y centroides se generan
4. ✅ Webhooks actualizan datos en tiempo real
5. ✅ Widget o enlace está visible en tienda
6. ✅ Búsqueda visual retorna resultados relevantes

## 📝 Notas

- **GDPR**: Webhooks GDPR están implementados pero requieren proceso manual adicional
- **Rate Limiting**: Tiendanube tiene límite de 2 req/s, el código ya maneja esto
- **Fallback**: Si el plan no soporta scripts, se crea enlace en menú automáticamente
- **Reinstalación**: Cada desinstalación/reinstalación crea un NUEVO cliente
