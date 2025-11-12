# Plan de Migración a BLIP-2 (Railway Pro)

> **Decisión**: Migrar a BLIP-2 OPT-2.7B aprovechando Railway Pro (32 GB RAM)
> **Fecha**: Noviembre 2025
> **Ventaja clave**: Sistema unificado (embeddings + NLU) en un solo modelo

---

## 🎯 Objetivos

1. **Reemplazar CLIP** → BLIP-2 para embeddings imagen-texto
2. **Reemplazar MiniLM** → Q-Former de BLIP-2 para NLU
3. **Simplificar arquitectura** → De 2 modelos a 1
4. **Mantener funcionalidad** → Sin cambios en API externa

---

## 📊 Recursos Railway Pro

| Recurso | Límite | Uso BLIP-2 | Disponible |
|---------|--------|------------|------------|
| **RAM** | 32 GB | ~7 GB | 25 GB ✅ |
| **vCPU** | 32 | ~4 vCPU | 28 vCPU ✅ |
| **Storage** | 100 GB | ~10 GB | 90 GB ✅ |

**Conclusión**: BLIP-2 cabe cómodamente con márgenes amplios.

---

## 🏗️ Arquitectura Propuesta

### ANTES (CLIP + MiniLM)
```
┌─────────────────────────────┐
│ CLIP ViT-B/16               │  ← Embeddings (512D)
│ - Image encoding            │
│ - Text encoding             │
└─────────────────────────────┘
           +
┌─────────────────────────────┐
│ MiniLM L12                  │  ← NLU
│ - Query normalization       │
│ - Intent extraction         │
└─────────────────────────────┘
```
**RAM Total**: ~1.2 GB
**Complejidad**: 2 modelos separados

### DESPUÉS (BLIP-2 Unificado)
```
┌─────────────────────────────────────────┐
│ BLIP-2 OPT-2.7B                         │
│ ┌─────────────────────────────────────┐ │
│ │ Vision Encoder (ViT-L/14)           │ │  ← Image embeddings
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ Q-Former (32 queries)               │ │  ← Multimodal bridge + NLU
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ OPT-2.7B Language Model             │ │  ← Text understanding
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```
**RAM Total**: ~7 GB (FP16)
**Complejidad**: 1 modelo integrado

---

## 🔧 Implementación

### 1. Crear Módulo BLIP-2 Unificado

```python
# clip_admin_backend/app/utils/blip2_embeddings.py

"""
BLIP-2 Unified Embeddings + NLU
Reemplaza CLIP + MiniLM con un solo modelo
"""
import torch
from transformers import Blip2Processor, Blip2ForImageTextRetrieval
from PIL import Image
import numpy as np
from typing import Union, List, Dict

class BLIP2System:
    """
    Sistema unificado BLIP-2 para:
    - Embeddings de imágenes
    - Embeddings de texto
    - Normalización de queries (NLU)
    """

    def __init__(self, device: str = "cpu", use_fp16: bool = True):
        self.device = device
        self.use_fp16 = use_fp16
        self.model = None
        self.processor = None
        self._load_model()

    def _load_model(self):
        """Carga BLIP-2 con optimizaciones para Railway Pro"""
        print("🚀 Cargando BLIP-2 OPT-2.7B...")

        model_name = "Salesforce/blip2-itm-vit-g"  # Image-Text Matching variant

        # Cargar procesador
        self.processor = Blip2Processor.from_pretrained(model_name)

        # Cargar modelo con optimizaciones
        self.model = Blip2ForImageTextRetrieval.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if self.use_fp16 else torch.float32,
            device_map="auto"  # Distribuye automáticamente en memoria
        )

        self.model.eval()  # Modo evaluación
        print(f"✅ BLIP-2 cargado ({self.device}, FP16={self.use_fp16})")

    @torch.no_grad()
    def encode_image(self, image: Union[Image.Image, str]) -> np.ndarray:
        """
        Genera embedding de imagen normalizado.

        Args:
            image: PIL Image o ruta

        Returns:
            np.ndarray: Embedding (256D) normalizado L2
        """
        if isinstance(image, str):
            image = Image.open(image).convert('RGB')

        # Preprocesar
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Forward pass (modo ITC - Contrastive)
        outputs = self.model(**inputs, use_image_text_matching_head=False)

        # Extraer embedding normalizado
        embedding = outputs.image_embeds[0].cpu().numpy()

        return embedding

    @torch.no_grad()
    def encode_text(self, text: str) -> np.ndarray:
        """
        Genera embedding de texto normalizado.

        Args:
            text: Texto a encodear (ej: "camisa azul")

        Returns:
            np.ndarray: Embedding (256D) normalizado L2
        """
        # Preprocesar
        inputs = self.processor(text=text, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Forward pass
        outputs = self.model(**inputs, use_image_text_matching_head=False)

        # Extraer embedding normalizado
        embedding = outputs.text_embeds[0].cpu().numpy()

        return embedding

    @torch.no_grad()
    def normalize_query(self, query: str, client_id: int = None) -> Dict:
        """
        Normaliza query usando capacidades NLU de BLIP-2.

        REEMPLAZA a MiniLM porque BLIP-2 tiene mejor comprensión
        multimodal (entiende texto EN CONTEXTO de imágenes).

        Args:
            query: Query del usuario (ej: "camisa azul marino")
            client_id: ID del cliente (para vocabulario específico)

        Returns:
            dict: {'tipo': ..., 'color': ..., 'contexto': [...], ...}
        """
        # TODO: Implementar lógica de NLU con Q-Former
        # Por ahora, mantener compatibilidad con sistema actual

        from app.utils.llm_query_normalizer import _extract_client_vocabulary
        from app.utils.llm_query_normalizer import _semantic_match, _semantic_match_multiple

        # Obtener vocabulario del cliente
        if client_id:
            vocab = _extract_client_vocabulary(client_id)
            colores = vocab['colores']
            tipos = vocab['tipos']
            contextos = vocab['contextos']
        else:
            colores = []
            tipos = []
            contextos = []

        # Generar embedding del query con BLIP-2
        query_embedding = self.encode_text(query)

        # Matching semántico (usar embeddings de BLIP-2)
        color = _semantic_match(query, colores, threshold=0.65) if colores else None
        tipo = _semantic_match(query, tipos, threshold=0.60) if tipos else None
        contexto = _semantic_match_multiple(query, contextos, threshold=0.45) if contextos else []

        return {
            'tipo': tipo,
            'color': color,
            'contexto': contexto,
            'query': query,
            'embedding': query_embedding.tolist()
        }

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calcula similitud coseno (embeddings ya normalizados por BLIP-2).
        """
        return float(np.dot(embedding1, embedding2))

    def batch_encode_images(self, images: List[Image.Image], batch_size: int = 8) -> np.ndarray:
        """
        Procesa múltiples imágenes en batches.

        Args:
            images: Lista de PIL Images
            batch_size: Tamaño de batch

        Returns:
            np.ndarray: (N, 256) embeddings
        """
        all_embeddings = []

        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]

            # Preprocesar batch
            inputs = self.processor(images=batch, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Forward
            with torch.no_grad():
                outputs = self.model(**inputs, use_image_text_matching_head=False)

            embeddings = outputs.image_embeds.cpu().numpy()
            all_embeddings.append(embeddings)

        return np.vstack(all_embeddings)


# Singleton global
_blip2_system = None

def get_blip2_system() -> BLIP2System:
    """Obtiene instancia singleton de BLIP-2"""
    global _blip2_system
    if _blip2_system is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _blip2_system = BLIP2System(device=device, use_fp16=True)
    return _blip2_system
```

### 2. Actualizar API Search

```python
# clip_admin_backend/app/blueprints/api.py

# ❌ ANTES
from embeddings import get_clip_model
from app.utils.llm_query_normalizer import normalize_query

model, processor = get_clip_model()
llm_norm = normalize_query(query_text, client_id=client.id)

# ✅ DESPUÉS
from app.utils.blip2_embeddings import get_blip2_system

blip2 = get_blip2_system()
llm_norm = blip2.normalize_query(query_text, client_id=client.id)
```

### 3. Migrar Código de Embeddings

**Búsqueda Visual**:
```python
# api.py - search_image()

# ❌ ANTES
image_embedding = encode_image(image, model, processor)

# ✅ DESPUÉS
blip2 = get_blip2_system()
image_embedding = blip2.encode_image(image)
```

**Búsqueda por Texto**:
```python
# api.py - text_search()

# ❌ ANTES
text_features = model.get_text_features(**text_inputs)
query_embedding = text_features.cpu().numpy()[0]

# ✅ DESPUÉS
blip2 = get_blip2_system()
query_embedding = blip2.encode_text(expanded_query)
```

**Centroides**:
```python
# category.py - update_centroid_embedding()

# ❌ ANTES
embedding_array = np.array(json.loads(image.clip_embedding))

# ✅ DESPUÉS (sin cambios - solo re-generar embeddings)
# El campo clip_embedding ahora almacena embeddings BLIP-2
```

---

## 🔄 Plan de Migración Paso a Paso

### Fase 1: Preparación (Local)
- [x] Documentar arquitectura actual
- [x] Crear BLIP2_MIGRATION_PLAN.md
- [ ] Implementar `blip2_embeddings.py`
- [ ] Testear localmente con dataset pequeño
- [ ] Medir RAM y latencia real

### Fase 2: Integración (Local)
- [ ] Refactorizar `api.py` para usar BLIP-2
- [ ] Refactorizar `diagnostic.py`
- [ ] Refactorizar `calibration.py`
- [ ] Actualizar tests
- [ ] Validar que todo funciona igual

### Fase 3: Re-embedding (Local)
- [ ] Script para re-embedear todas las imágenes
- [ ] Job batch con progress tracking
- [ ] Backup BD antes de comenzar
- [ ] Ejecutar re-embedding masivo
- [ ] Recalcular centroides

### Fase 4: Recalibración
- [ ] Ejecutar calibración para cada cliente
- [ ] Aplicar nuevos thresholds F1-óptimos
- [ ] Validar resultados de detección

### Fase 5: Deploy Railway Pro
- [ ] Upgrade a Railway Pro ($20/mes)
- [ ] Configurar variables de entorno
- [ ] Deploy con BLIP-2
- [ ] Monitoring de RAM/CPU
- [ ] Tests de producción

### Fase 6: Limpieza
- [ ] Remover código de CLIP
- [ ] Remover dependencias de MiniLM
- [ ] Actualizar documentación
- [ ] Eliminar training_events/variants

---

## 💰 Costos Railway Pro

| Componente | Costo |
|------------|-------|
| **Suscripción Pro** | $20/mes (incluye $20 de uso) |
| **RAM (7 GB x 24h x 30d)** | ~$5/mes |
| **vCPU (4 vCPU promedio)** | ~$6/mes |
| **Network Egress** | ~$1-2/mes |
| **Total Estimado** | **$20-25/mes** |

**Nota**: Los $20 de suscripción cubren casi todo el uso de recursos.

---

## 🎯 Ventajas de BLIP-2 vs BLIP-1+MiniLM

| Aspecto | BLIP-1 + MiniLM | BLIP-2 Solo |
|---------|----------------|-------------|
| **Modelos** | 2 separados | 1 integrado ✅ |
| **RAM** | 1.2 GB | 7 GB |
| **Complejidad** | Media | Baja ✅ |
| **NLU** | Solo texto | Multimodal ✅ |
| **Latencia** | ~300ms | ~500ms |
| **Costo Railway** | Hobby OK | Requiere Pro |
| **Calidad** | Buena | Superior ✅ |

---

## ⚠️ Consideraciones

1. **Latencia**: BLIP-2 es ~1.5-2x más lento que CLIP
   - Mitigación: Caché agresivo de embeddings

2. **RAM en Startup**: Pico de ~9 GB al cargar modelo
   - Mitigación: Railway Pro tiene 32 GB (suficiente)

3. **Cold Start**: Primera request tardará ~10-15s
   - Mitigación: Health check que precaliente modelo

4. **Dimensión Embeddings**: 256D (igual que BLIP-1)
   - ✅ Compatible con estructura actual

---

## 🚀 Próximos Pasos

1. **AHORA**: Implementar `blip2_embeddings.py`
2. **DESPUÉS**: Testear localmente
3. **LUEGO**: Upgrade Railway Pro
4. **FINALMENTE**: Deploy y monitoring

---

**Estado**: 🔄 EN PLANIFICACIÓN
**Fecha Target**: Noviembre 2025
**Owner**: Equipo de desarrollo
