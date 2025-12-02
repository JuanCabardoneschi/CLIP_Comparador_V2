# Plan de Analíticas de Términos y Atributos (Diciembre 2025)

## Objetivo
- Mejorar la trazabilidad de búsquedas de texto para que cada consulta cuente correctamente en `search_logs` y alimente los paneles.
- Población consistente del panel “Términos/Atributos más buscados (Sin Match)”.
- Incorporar métricas de atributos a nivel clave/valor para análisis de eficiencia (opcional con migración).

## Estado actual (resumen)
- Inserciones en `search_logs` restablecidas para `search_type='text'` y `had_results` correcto.
- Panel de “Términos sin match” vacío por cómo se registran actualmente `terms_*`.
- Enriquecimiento `top_5_productos` estable tras fix de `tag_matches_map`.

## Alcance
- Fase 1 (sin migraciones): Ajuste rápido de cómo se completan `terms_extracted`, `terms_matched`, `terms_unmatched`.
- Fase 2 (con migración opcional): Nuevos campos para métricas de atributos y actualización de dashboard.

---

## Fase 1 — Ajuste rápido de términos (sin migraciones)
**Objetivo:** Población inmediata del panel “Términos sin match” sin cambios de esquema.

### Cambios
- `terms_extracted`: todos los modificadores extraídos del texto (normalizados).
- `terms_matched`: subconjunto de `terms_extracted` que se mapean a atributos/valores (`atributos_encontrados`).
- `terms_unmatched`: `modificadores_no_configurados` incluso si hubo resultados.

### Criterios de aceptación
- Cada búsqueda de texto crea una fila con `search_type='text'` y completa `terms_*` según reglas.
- El panel “Términos sin match” muestra datos al menos para el día de validación.
- No se rompen métricas ya existentes (categorías detectadas, had_results, results_count).

### Tareas
- [ ] Ajustar asignación de `terms_*` en `clip_admin_backend/app/blueprints/search_text.py`.
- [ ] Pushear a `main` y esperar deploy en Railway.
- [ ] Validar con 1-2 consultas reales que se incrementa el total diario y se puebla “Sin Match”.

### Comandos útiles
- Probar la API (PowerShell):
  ```powershell
  $body = @{ query = "delantal negro" } | ConvertTo-Json
  Invoke-RestMethod -Method Post -Uri "https://clipcomparadorv2-production.up.railway.app/api/search/text" -Headers @{ "X-API-Key" = "<API_KEY>" } -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 6
  ```
- Consultar inserciones (usar herramienta de BD del repo):
  ```powershell
  python .\railway_db_tool.py sql -e "SELECT COUNT(*) FROM search_logs WHERE search_type='text' AND created_at::date = CURRENT_DATE;"
  python .\railway_db_tool.py sql -e "SELECT created_at, query_text, terms_unmatched FROM search_logs WHERE search_type='text' ORDER BY created_at DESC LIMIT 10;"
  ```

---

## Fase 2 — Métricas de atributos (con migración opcional)
**Objetivo:** Analizar eficiencia de detección de atributos (claves y valores) y descubrir brechas por categoría.

### Diseño de esquema (SearchLog)
- `attributes_detected_keys` (text[]): claves de atributos detectadas en la query.
- `attributes_matched_keys` (text[]): claves efectivamente mapeadas a atributos de catálogo.
- `attributes_uncovered_keys` (text[]): claves detectadas sin configuración o sin match.
- Opcional: `attribute_values_detected` (jsonb): mapa clave → valores detectados (para análisis finos).

### Tareas
- [ ] Especificar tipos y compatibilidad (nullable, default) y documentar.
- [ ] Crear migración SQL (ALTER TABLE) y actualizar modelo `SearchLog`.
- [ ] Completar logging en `search_text.py` para poblar los nuevos campos.
- [ ] Actualizar consultas/visualizaciones del dashboard (eficiencia por atributo y uncovered).
- [ ] Backfill opcional: script para derivar métricas desde datos recientes.

### Criterios de aceptación
- Nuevos campos presentes y poblados para búsquedas nuevas de texto.
- Consultas de dashboard muestran:
  - Top atributos detectados, top atributos sin cover, eficiencia por categoría.
- Backward compatible: endpoints y paneles existentes no fallan sin backfill.

### Riesgos y mitigación
- Cambio de esquema: aplicar primero en entorno de prueba; usar columnas nullable.
- Complejidad de backfill: limitarlo a N días y marcar como opcional.

### Consultas SQL de verificación (ejemplos)
```sql
-- Términos sin match (diario)
SELECT unnest(terms_unmatched) AS term, COUNT(*)
FROM search_logs
WHERE search_type='text' AND created_at::date = CURRENT_DATE
GROUP BY term
ORDER BY COUNT(*) DESC
LIMIT 50;

-- Eficiencia de atributos (si Fase 2 activa)
SELECT k, SUM(CASE WHEN k = ANY(attributes_matched_keys) THEN 1 ELSE 0 END) AS matched,
       SUM(CASE WHEN k = ANY(attributes_uncovered_keys) THEN 1 ELSE 0 END) AS uncovered
FROM (
  SELECT unnest(attributes_detected_keys) AS k, attributes_matched_keys, attributes_uncovered_keys
  FROM search_logs
  WHERE search_type='text' AND created_at >= NOW() - INTERVAL '7 days'
) t
GROUP BY k
ORDER BY matched DESC;
```

---

## Cronograma y responsables
- Fase 1: 0.5 día (ajuste + validación).
- Fase 2: 1.5–2.5 días (diseño, migración, logging, dashboard, backfill opcional).
- Responsables: a definir (dev backend + soporte datos/dashboard).

## Checklist global
- [ ] Confirmar deploy Railway y verificar inserción en producción.
- [ ] Fase 1 completa y panel “Sin Match” con datos.
- [ ] Fase 2: esquema aplicado, logging activo y dashboard actualizado.
- [ ] Documentación y pruebas en repo actualizadas.
