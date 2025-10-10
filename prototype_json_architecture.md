# 🎯 CLIP Comparador V2 - Arquitectura JSON Prototipo

## 📋 ESTRUCTURA DE ARCHIVOS JSON

```
clip_admin_backend/
├── data/
│   ├── clients.json           # Clientes del sistema
│   ├── users.json            # Usuarios y autenticación
│   ├── categories.json       # Categorías por cliente
│   ├── products.json         # Catálogo de productos
│   ├── images.json           # Metadatos de imágenes
│   ├── api_keys.json         # Claves de API
│   └── search_logs.json      # Logs de búsquedas
└── services/
    ├── json_storage.py       # Servicio de almacenamiento JSON
    ├── data_manager.py       # Manager para operaciones CRUD
    └── migration_service.py  # Migración futura a PostgreSQL
```

## 🔧 IMPLEMENTACIÓN TÉCNICA

### 1. Servicio de Almacenamiento JSON

```python
# services/json_storage.py
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import threading

class JSONStorage:
    """Almacenamiento JSON thread-safe con auto-guardado"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.cache = {}
        self.lock = threading.RLock()
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Crear directorio de datos si no existe"""
        os.makedirs(self.data_dir, exist_ok=True)

    def _load_file(self, filename: str) -> Dict:
        """Cargar archivo JSON con cache"""
        if filename not in self.cache:
            filepath = os.path.join(self.data_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.cache[filename] = json.load(f)
            else:
                self.cache[filename] = {"data": [], "meta": {"version": 1}}
        return self.cache[filename]

    def _save_file(self, filename: str):
        """Guardar archivo JSON"""
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.cache[filename], f, indent=2, ensure_ascii=False)

    def get_all(self, table: str) -> List[Dict]:
        """Obtener todos los registros de una tabla"""
        with self.lock:
            filename = f"{table}.json"
            data = self._load_file(filename)
            return data["data"]

    def get_by_id(self, table: str, record_id: str) -> Optional[Dict]:
        """Obtener registro por ID"""
        records = self.get_all(table)
        return next((r for r in records if r["id"] == record_id), None)

    def filter_by(self, table: str, **kwargs) -> List[Dict]:
        """Filtrar registros por criterios"""
        records = self.get_all(table)
        result = []
        for record in records:
            match = True
            for key, value in kwargs.items():
                if record.get(key) != value:
                    match = False
                    break
            if match:
                result.append(record)
        return result

    def create(self, table: str, data: Dict) -> Dict:
        """Crear nuevo registro"""
        with self.lock:
            if "id" not in data:
                data["id"] = str(uuid.uuid4())
            if "created_at" not in data:
                data["created_at"] = datetime.utcnow().isoformat()

            filename = f"{table}.json"
            file_data = self._load_file(filename)
            file_data["data"].append(data)
            self._save_file(filename)
            return data

    def update(self, table: str, record_id: str, data: Dict) -> Optional[Dict]:
        """Actualizar registro existente"""
        with self.lock:
            filename = f"{table}.json"
            file_data = self._load_file(filename)

            for i, record in enumerate(file_data["data"]):
                if record["id"] == record_id:
                    data["updated_at"] = datetime.utcnow().isoformat()
                    file_data["data"][i].update(data)
                    self._save_file(filename)
                    return file_data["data"][i]
            return None

    def delete(self, table: str, record_id: str) -> bool:
        """Eliminar registro"""
        with self.lock:
            filename = f"{table}.json"
            file_data = self._load_file(filename)

            for i, record in enumerate(file_data["data"]):
                if record["id"] == record_id:
                    del file_data["data"][i]
                    self._save_file(filename)
                    return True
            return False

# Instancia global
storage = JSONStorage()
```

### 2. Adaptador de Modelos

```python
# services/data_manager.py
from .json_storage import storage
from typing import Dict, List, Optional

class BaseModel:
    """Modelo base para compatibilidad con SQLAlchemy"""
    table_name = ""

    def __init__(self, **kwargs):
        self.data = kwargs
        if "id" not in self.data:
            self.data["id"] = None

    @property
    def id(self):
        return self.data.get("id")

    def save(self):
        """Guardar o actualizar registro"""
        if self.id:
            result = storage.update(self.table_name, self.id, self.data)
        else:
            result = storage.create(self.table_name, self.data)
        self.data = result
        return self

    def delete(self):
        """Eliminar registro"""
        if self.id:
            return storage.delete(self.table_name, self.id)
        return False

    @classmethod
    def get_by_id(cls, record_id: str):
        """Buscar por ID"""
        data = storage.get_by_id(cls.table_name, record_id)
        return cls(**data) if data else None

    @classmethod
    def filter_by(cls, **kwargs):
        """Filtrar registros"""
        records = storage.filter_by(cls.table_name, **kwargs)
        return [cls(**record) for record in records]

    @classmethod
    def all(cls):
        """Obtener todos los registros"""
        records = storage.get_all(cls.table_name)
        return [cls(**record) for record in records]

class Client(BaseModel):
    table_name = "clients"

    @property
    def name(self):
        return self.data.get("name")

    @property
    def email(self):
        return self.data.get("email")

    @property
    def api_key(self):
        return self.data.get("api_key")

class Product(BaseModel):
    table_name = "products"

    @property
    def name(self):
        return self.data.get("name")

    @property
    def client_id(self):
        return self.data.get("client_id")

    def get_client(self):
        return Client.get_by_id(self.client_id)

class Image(BaseModel):
    table_name = "images"

    @property
    def filename(self):
        return self.data.get("filename")

    @property
    def product_id(self):
        return self.data.get("product_id")
```

### 3. Búsqueda Simplificada

```python
# services/search_service.py
import re
from typing import List, Dict
from .data_manager import Product, Image, Client

class SearchService:
    """Servicio de búsqueda simplificado para JSON"""

    def search_products(self, client_id: str, query: str, limit: int = 10) -> List[Dict]:
        """Búsqueda básica por texto en productos"""
        products = Product.filter_by(client_id=client_id, is_active=True)

        # Búsqueda por similitud de texto
        matches = []
        query_lower = query.lower()

        for product in products:
            score = 0
            name = product.data.get("name", "").lower()
            description = product.data.get("description", "").lower()
            tags = product.data.get("tags", "").lower()

            # Scoring básico
            if query_lower in name:
                score += 10
            if query_lower in description:
                score += 5
            if query_lower in tags:
                score += 3

            # Palabras parciales
            for word in query_lower.split():
                if word in name:
                    score += 2
                if word in description:
                    score += 1

            if score > 0:
                # Obtener imagen principal
                images = Image.filter_by(product_id=product.id, is_primary=True)
                image_url = images[0].data.get("cloudinary_url") if images else None

                matches.append({
                    "product_id": product.id,
                    "name": product.data.get("name"),
                    "description": product.data.get("description"),
                    "price": product.data.get("price"),
                    "image_url": image_url,
                    "score": score,
                    "similarity": min(score / 10, 1.0)  # Simular similitud
                })

        # Ordenar por score y limitar
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]

    def search_by_category(self, client_id: str, category_name: str) -> List[Dict]:
        """Búsqueda por categoría"""
        # Implementación simplificada
        products = Product.filter_by(client_id=client_id)
        # ... lógica de filtrado por categoría
        return []
```

## 📦 DATOS INICIALES

### clients.json
```json
{
  "data": [
    {
      "id": "demo-client-001",
      "name": "Demo Fashion Store",
      "slug": "demo-fashion",
      "email": "demo@fashionstore.com",
      "industry": "textil",
      "api_key": "demo_api_key_12345",
      "is_active": true,
      "created_at": "2025-10-10T10:00:00Z"
    }
  ],
  "meta": {"version": 1}
}
```

### products.json
```json
{
  "data": [
    {
      "id": "prod-001",
      "client_id": "demo-client-001",
      "category_id": "cat-camisas",
      "name": "Camisa Azul Clásica",
      "description": "Camisa de algodón azul para uso formal",
      "price": 45.99,
      "sku": "CAM-AZ-001",
      "tags": "camisa,azul,algodón,formal",
      "is_active": true,
      "created_at": "2025-10-10T10:00:00Z"
    }
  ],
  "meta": {"version": 1}
}
```

## 🔄 MIGRACIÓN A PostgreSQL

### Servicio de Migración

```python
# services/migration_service.py
import json
import asyncpg
from .json_storage import storage

class MigrationService:
    """Migración de JSON a PostgreSQL"""

    def __init__(self, database_url: str):
        self.database_url = database_url

    async def migrate_all_data(self):
        """Migrar todos los datos JSON a PostgreSQL"""
        conn = await asyncpg.connect(self.database_url)

        try:
            # Migrar clientes
            await self._migrate_table(conn, "clients")

            # Migrar usuarios
            await self._migrate_table(conn, "users")

            # Migrar categorías
            await self._migrate_table(conn, "categories")

            # Migrar productos
            await self._migrate_table(conn, "products")

            # Migrar imágenes
            await self._migrate_table(conn, "images")

            print("✅ Migración completada exitosamente")

        finally:
            await conn.close()

    async def _migrate_table(self, conn, table_name: str):
        """Migrar una tabla específica"""
        records = storage.get_all(table_name)

        for record in records:
            # Insertar en PostgreSQL
            columns = list(record.keys())
            values = list(record.values())
            placeholders = [f"${i+1}" for i in range(len(values))]

            sql = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT (id) DO UPDATE SET
                {', '.join([f'{col} = EXCLUDED.{col}' for col in columns if col != 'id'])}
            """

            await conn.execute(sql, *values)

        print(f"✅ Migrada tabla {table_name}: {len(records)} registros")
```

## 🚀 DEPLOYMENT RAILWAY

### Configuración Simplificada

```python
# config/json_config.py
import os

class JSONConfig:
    """Configuración para modo JSON"""
    USE_JSON_STORAGE = True
    JSON_DATA_DIR = os.getenv("JSON_DATA_DIR", "data")

    # Desactivar dependencias pesadas
    ENABLE_CLIP_PROCESSING = False
    ENABLE_REDIS_CACHE = False
    ENABLE_VECTOR_SEARCH = False

    # Cloudinary simplificado
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
```

### Dockerfile Simplificado

```dockerfile
# Dockerfile.json
FROM python:3.11-slim

WORKDIR /app

# Solo dependencias básicas
COPY requirements-json.txt .
RUN pip install -r requirements-json.txt

COPY . .

# Crear directorio de datos
RUN mkdir -p data

EXPOSE 5000

CMD ["python", "app.py"]
```

### requirements-json.txt
```
Flask==3.0.0
Flask-CORS==4.0.0
Flask-Login==0.6.3
python-dotenv==1.0.0
cloudinary==1.36.0
Pillow==10.0.1
```

## 📊 MÉTRICAS DE COMPARACIÓN

| Aspecto | JSON | PostgreSQL |
|---------|------|-------------|
| **Costo Railway** | $0/mes | $5-10/mes |
| **Setup Time** | 1 hora | 4-6 horas |
| **Desarrollo** | Rápido | Medio |
| **Búsqueda** | Básica | Avanzada |
| **Escalabilidad** | <1000 productos | Ilimitada |
| **Rendimiento** | Limitado | Óptimo |
| **Funcionalidad** | 60% | 100% |

## 🎯 RECOMENDACIÓN ESTRATÉGICA

### ✅ **USAR JSON SI:**
- Prototipo rápido para demos
- Budget limitado ($0 vs $5-10/mes)
- <500 productos por cliente
- Validación de mercado inicial
- 1-2 meses de desarrollo

### ❌ **NO USAR JSON SI:**
- Búsqueda por similitud es crítica
- >1000 productos esperados
- Múltiples usuarios concurrentes
- Producción real desde el inicio
- Rendimiento es prioridad

### 🔄 **ESTRATEGIA HÍBRIDA RECOMENDADA:**

1. **Fase 1 (1-2 meses)**: JSON + Railway gratuito
2. **Fase 2 (mes 3)**: Migración a PostgreSQL
3. **Fase 3 (mes 4+)**: Funcionalidades completas

Este enfoque permite:
- ⚡ **MVP rápido** con costo $0
- 📊 **Validación** de funcionalidades core
- 🔄 **Migración suave** sin reescribir todo
- 💰 **Control de costos** progresivo
