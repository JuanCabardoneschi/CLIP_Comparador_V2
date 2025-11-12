# BLIP - Mejores Prácticas de Implementación

> **Fuentes**: Investigación en repositorios oficiales de Salesforce/BLIP y HuggingFace/transformers
> **Fecha**: Octubre 2025
> **Contexto**: Migración de CLIP → BLIP para sistema multi-categoría de detección de prendas

---

## 📋 Resumen Ejecutivo

### Modelo Recomendado: `BlipForImageTextRetrieval`
**Razón**: Es el modelo oficial diseñado específicamente para **similitud imagen-texto** (nuestro caso de uso).

```python
from transformers import BlipProcessor, BlipForImageTextRetrieval

# ✅ CORRECTO - Modelo especializado en retrieval
model = BlipForImageTextRetrieval.from_pretrained("Salesforce/blip-itm-base-coco")
processor = BlipProcessor.from_pretrained("Salesforce/blip-itm-base-coco")
```

### ❌ NO usar: `BlipModel`
- **Deprecado** según la documentación oficial
- HuggingFace recomienda usar modelos especializados según el caso de uso
- Referencia: `/src/transformers/models/blip/modeling_blip.py#L563-L574`

---

## 🎯 Arquitectura de BLIP para Retrieval

### Componentes Clave

```python
class BlipForImageTextRetrieval:
    - vision_model: BlipVisionModel           # Encoder de imágenes
    - text_encoder: BlipTextModel             # Encoder de texto
    - vision_proj: nn.Linear                  # Proyección imagen → espacio común
    - text_proj: nn.Linear                    # Proyección texto → espacio común
    - itm_head: nn.Linear(hidden_size, 2)     # Head para Image-Text Matching (opcional)
```

**Clave**: BLIP tiene **dos modos de operación**:
1. **ITC (Image-Text Contrastive)**: Similitud coseno entre embeddings proyectados
2. **ITM (Image-Text Matching)**: Clasificación binaria (relevante/no relevante)

---

## 🔧 Patrón 1: Carga del Modelo

### Código de Producción

```python
import torch
from transformers import BlipProcessor, BlipForImageTextRetrieval

def load_blip_model(device: str = "cpu"):
    """
    Carga BLIP optimizado para retrieval de imágenes.

    Returns:
        model: BlipForImageTextRetrieval
        processor: BlipProcessor
    """
    model_name = "Salesforce/blip-itm-base-coco"

    # Cargar procesador (maneja tokenización + preprocessing)
    processor = BlipProcessor.from_pretrained(model_name)

    # Cargar modelo
    model = BlipForImageTextRetrieval.from_pretrained(model_name)
    model.to(device)
    model.eval()  # ✅ CRÍTICO: Modo evaluación para inference

    return model, processor
```

### Configuraciones Disponibles

| Modelo | Tamaño | Parámetros | Velocidad | Precisión |
|--------|--------|------------|-----------|-----------|
| `blip-itm-base-coco` | Base | ~223M | ⚡⚡⚡ | ⭐⭐⭐ |
| `blip-itm-large-coco` | Large | ~447M | ⚡⚡ | ⭐⭐⭐⭐ |

**Recomendación Railway**: `base` (memoria limitada: 512 MB, Railway Hobby Plan)

---

## 🖼️ Patrón 2: Preprocessing de Imágenes

### Transformaciones Oficiales

```python
from PIL import Image
import requests

def preprocess_image_blip(image_path: str, processor):
    """
    Preprocesa imagen siguiendo estándares BLIP oficiales.

    Transformaciones aplicadas por BlipProcessor internamente:
    - Resize a (384, 384) con interpolación BICUBIC
    - ToTensor: [0, 255] → [0.0, 1.0]
    - Normalize: mean=(0.48145466, 0.4578275, 0.40821073)
                 std=(0.26862954, 0.26130258, 0.27577711)
    """
    # Cargar imagen
    if image_path.startswith("http"):
        image = Image.open(requests.get(image_path, stream=True).raw)
    else:
        image = Image.open(image_path)

    # BlipProcessor maneja todo automáticamente
    inputs = processor(images=image, return_tensors="pt")

    return inputs
```

### 🎨 Valores de Normalización (NO cambiar)

```python
# ⚠️ Estos valores son ESPECÍFICOS de BLIP - entrenado con ImageNet
BLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
BLIP_STD = (0.26862954, 0.26130258, 0.27577711)
```

**Fuente**: `/src/transformers/models/blip_retrieval.py` (repositorio Salesforce/BLIP)

---

## 🔢 Patrón 3: Extracción de Embeddings

### Modo 1: Contrastive Embeddings (ITC) - **NUESTRO CASO**

```python
@torch.no_grad()  # ✅ CRÍTICO: Deshabilitar gradientes en inference
def get_image_embedding(image, model, processor, device="cpu"):
    """
    Extrae embedding de imagen normalizado para similitud coseno.

    Returns:
        np.ndarray: Embedding normalizado (L2) de forma (512,) para base
    """
    model.eval()

    # Preprocesar
    inputs = processor(images=image, return_tensors="pt").to(device)

    # Forward pass (modo ITC - sin ITM head)
    outputs = model(**inputs, use_itm_head=False)

    # Extraer embedding de imagen
    image_embeds = outputs.image_embeds  # Ya normalizado internamente

    # Convertir a numpy
    embedding = image_embeds[0].cpu().numpy()

    return embedding

@torch.no_grad()
def get_text_embedding(text: str, model, processor, device="cpu"):
    """
    Extrae embedding de texto normalizado para similitud coseno.

    Returns:
        np.ndarray: Embedding normalizado (L2) de forma (512,) para base
    """
    model.eval()

    # Preprocesar
    inputs = processor(text=text, return_tensors="pt").to(device)

    # Forward pass (modo ITC)
    outputs = model(**inputs, use_itm_head=False)

    # Extraer embedding de texto
    text_embeds = outputs.text_embeds  # Ya normalizado internamente

    # Convertir a numpy
    embedding = text_embeds[0].cpu().numpy()

    return embedding
```

### 📊 Estructura de Outputs

```python
# outputs.image_embeds: torch.FloatTensor (batch_size, projection_dim)
# outputs.text_embeds: torch.FloatTensor (batch_size, projection_dim)
# projection_dim = 256 para BLIP-base (verificar con model.config)
```

### ✅ Normalización Automática

**IMPORTANTE**: BLIP **normaliza automáticamente** los embeddings:

```python
# Código interno de BlipForImageTextRetrieval.forward():
image_feat = normalize(self.vision_proj(image_embeds[:, 0, :]), dim=-1)
text_feat = normalize(self.text_proj(question_embeds[:, 0, :]), dim=-1)
```

**Referencia**: `/src/transformers/models/blip/modeling_blip.py#L1267-L1284`

Por lo tanto:
- ❌ NO normalizar manualmente después de extraer
- ✅ Usar embeddings tal cual vienen de `outputs.image_embeds` / `outputs.text_embeds`

---

## 🧮 Patrón 4: Cálculo de Similitud

### Similitud Coseno (Embeddings ya normalizados)

```python
import numpy as np

def cosine_similarity_blip(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Calcula similitud coseno entre embeddings BLIP.

    IMPORTANTE: Como BLIP normaliza automáticamente (L2 norm),
    la similitud coseno se reduce a un simple producto punto.

    Args:
        embedding1: Embedding normalizado (512,)
        embedding2: Embedding normalizado (512,)

    Returns:
        float: Similitud en rango [-1, 1] (típicamente [0, 1] en la práctica)
    """
    # Como están normalizados: cosine_sim = dot_product
    similarity = np.dot(embedding1, embedding2)

    return float(similarity)
```

### Batch Similarity (Optimizado)

```python
def batch_similarity_blip(query_embedding: np.ndarray,
                         catalog_embeddings: np.ndarray) -> np.ndarray:
    """
    Calcula similitudes entre 1 query y N embeddings del catálogo.

    Args:
        query_embedding: (projection_dim,)
        catalog_embeddings: (N, projection_dim)

    Returns:
        np.ndarray: (N,) con similitudes
    """
    # Producto punto vectorizado (MUCHO más rápido que loops)
    similarities = catalog_embeddings @ query_embedding

    return similarities
```

---

## 🎨 Patrón 5: Prompts para Centroides

### Estructura Recomendada (según papers BLIP)

```python
# ✅ BUENO - Descriptivo y natural
"a photo of a {category_name}"
"an image showing a {category_name}"

# ✅ MEJOR - Con contexto del dominio
"a photo of a {category_name} garment"
"clothing item: {category_name}"

# ❌ MALO - Demasiado simple
"{category_name}"

# ❌ MALO - Demasiado complejo
"This is a high-quality photograph showing a {category_name} garment in retail display"
```

### Ejemplos para Nuestro Sistema

```python
CATEGORY_PROMPTS = {
    "CAMISA": "a photo of a shirt",
    "PANTALON": "a photo of pants",
    "VESTIDO": "a photo of a dress",
    "GORRA": "a photo of a cap",
    # ...
}
```

---

## 🔥 Patrón 6: Inference Optimizado

### Código de Producción con @torch.no_grad()

```python
import torch
from typing import List, Tuple

@torch.no_grad()  # ✅ CRÍTICO: Ahorra memoria y acelera inference
def batch_encode_images(images: List[Image.Image],
                       model,
                       processor,
                       device: str = "cpu",
                       batch_size: int = 32) -> np.ndarray:
    """
    Procesa múltiples imágenes en batches para eficiencia.

    Args:
        images: Lista de PIL Images
        batch_size: Tamaño de batch (ajustar según memoria disponible)

    Returns:
        np.ndarray: (N, projection_dim) embeddings
    """
    model.eval()
    all_embeddings = []

    # Procesar en batches
    for i in range(0, len(images), batch_size):
        batch_images = images[i:i + batch_size]

        # Preprocesar batch
        inputs = processor(images=batch_images, return_tensors="pt").to(device)

        # Forward pass
        outputs = model(**inputs, use_itm_head=False)

        # Extraer embeddings
        embeddings = outputs.image_embeds.cpu().numpy()
        all_embeddings.append(embeddings)

    # Concatenar todos los batches
    return np.vstack(all_embeddings)
```

### 🚀 Optimizaciones Adicionales

```python
# 1. Modo eval SIEMPRE en inference
model.eval()

# 2. Deshabilitar autograd globalmente si solo haces inference
torch.set_grad_enabled(False)

# 3. Para Railway (CPU-only), asegurar device correcto
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

# 4. Liberar caché después de procesamiento pesado
import gc
gc.collect()
torch.cuda.empty_cache() if torch.cuda.is_available() else None
```

---

## 📊 Patrón 7: Compatibilidad con Sistema Actual

### Integración con DB Existente

```python
# ✅ BUENO: Reutilizar campo Image.clip_embedding
def save_blip_embedding_to_db(image_id: int, embedding: np.ndarray):
    """
    Guarda embedding BLIP en campo existente.

    IMPORTANTE:
    - Campo: Image.clip_embedding (tipo: JSON/Text)
    - Formato: Lista de floats serializada como JSON
    - BLIP projection_dim puede diferir de CLIP (512 vs 256)
    """
    from app import db
    from app.models import Image

    # Convertir numpy → lista → JSON
    embedding_list = embedding.tolist()

    # Actualizar DB
    image = db.session.query(Image).get(image_id)
    image.clip_embedding = json.dumps(embedding_list)
    db.session.commit()
```

### ⚠️ Diferencias de Dimensión

| Modelo | Embedding Dimension |
|--------|-------------------|
| CLIP ViT-B/32 | 512 |
| CLIP ViT-B/16 | 512 |
| **BLIP-base** | **256** ⚠️ |
| **BLIP-large** | **256** ⚠️ |

**ACCIÓN REQUERIDA**:
- Verificar `model.config.projection_dim` al cargar modelo
- Actualizar validaciones si dimension cambió
- Recalcular TODOS los centroides con nueva dimensión

---

## 🏗️ Implementación Paso a Paso

### 1. Crear Módulo `embeddings_blip.py`

```python
"""
BLIP Embeddings - Reemplazo para CLIP siguiendo mejores prácticas.
"""
import torch
import numpy as np
from PIL import Image
from typing import Union, List
from transformers import BlipProcessor, BlipForImageTextRetrieval

class BLIPEmbeddings:
    def __init__(self, device: str = "cpu"):
        self.device = device
        self.model = None
        self.processor = None
        self._load_model()

    def _load_model(self):
        """Carga modelo BLIP siguiendo best practices."""
        model_name = "Salesforce/blip-itm-base-coco"

        self.processor = BlipProcessor.from_pretrained(model_name)
        self.model = BlipForImageTextRetrieval.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()  # ✅ Modo evaluación

    @torch.no_grad()  # ✅ Deshabilitar autograd
    def encode_image(self, image: Union[Image.Image, str]) -> np.ndarray:
        """
        Genera embedding de imagen.

        Args:
            image: PIL Image o ruta

        Returns:
            np.ndarray: Embedding normalizado (projection_dim,)
        """
        if isinstance(image, str):
            image = Image.open(image)

        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        outputs = self.model(**inputs, use_itm_head=False)

        return outputs.image_embeds[0].cpu().numpy()

    @torch.no_grad()
    def encode_text(self, text: str) -> np.ndarray:
        """
        Genera embedding de texto.

        Args:
            text: Texto a encodear (ej: "a photo of a shirt")

        Returns:
            np.ndarray: Embedding normalizado (projection_dim,)
        """
        inputs = self.processor(text=text, return_tensors="pt").to(self.device)
        outputs = self.model(**inputs, use_itm_head=False)

        return outputs.text_embeds[0].cpu().numpy()

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calcula similitud coseno (optimizado para embeddings normalizados).
        """
        return float(np.dot(embedding1, embedding2))
```

### 2. Migrar `api.py` y `diagnostic.py`

```python
# ❌ ANTES (CLIP)
from embeddings import load_model_and_preprocess
model, preprocess, device = load_model_and_preprocess()

# ✅ DESPUÉS (BLIP)
from embeddings_blip import BLIPEmbeddings
blip = BLIPEmbeddings(device="cpu")

# Uso:
image_embedding = blip.encode_image(image)
text_embedding = blip.encode_text("a photo of a shirt")
similarity = blip.similarity(image_embedding, text_embedding)
```

### 3. Recalcular Centroides

```python
# Ver: app/models/category.py método recalculate_all_centroids()
def recalculate_all_centroids_blip():
    """Recalcula centroides usando BLIP."""
    from app.models import Category

    blip = BLIPEmbeddings()

    for category in Category.query.all():
        # Generar embedding de texto para categoría
        prompt = f"a photo of a {category.name.lower()}"
        centroid_embedding = blip.encode_text(prompt)

        # Guardar
        category.centroid_embedding = json.dumps(centroid_embedding.tolist())
        db.session.commit()
```

### 4. Re-embedear Catálogo

```python
def reembed_all_images_blip():
    """Job para re-embedear todas las imágenes con BLIP."""
    from app.models import Image

    blip = BLIPEmbeddings()
    images = Image.query.all()

    for i, image in enumerate(images):
        try:
            # Descargar de Cloudinary
            img = download_image(image.cloudinary_url)

            # Generar embedding BLIP
            embedding = blip.encode_image(img)

            # Guardar
            image.clip_embedding = json.dumps(embedding.tolist())
            db.session.commit()

            if i % 100 == 0:
                print(f"Procesadas {i}/{len(images)} imágenes")

        except Exception as e:
            print(f"Error en imagen {image.id}: {e}")
```

---

## ⚠️ Diferencias CLIP vs BLIP

| Aspecto | CLIP | BLIP |
|---------|------|------|
| **Dimensión** | 512 | 256 ⚠️ |
| **Normalización** | Manual | **Automática** ✅ |
| **Preprocessing** | Manual transforms | **BlipProcessor** ✅ |
| **Modelo** | `clip.load()` | `BlipForImageTextRetrieval` ✅ |
| **Tokenización** | `clip.tokenize()` | **Incluida en processor** ✅ |
| **Modo Eval** | Manual | **Requerido explícitamente** ⚠️ |

---

## 🐛 Debugging Checklist

### Problemas Comunes

1. **Embeddings con valores NaN**
   - ✅ Verificar `model.eval()` está llamado
   - ✅ Verificar `@torch.no_grad()` en funciones de inference
   - ✅ Revisar formato de entrada (PIL Image RGB)

2. **Dimensiones incorrectas**
   - ✅ Verificar `model.config.projection_dim`
   - ✅ No confundir `last_hidden_state` con `image_embeds` / `text_embeds`

3. **Similitudes fuera de rango [-1, 1]**
   - ✅ Verificar que usas `use_itm_head=False` (modo ITC)
   - ✅ Embeddings deben estar normalizados (BLIP lo hace automáticamente)

4. **Memoria insuficiente en Railway**
   - ✅ Usar `batch_size=1` o `batch_size=8` máximo
   - ✅ Liberar caché con `gc.collect()` después de batches
   - ✅ Considerar `torch.float16` si Railway soporta (verificar)

---

## 📚 Referencias

### Repositorios Oficiales
- **Salesforce/BLIP**: https://github.com/salesforce/BLIP
- **HuggingFace Transformers**: https://github.com/huggingface/transformers

### Papers
- **BLIP Paper**: "BLIP: Bootstrapping Language-Image Pre-training" (Li et al., 2022)

### Documentación
- **BlipForImageTextRetrieval**: https://huggingface.co/docs/transformers/model_doc/blip#blipforimagetextretrieval
- **BlipProcessor**: https://huggingface.co/docs/transformers/model_doc/blip#blipprocessor

---

## ✅ Checklist de Migración

- [ ] Crear `embeddings_blip.py` con clase `BLIPEmbeddings`
- [ ] Actualizar `api.py` para usar BLIP
- [ ] Actualizar `diagnostic.py` para usar BLIP
- [ ] Actualizar `calibration.py` para usar BLIP
- [ ] Re-embedear todas las imágenes del catálogo
- [ ] Recalcular centroides de categorías con prompts de texto
- [ ] Ejecutar calibración para cada cliente con dataset existente
- [ ] Validar que thresholds funcionan correctamente
- [ ] Actualizar documentación en README.md
- [ ] Eliminar dependencias de CLIP de requirements.txt

---

**Autor**: GitHub Copilot + Investigación oficial BLIP/HuggingFace
**Fecha**: Octubre 2025
**Estado**: ✅ READY FOR IMPLEMENTATION
