# Reglas de Exclusión de Pares de Categorías

## Objetivo
Resolver ambigüedades cuando dos categorías visualmente similares tienen scores muy cercanos, seleccionando automáticamente la más apropiada según evidencia visual regional.

## Caso de Uso Principal: Delantales
Problema: "Delantal Completo" y "Medio Delantal" pueden tener scores cercanos (diferencia <10%) porque CLIP detecta señales mixtas (pechera visible pero también cintura fuerte).

Solución: Regla `torso_evidence` que examina:
- **torso_full**: max(chest_focus, upper_torso) ponderado del Delantal Completo
- **waist_half**: lower_50 ponderado del Medio Delantal
- **gap**: diferencia absoluta de scores finales

### Lógica de Decisión
```python
# Pseudo-código simplificado
if abs(score_full - score_half) <= tie_margin:
    # Empate técnico: usar evidencia regional
    if torso_full >= waist_half + torso_advantage_min:
        elegir("Delantal Completo", reason="torso_evidence")
    else:
        elegir("Medio Delantal", reason="waist_evidence")
elif score_full > score_half:
    elegir("Delantal Completo", reason="higher_score")
else:
    # Override suave: si hay evidencia fuerte de torso y gap es pequeño
    if (score_half - score_full) <= override_gap_max and \
       torso_full >= torso_evidence_min and \
       (torso_full - waist_half) >= torso_advantage_min:
        elegir("Delantal Completo", reason="torso_override")
    else:
        elegir("Medio Delantal", reason="higher_score")
```

## Parámetros
### Valores por Defecto (system_config.json)
```json
{
  "pair_exclusion_rules": {
    "apply_pair_exclusion_default": true,
    "delantal": {
      "override_gap_max": 0.10,
      "torso_evidence_min": 0.24,
      "torso_advantage_min": 0.06,
      "suppression_evidence_threshold": 0.22,
      "tie_margin": 0.02
    }
  }
}
```

### Valores por Cliente (CategoryPairExclusion)
Cada cliente puede tener reglas personalizadas con parámetros ajustados a su catálogo.

## Extensión a Nuevos Pares
Para agregar otro par (e.g., "Camisa Manga Larga" vs "Camisa Manga Corta"):

1. **Identificar crops distintivos**: ¿Qué región visual separa ambas? (e.g., `left_50` / `right_50` para mangas)
2. **Ajustar ponderaciones**: En `detect_categories_multi_crop`, definir region_weights específicos
3. **Crear regla**: En CategoryPairExclusion, tipo `sleeve_evidence` con parámetros análogos
4. **Implementar lógica**: Añadir bloque condicional en la sección de exclusión de pares

## Logs y Auditoría
Cada decisión de exclusión se registra con:
- `reason`: 'torso_evidence', 'waist_evidence', 'torso_override', 'higher_score'
- `torso_full`, `waist_half`, `gap`, `tie_margin`
- Cliente, imagen, categorías involucradas

JSONL diario en `logs/pair_exclusions_YYYYMMDD.jsonl`.

## Panel Admin
- Ruta: `/categories/exclusions`
- Funciones: crear, editar, desactivar reglas
- Vista de decisiones recientes con filtro por cliente y fecha

## Métricas
- % de casos con ambos pares candidatos
- Distribución de `reason` (qué regla se aplicó)
- Errores (casos donde la decisión fue incorrecta según feedback manual)

## Calibración
Ajustar umbrales basándose en:
- **override_gap_max**: si muchos falsos positivos, bajar a 0.08
- **torso_evidence_min**: si muchos medios incorrectos, subir a 0.26
- **torso_advantage_min**: margen de confianza, ajustar según varianza

## Referencias
- `app/blueprints/embeddings.py`: función `detect_categories_multi_crop`
- `app/models/category_pair_exclusion.py`: modelo de reglas
- `app/blueprints/category_exclusions.py`: blueprint admin
- `system_config.json`: configuración global
