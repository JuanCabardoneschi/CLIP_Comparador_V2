# Backlog de Mejoras

## 🔹 Vocabulario por Cliente en BD (client_vocabulary_cache)
**Estado**: ✅ CERRADO
**Comentario**: Implementado y superado por sistema JSON configurable y admin UI. No requiere tabla ni hooks adicionales. Mapeo semántico de colores incluido.

---

## 🔄 1) Sistema de Recálculo Automático de Embeddings de Vocabulario
**Estado**: 🟡 Prioridad BAJA
**Comentario**: Parcialmente obsoleto. El sistema actual funciona con vocabulario estático y caching. Mantener solo si se detectan problemas de vocabulario desactualizado. Monitorear logs y reactivar si es necesario.

---

## 2) Sistema de Variantes de Colores Generadas por LLM
**Estado**: ❌ RECHAZADO
**Comentario**: No necesario. spaCy + mapeo semántico cubren variantes y sinónimos. Solo considerar LLM si se detectan casos no cubiertos o se requiere multi-idioma.

---

## 2) Búsqueda de Texto en Modo Multi-Categoría (futuro)
**Estado**: 🟡 Prioridad MEDIA
**Comentario**: Propuesta válida para queries ambiguas. Mantener como feature flag desactivado por defecto. Validar con cliente antes de implementar.

---

## 3) Normalización de Colores y Sinónimos (configurable)
**Estado**: 🟡 Parcialmente Completo
**Comentario**: Sistema actual cubre colores y sinónimos vía JSON y helpers. Falta exponer pesos/umbrales en config y admin UI. Prioridad baja, funciona correctamente.

---
