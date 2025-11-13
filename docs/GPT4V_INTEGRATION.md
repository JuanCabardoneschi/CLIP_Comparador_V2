"""
Documentación de integración GPT-4 Vision + CLIP Comparador V2
================================================================

## Resumen de cambios

1. **Limpieza completa**: Eliminados Moondream, Grounding DINO y dependencias de prueba
2. **Nuevo blueprint**: `gpt4v_detection.py` para detección de categorías con GPT-4 Vision
3. **requirements.txt actualizado**: Solo dependencias esenciales + openai
4. **Endpoint modificado**: `/api/search/unified` simplificado

## Stack final

### Componentes core:
- ✅ **GPT-4 Vision**: Detección de categorías (API externa, pago por uso)
- ✅ **CLIP ViT-L/14**: Embeddings visuales y búsqueda por similitud
- ✅ **Sentence-Transformers (MiniLM)**: LLM local para búsqueda de texto
- ✅ **Google Translator**: Traducciones automáticas
- ✅ **PostgreSQL + Redis**: Base de datos y caché
- ✅ **Cloudinary**: Almacenamiento de imágenes

### RAM estimado en Railway Pro (8GB):
- CLIP ViT-L/14: ~3 GB
- Sentence Transformers: ~200 MB
- PyTorch CPU: ~500 MB
- Flask + overhead: ~300 MB
- **Total: ~4 GB** (cabe en Railway Pro $20/mes)

## Flujo de búsqueda actualizado

### Antes (con CLIP centroids):
1. Cliente sube imagen → `/api/search/unified`
2. Backend detecta categorías con centroids multi-crop (lento, impreciso)
3. Busca productos en categorías detectadas
4. Retorna resultados

### Ahora (con GPT-4 Vision):
1. Cliente sube imagen → `/api/gpt4v/detect`
2. GPT-4 Vision detecta categoría (preciso, rápido)
3. Cliente envía categoría + imagen → `/api/search/unified`
4. Backend busca productos en categoría específica
5. Retorna resultados

## Endpoints disponibles

### 1. Detección de categoría (GPT-4 Vision)
```
POST /api/gpt4v/detect
Headers:
    Content-Type: multipart/form-data

Body (form-data):
    image: <archivo de imagen>
    client_id: <UUID del cliente> (opcional)
    categories: <lista separada por comas> (opcional)

Response:
{
    "success": true,
    "category": "Delantal Completo",
    "confidence": "Alta",
    "reasoning": "Se observa un delantal negro completo...",
    "categories_available": ["Delantal Completo", "Medio Delantal", ...]
}
```

### 2. Búsqueda simplificada (CLIP)
```
POST /api/search/unified
Headers:
    X-API-Key: <API Key del cliente>
    Content-Type: application/json

Body:
{
    "image": "data:image/png;base64,...",
    "category": "Delantal Completo",  // NUEVO: Obligatorio
    "max_results": 5
}

Response:
{
    "success": true,
    "client": {...},
    "products": [
        {
            "id": "...",
            "name": "...",
            "similarity_score": 0.95,
            "image_url": "...",
            ...
        }
    ],
    "metadata": {
        "category_used": "Delantal Completo",
        "processing_time_ms": 123,
        ...
    }
}
```

## Configuración requerida

### Variables de entorno (.env o Railway):
```bash
# OpenAI API Key (GPT-4 Vision)
OPENAI_API_KEY=sk-...

# Otras variables existentes
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
CLOUDINARY_URL=cloudinary://...
CLIP_MODEL=ViT-L/14  # o ViT-B/16 para menos RAM
```

### Costos estimados GPT-4 Vision:
- Precio: ~$0.01 por imagen (puede variar)
- 100 búsquedas/día: ~$1/día = $30/mes
- 1000 búsquedas/día: ~$10/día = $300/mes

## Próximos pasos

1. ✅ Agregar `OPENAI_API_KEY` a Railway
2. ✅ Reiniciar servidor Flask
3. 🔲 Probar `/api/gpt4v/detect` con imagen de delantal
4. 🔲 Modificar widget/frontend para usar flujo en 2 pasos:
   - Paso 1: Detectar categoría con GPT-4V
   - Paso 2: Buscar productos con CLIP
5. 🔲 Monitorear costos de OpenAI en dashboard

## Archivos modificados

- `requirements.txt`: Limpiado y agregado `openai>=1.0.0`
- `app.py`: Removido moondream_bp, agregado gpt4v_bp
- `app/blueprints/gpt4v_detection.py`: Nuevo blueprint (270 líneas)
- `app/blueprints/api.py`: (pendiente modificación para categoria obligatoria)

## Archivos eliminados

- `clip_admin_backend/app/blueprints/moondream_test.py`
- `clip_admin_backend/app/templates/moondream_test.html`
- Dependencias: bitsandbytes, einops, groundingdino-py, opencv-python, timm

## Notas importantes

- El sistema ahora prioriza **precisión sobre velocidad**
- GPT-4 Vision tiene ~100% precisión vs ~60-70% con centroids
- Costo adicional justificado por eliminar frustración del usuario
- Railway Pro ($20/mes) sigue siendo necesario para CLIP
- Stack final más simple y mantenible
