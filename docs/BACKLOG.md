# Backlog de Mejoras

## 1) Búsqueda de Texto en Modo Multi-Categoría (futuro)
- Estado: Pendiente (no implementado). Mantener por ahora búsqueda de texto en una sola categoría.
- Descripción: Permitir que la búsqueda textual recupere resultados organizados por múltiples categorías (similar al flujo visual multi-categoría), mostrando secciones por categoría candidata.
- Activación: Detrás de feature flag (p. ej., `text_multi_category=true` o configuración en `system_config`). Por defecto desactivado.
- Heurística de categorías candidatas:
  - Prioridad: exacta (nombre/alt/name_en) → tokens (score) → LLM (similitud).
  - Limitar a top-N categorías con productos activos y similitud/score por encima de umbral.
- Respuesta API (propuesta):
  - `mode: "multi_category"`
  - `results_by_category: [{ category_id, category_name, confidence, product_count, products: [...] }, ...]`
  - `category_selection_info: { query, candidates: [{name, method: 'exact|tokens|llm', score|similarity}], thresholds }`
- UI/Widget:
  - Reutilizar el layout de multi-categoría del flujo visual.
  - Mostrar banner si se trató de una sustitución (closest category) con `category_substitution_info`.
- Criterios de Aceptación:
  - Flag en OFF: comportamiento actual (una sola categoría, sin cambios).
  - Flag en ON: organizar resultados de texto por categorías seleccionadas; sin fallbacks globales.
  - Documentación de thresholds y métricas para ajuste.
- Riesgos:
  - Ambigüedad alta en consultas cortas puede generar ruido. Mitigar con límites de N, umbrales y mensajes de guía/refinamiento.
