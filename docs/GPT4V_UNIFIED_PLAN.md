# GPT-4V Unified Search – Resumen y Plan de Implementación (13 Nov 2025)

Este documento resume el estado actual del endpoint `/api/search/gpt4v-unified`, las diferencias respecto del endpoint histórico `/api/search`, las funcionalidades faltantes, decisiones estratégicas y próximos pasos.

## Resumen Ejecutivo
- Flujo actual: Imagen → GPT-4V detecta categorías → CLIP busca por categoría → Resultados agrupados.
- Correcciones críticas realizadas: tipos de imagen, uso correcto de CLIPProcessor, campo `Image.clip_embedding`, selección de imagen primaria, `max_results` desde `system_config`, mensajes de intención del usuario, alerta de productos fuera de catálogo, y mejoras de UI.
- Mejora de hoy: Sólo enviamos a Vision categorías con imágenes procesadas y embeddings. El backend ahora expone la lista completa de categorías disponibles para mostrarlas una a una en el widget.

## Estado Actual del Endpoint
Archivo: `clip_admin_backend/app/blueprints/api.py`
- Endpoint: `gpt4v_unified_search()`
- Detección: `detect_categories_with_gpt4v(image, categories_list, client_id)`
- Búsqueda: Similaridad CLIP por categoría con `similarity_threshold` y `max_results_per_category`.
- Respuesta incluye:
  - `detection.prendas`, `detection.categories_detected`
  - `detection.categories_available` (conteo) y `detection.categories_available_list` (nombres, NUEVO)
  - `detection.products_not_found` (prendas fuera de catálogo)
  - `detection.user_intent` (alias de `mensaje_usuario`)
  - `results_by_category` con productos, total en categoría y devueltos
  - `metadata` (tiempos, límites, etc.)

## Diferencias con `/api/search` original
- El original aplicaba SearchOptimizer (3 capas: visual 60%, metadata 30%, negocio 10%), normalización LLM de queries, color detection, y scoring por nombre/SKU/tags.
- El nuevo flujo Vision-first ya pre-filtra por categoría, simplificando varias reglas antiguas.

## Funcionalidades Faltantes – Evaluación
- Críticas (ya implementadas):
  - Imagen primaria, stock en respuesta, URL de producto desde JSONB, filtro por `product_attribute_config`.
- Importantes (recomendadas):
  - Matching de color simplificado (usar color mencionado por GPT-4V en `user_intent` para desempatar dentro de la categoría).
- Estratégicas (decisión de negocio):
  - SearchOptimizer Lite (visual 70%, metadata-color 20%, negocio 10% – pesos fijos iniciales).
  - Búsqueda híbrida texto+imagen (para futuro; requiere cambio de widget).
- Opcionales (no prioritarias ahora):
  - Normalización LLM de queries (no aplica a flujo sólo-imagen).
  - Detección de color separada (redundante; usar `user_intent`).
  - Fallback a búsqueda global (postergar; primero mejorar prompt/detección).

## Cambios realizados hoy
1. Backend: Filtrado de categorías enviadas a Vision
   - Sólo se envían categorías leaf y activas que **tienen al menos una imagen procesada con embedding**.
   - Código: consulta `Product` + `Image` con `Image.is_processed == True` y `Image.clip_embedding != None`, `distinct()` por categoría.
2. Backend: Se agregó `detection.categories_available_list` con los nombres completos.
3. Frontend (widget V3): Se listan las categorías disponibles una por una en el bloque “📋 Categorías disponibles (N en total)”.

## Decisiones y Recomendaciones
- Mantener el conteo de categorías por compatibilidad y exponer siempre la lista para UI.
- No aplicar “category boost” adicional: Vision ya pre-filtra por categoría.
- Implementar color matching simplificado para ranking intra-categoría.
- Considerar SearchOptimizer Lite si se busca mayor control de ranking.

## Próximos Pasos
1. Implementar “Color Matching Simplificado”:
   - Parsear `user_intent` buscando menciones de color.
   - Aplicar boost (+0.30) a productos cuyo atributo de color coincida (semánticamente) con el color detectado.
2. Diseñar SearchOptimizer Lite (pesos fijos) e integrar en `_build_search_results` o en el armado de similitudes.
3. QA end-to-end con imágenes reales por categoría para validar:
   - Detecciones correctas
   - Listado de categorías disponibles
   - Ausencia de categorías sin inventario
   - Calidad de ranking con y sin color matching

## Campos de Respuesta (actual)
- `detection`: `{ prendas, categories_detected, categories_available, categories_available_list, products_not_found, cost_usd, user_intent }`
- `results_by_category`: `{ [category_name]: { products: [...], total_in_category, results_returned } }`
- `metadata`: `{ total_products_found, categories_searched, max_results_per_category, max_results_config, processing_time_ms, similarity_threshold }`

---
Última actualización: 13/11/2025
