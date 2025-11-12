# Migración BLIP-only (HuggingFace) para CLIP Comparador V2

Estado: aprobado por producto • Alcance: 100% reemplazo CLIP → BLIP • Entorno: Local (sin Railway)

## 1. Objetivo y alcance

Migrar el sistema completo de embeddings y scoring de imágenes/textos desde CLIP a BLIP (ViT-B/16), operando únicamente en entorno local con HuggingFace, sin mantener compatibilidad híbrida ni fallback. La API pública (/api/search) y la UI deben seguir funcionando con el nuevo backend de embeddings, manteniendo o mejorando la calidad de detección multi‑label y la búsqueda híbrida.

Resultados esperados:
- Embeddings de imagen/texto generados con BLIP y almacenados en los mismos campos existentes (sin migraciones de BD).
- Recalibración de umbrales por cliente con BLIP y recalculo de centroides.
- Eliminación de código CLIP y de sus rutas de carga/precarga.
- Documentación y scripts actualizados para operación local.

No incluido: despliegue en Railway (limitación de GPU), vector DB adicional, re-ranking híbrido.

## 2. Decisiones clave

- BLIP-only: no se conserva CLIP en runtime. El rollback se hará con Git.
- Sin cambios de esquema: reutilizar columnas actuales.
  - images.clip_embedding → guardará el vector BLIP (JSON array).
  - categories.centroid_embedding → guardará el centroide BLIP (JSON array).
- Normalización y métrica: vectores L2-normalizados y similitud por coseno (como hoy).
- Modelo sugerido: Salesforce/blip-itm-base-coco (ViT-B/16). Alternativas en Anexos.

## 3. Dependencias y entorno

Añadir/actualizar en requirements.txt (si no están):
- transformers>=4.40.0
- timm>=0.9.0
- accelerate>=0.26.0
- pillow>=9.5.0
- numpy>=1.24.0

Caché local HuggingFace (recomendado para offline):
- Variable opcional: HF_HOME (ruta de caché). Por defecto: %USERPROFILE%\.cache\huggingface

GPU opcional:
- Si el equipo local dispone de CUDA/cuDNN configurados, BLIP se ejecutará en GPU; si no, CPU.

## 4. Inventario de uso CLIP y cambios

Principales archivos impactados (referencias encontradas):
- clip_admin_backend/app/blueprints/embeddings.py (carga de modelo, generación de embeddings CLIP)
- clip_admin_backend/app/blueprints/api.py (detección, búsqueda híbrida, similitud)
- clip_admin_backend/app/blueprints/diagnostic.py (diagnóstico y multi‑label)
- clip_admin_backend/app/blueprints/calibration.py (calibración y thresholds)
- clip_admin_backend/app/blueprints/categories.py (regeneración de embeddings por categoría)
- clip_admin_backend/app/blueprints/products.py (procesamiento de imágenes → embeddings)
- clip_admin_backend/app.py y wsgi.py (precarga CLIP y logs)
- Modelos:
  - app/models/image.py (campo clip_embedding)
  - app/models/category.py (centroid_embedding y utilidades)
- Herramientas varias en tools/ y tests con mención a CLIP

Acción: todas las referencias a CLIP (carga, procesador, logs, helpers) deben sustituirse por BLIP o eliminarse si quedan obsoletas.

## 5. Diseño técnico BLIP‑only

### 5.1 Interfaz de embeddings (helpers BLIP)

- load_model_blip():
  - Cargar y cachear BLIP (modelo + procesador) una sola vez (singleton con lock opcional).
  - Seleccionar device (cuda/cpu) automáticamente.
- image_embed_blip(image | url):
  - Descarga/carga de imagen (PIL), preprocesamiento con BlipProcessor.
  - Forward al modelo para extraer representación visual.
  - L2-normalización del vector de salida.
- text_embed_blip(list[str]):
  - Tokenización y forward para representación textual.
  - L2-normalización por fila.
- similarity(a, b):
  - Producto punto entre vectores normalizados (coseno).

Notas de implementación:
- BLIP ITM (Image-Text Matching) expone heads/embeddings adecuados. Si se usa BlipModel/BlipForImageTextRetrieval, debemos tomar las salidas pooler/hidden adecuadas. Normalizar al final.
- Mantener batch pequeño (1–2) para CPU; ajustar tamaño de imagen (224/256) desde config.

### 5.2 Reutilización de columnas

- images.clip_embedding: almacenar BLIP en JSON (lista de floats). Sobrescribe el CLIP actual.
- categories.centroid_embedding: almacenar el centroide calculado a partir de embeddings BLIP. Ya está preparado para normalizados.

### 5.3 Prompts y clasificación multi‑label

- Se mantienen los prompts existentes (clip_prompt) como prompts_en hasta refactor futuro. BLIP funciona con el mismo esquema: embedding textual vs embedding de imagen, sin softmax competitivo.
- La lógica multi‑label actual (scores independientes + thresholds por categoría + familias exclusivas) se conserva; solo cambia la fuente del embedding.

## 6. Playbook de cambios por archivo

Resumen de reemplazos (sin diffs detallados):

1) embeddings.py
- Eliminar imports de CLIP (CLIPModel, CLIPProcessor) y sus estructuras de cache/idle.
- Implementar load_model_blip(), image_embed_blip(), text_embed_blip(), similarity().
- Exponer helpers neutrales que consumen BLIP:
  - get_image_embedding(url|PIL) → image_embed_blip
  - get_text_embeddings(list[str]) → text_embed_blip

2) api.py
- Reemplazar get_clip_model por carga implícita en helpers BLIP.
- Donde se genera embedding de imagen/consulta, usar get_image_embedding / get_text_embeddings.
- Mantener cálculo de similitud por coseno (helpers.similarity) y el pipeline de fusión con atributos/color/tags.

3) diagnostic.py
- Sustituir generación de embeddings y scoring CLIP por los helpers BLIP.
- Mantener independencia por categoría y thresholds multi‑label.

4) calibration.py
- En el flujo de evaluación, usar helpers BLIP para generar scores multi‑label y calcular métricas (precision/recall/F1).
- Guardar nuevas sugerencias de thresholds.

5) categories.py y products.py
- Donde se regeneran embeddings de imágenes, usar get_image_embedding y setear image.clip_embedding = json.dumps(vec).

6) app.py / wsgi.py
- Eliminar precarga CLIP y logs relacionados.
- Si se desea, precarga BLIP opcional (load_model_blip on start) controlado por env o config.

7) models (image.py, category.py)
- Sin cambios de esquema. Mantener métodos auxiliares que leen/escriben clip_embedding/centroid_embedding.
- Opcional: ajustar docstrings y logs para quitar menciones a CLIP.

8) tools/ y tests/
- Actualizar scripts de prueba/diagnóstico que importaban CLIP directamente para que utilicen BLIP o llamen a endpoints.

## 7. Re‑embedding masivo (job local)

Objetivo: regenerar embeddings BLIP para todas las imágenes activas.

Pseudocódigo del job:
- Query imágenes activas por cliente (o todas).
- Para cada imagen:
  - vec = image_embed_blip(url)
  - image.clip_embedding = json.dumps(vec)
  - image.is_processed = True
- Commit por lotes (p.ej., cada 200 imágenes) con reintentos.
- Métricas: conteo total, procesadas, fallidas, tiempo medio por imagen.

Recomendaciones:
- Tamaño de imagen: 224/256; batch=1–2 en CPU.
- Registrar errores por URL (404, timeouts, formatos inválidos) y continuar.

## 8. Recalcular centroides BLIP

- Usar Category.recalculate_all_centroids(force=True) tras completar re‑embedding.
- Verificar logging: total, updated, skipped, errors.
- Para categorías sin imágenes procesadas, el centroide queda NULL.

## 9. Calibración y thresholds (BLIP)

- Ejecutar el módulo de calibración existente con BLIP activo.
- Métricas por categoría: TP/FP/FN/TN, precision/recall/F1.
- Estrategia por defecto: f1_optimal; exportar resultados y aplicar thresholds.
- Guardar en BD y actualizar Category.confidence_threshold.

## 10. Rendimiento y parámetros

- Device: cuda si disponible; caso contrario cpu.
- Tamaño imagen (configurable): 224 o 256.
- Batch: 1–2 en CPU para evitar picos de RAM.
- Cache de modelo: una sola instancia en memoria; descargar recursos si hay inactividad (opcional).

## 11. Calidad y validación (QA)

Criterios de aceptación:
- /api/search y diagnóstico responden sin errores y con latencias similares o aceptables en local.
- Recall de categorías secundarias en multi‑label ≥ que con la última calibración CLIP.
- Recalibración aplicada con éxito; categorías con thresholds BLIP coherentes.
- Centroides calculados y sin errores de deserialización.

Pruebas sugeridas:
- A/B en dataset de calibración: comparar detecciones anteriores vs BLIP.
- Casos problemáticos (CAMISAS/CHALECOS): verificar mejoras en presencia simultánea.
- Búsqueda textual híbrida: confirmar efecto de atributos/tags.

## 12. Despliegue local (operación)

Pasos recomendados (PowerShell, Windows):

1) Instalar dependencias (opcional si ya están):
```
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Primera carga de modelo (se descarga a caché de HuggingFace):
- Ocurre al primer uso de load_model_blip().

3) Re‑embedding BLIP (job):
- Ejecutar el script local preparado (tools/reembed_blip.py) por cliente o global.

4) Recalcular centroides:
- Invocar el utilitario o endpoint existente que llama Category.recalculate_all_centroids(force=True).

5) Calibración UI:
- Desde el panel de calibración, ejecutar corrida, revisar métricas y aplicar thresholds.

6) Validar endpoints de búsqueda y diagnóstico.

## 13. Rollback

- Revertir commits de migración con Git a la versión con CLIP.
- No hay cambios de esquema, por lo que no se requiere migración inversa de BD.

## 14. Limpieza: remover CLIP

Eliminar o reescribir:
- Imports y funciones CLIP en embeddings.py.
- Precarga y logs CLIP en app.py y wsgi.py.
- Referencias/strings de logging que mencionen CLIP en api.py/diagnostic/calibration.
- Tests/scripts que importan clip directamente (test_text_search.py, debug_image_embeddings.py, etc.).
- Documentación con mención a CLIP; actualizar a terminología genérica o BLIP.

## 15. Observaciones y riesgos

- Latencia CPU: mayor que CLIP en algunos escenarios; mitigado con imagen 224/256 y batch 1–2.
- Cambio de escala/dimensión del embedding: con L2 + coseno es estable; recalibración es obligatoria.
- Descarga inicial del modelo: requiere conectividad; luego opera en caché.

## 16. Roadmap opcional (posterior)

- Renombrar campos a nombres genéricos (image_embedding, centroid_embedding) para quitar legado semántico.
- Añadir vector DB (pgvector) y/o índices ANN para escalabilidad.
- Re‑rank avanzado (por ahora fuera de alcance local).

## 17. Anexos

### 17.1 Mapeo de reemplazos (conceptual)
- from app.blueprints.embeddings import get_clip_model → (eliminar). Se usa load_model_blip() internamente en helpers.
- generate_clip_embedding(image_url, image_obj) → get_image_embedding(image_url)
- Uso de image.clip_embedding: se mantiene; ahora contiene BLIP.
- Uso de Category.generate_clip_prompt: se mantiene como generador de prompt en inglés (renombrable más adelante).

### 17.2 Modelos BLIP alternativos (HuggingFace)
- Salesforce/blip-itm-base-coco (ViT-B/16): balance precisión/latencia.
- Salesforce/blip-itm-large-coco (ViT-L/16): mayor costo, no recomendado en CPU.

---

Checklist de finalización:
- [ ] embeddings.py migrado a BLIP y helpers neutrales.
- [ ] api/diagnostic/calibration/categories/products referencian helpers BLIP.
- [ ] Re‑embed ejecutado y persistido en images.clip_embedding.
- [ ] Centroides recalculados en categories.centroid_embedding.
- [ ] Calibración BLIP aplicada (thresholds por categoría).
- [ ] Limpieza de código/strings CLIP completada.
- [ ] Docs actualizados.
