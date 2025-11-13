# 📊 Database Schema Reference - CLIP Comparador V2

> **Referencia rápida para consultas SQL y debugging**
> Última actualización: 10 Nov 2025

---

## 🗂️ Tablas Principales

### 1️⃣ **clients** - Clientes del sistema multi-tenant
```sql
-- Columnas principales:
- id (UUID, PK)
- name (VARCHAR)
- api_key (VARCHAR, UNIQUE)
- category_confidence_threshold (FLOAT, default: 0.70)
- product_similarity_threshold (FLOAT, default: 0.30)
- active (BOOLEAN, default: TRUE)
- created_at, updated_at (TIMESTAMP)
```

### 2️⃣ **categories** - Categorías de productos por cliente
```sql
-- Columnas principales:
- id (UUID, PK)
- client_id (UUID, FK -> clients.id)
- name (VARCHAR)
- description (TEXT)
- active (BOOLEAN, default: TRUE)
- centroid_embedding (TEXT) -- JSON array con centroid CLIP
- created_at, updated_at (TIMESTAMP)
```

### 3️⃣ **products** - Productos del catálogo
```sql
-- Columnas principales:
- id (UUID, PK)
- client_id (UUID, FK -> clients.id)
- category_id (UUID, FK -> categories.id)
- sku (VARCHAR, UNIQUE per client)
- name (VARCHAR)
- description (TEXT)
- price (FLOAT)
- stock (INTEGER, default: 0)
- active (BOOLEAN, default: TRUE)
- attributes (JSONB) -- Atributos dinámicos
- created_at, updated_at (TIMESTAMP)
```

### 4️⃣ **images** - Imágenes de productos
```sql
-- Columnas principales:
- id (UUID, PK)
- product_id (UUID, FK -> products.id)
- cloudinary_public_id (VARCHAR)
- cloudinary_version (VARCHAR)
- cloudinary_format (VARCHAR)
- width, height (INTEGER)
- is_primary (BOOLEAN, default: FALSE)
- embedding (TEXT) -- JSON array con embedding CLIP
- created_at, updated_at (TIMESTAMP)

-- Propiedades calculadas (Python):
- display_url: URL completa de Cloudinary
- thumbnail_url: URL del thumbnail (150x150)
```

<!-- Se removieron secciones de variantes/entrenamiento obsoletas -->

### 7️⃣ **product_attribute_config** - Configuración de atributos dinámicos
```sql
-- Columnas principales:
- id (UUID, PK)
- client_id (UUID, FK -> clients.id)
- category_id (UUID, FK -> categories.id)
- attribute_key (VARCHAR)
- display_name (VARCHAR)
- attribute_type (VARCHAR) -- 'text', 'number', 'list'
- is_required (BOOLEAN, default: FALSE)
- is_filterable (BOOLEAN, default: FALSE)
- sort_order (INTEGER)
- options (JSONB) -- Para tipo 'list'
- created_at, updated_at (TIMESTAMP)
```

### 8️⃣ **color_mappings** - Mapeo de colores estándar por cliente
```sql
-- Columnas principales:
- id (UUID, PK)
- client_id (UUID, FK -> clients.id)
- original_color (VARCHAR) -- Color original del cliente
- standard_color (VARCHAR) -- Color estándar del sistema
- hex_value (VARCHAR) -- Valor hexadecimal
- created_at, updated_at (TIMESTAMP)
```

### 9️⃣ **search_logs** - Logs de búsquedas para analytics
```sql
-- Columnas principales:
- id (UUID, PK)
- client_id (UUID, FK -> clients.id)
- search_type (VARCHAR) -- 'image', 'text'
- query_text (TEXT)
- categories_detected (JSONB)
- results_count (INTEGER)
- response_time_ms (INTEGER)
- created_at (TIMESTAMP)
```

### 🔟 **users** - Usuarios del panel admin
```sql
-- Columnas principales:
- id (UUID, PK)
- username (VARCHAR, UNIQUE)
- email (VARCHAR, UNIQUE)
- password_hash (VARCHAR)
- is_active (BOOLEAN, default: TRUE)
- created_at, updated_at (TIMESTAMP)
```

---

## 🔗 Relaciones Clave

```
clients (1) ──────< (N) categories
clients (1) ──────< (N) products
clients (1) ──────< (N) product_attribute_config
clients (1) ──────< (N) color_mappings

categories (1) ──────< (N) products
categories (1) ──────< (N) product_attribute_config

products (1) ──────< (N) images
```

---

## 🎯 Consultas Útiles

<!-- Consultas de variantes eliminadas -->

### Productos sin stock
```sql
SELECT
    sku,
    name,
    category_id,
    stock
FROM products
WHERE client_id = 'CLIENT_UUID_AQUI'
AND stock = 0;
```

<!-- Consultas de training events eliminadas -->

### Verificar embeddings de productos
```sql
SELECT
    p.sku,
    p.name,
    i.id as image_id,
    CASE
        WHEN i.embedding IS NULL THEN 'NULL'
        WHEN i.embedding = '' THEN 'EMPTY'
        ELSE 'LENGTH=' || LENGTH(i.embedding)
    END as embedding_status
FROM products p
LEFT JOIN images i ON i.product_id = p.id
WHERE p.client_id = 'CLIENT_UUID_AQUI'
ORDER BY p.created_at DESC
LIMIT 10;
```

---

## 📝 Notas Importantes

1. **UUIDs**: Todos los IDs son UUIDs (v4) para aislamiento multi-tenant
2. **Embeddings**: Almacenados como TEXT con JSON arrays `[0.123, -0.456, ...]`
<!-- Nota sobre centroides/variants eliminada -->
4. **Cloudinary**: Imágenes NO se almacenan en BD, solo referencias
5. **JSONB**: `attributes` y `options` usan JSONB para flexibilidad

---

## 🛠️ Herramientas de BD

### Local Development
```bash
# Consulta SQL directa
python local_db_tool.py sql -e "SELECT * FROM clients LIMIT 5"

# Ver conteos de todas las tablas
python local_db_tool.py counts

# Ejecutar archivo SQL
python local_db_tool.py sql -f script.sql --yes
```

### Railway Production
```bash
# Consulta SQL en producción
python railway_db_tool.py sql -e "SELECT * FROM clients LIMIT 5"

# Ver conteos de producción
python railway_db_tool.py counts
```

---

## ⚡ Acceso Rápido a Modelos

```python
# En scripts Python:
from app.models import (
    Client,
    Category,
    Product,
    Image,
    ClientCategoryVariant,
    TrainingEvent,
    ProductAttributeConfig,
    ColorMapping,
    SearchLog,
    User
)
```

---

**📌 Mantener este documento actualizado al crear nuevas tablas o relaciones.**
