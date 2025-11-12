# Sistema Multi-Crop y Generalización (Diseño Propuesto)

> Estado: BORRADOR INICIAL – Ajustes “clavados” para validar idea antes de hacerla configurable.

## 1. Objetivo
Mejorar la discriminación entre categorías visualmente similares (ej. Delantal Completo vs Medio Delantal) usando múltiples recortes (crops) estratégicos, reglas de supresión y prompts enriquecidos, manteniendo baja complejidad para usuarios no técnicos (vendedores de ropa).

## 2. Situación Actual
- Crops usados: `full`, `center_60`, `upper_50`, `lower_50`, `left_50`, `right_50`, añadidos: `upper_torso`, `chest_focus`.
- Reglas ad hoc:
  - Si “Delantal Completo” gana con evidencia en `upper_torso` o `chest_focus` y margen > 0.06 ⇒ suprimir “Medio Delantal”.
  - Suprimir headwear (gorros/gorras) si score en crops superiores < 0.15.
- Prompts dinámicos in-memory para tres categorías críticas.

Limitaciones: hardcode en código, no reutilizable para otros pares de categorías o clientes con nombres diferentes.

## 3. Principios de Generalización
1. **Perfiles de región**: Cada categoría define dónde están sus rasgos clave:
   - `torso`, `waist`, `full_body`, `head`, `foot`.
2. **Selección dinámica de crops**: Generar sólo los necesarios según unión de perfiles de categorías activas.
3. **Relaciones exclusivas configurables**: Pares de categorías mutuamente excluyentes con condiciones de supresión.
4. **Enriquecimiento de prompts** persistente, no inline, para reproducibilidad.
5. **Reglas simples primero**, sin introducir modelos de detección avanzados hasta que métricas lo exijan.

## 4. Estructuras Propuestas
### 4.1 Nuevos Campos en `Category`
| Campo | Tipo | Propósito |
|-------|------|-----------|
| `region_profile` | enum (string) | Indicar perfil visual dominante. |
| `suppression_group` | string/null | Agrupar categorías exclusivas. |
| `auto_prompt_enriched` | bool | Indicar si prompt fue enriquecido. |
| `visual_priority` | int | Orden relativo para desempate. |

### 4.2 Tabla / JSON `category_relations` (futuro)
```json
{
  "relations": [
    {
      "primary_id": "uuid-delantal-completo",
      "secondary_id": "uuid-medio-delantal",
      "type": "exclusive",
      "min_margin": 0.06,
      "evidence_crops": ["upper_torso", "chest_focus"],
      "min_evidence_score": 0.20,
      "reason_code": "bib_detected"
    }
  ]
}
```

## 5. Pipeline de Detección Generalizada (Meta)
1. Cargar categorías activas.
2. Reunir perfiles → generar set final de crops.
3. Calcular embeddings por crop.
4. Scoring por categoría (prompt fijo + embeddings normalizados).
5. Aplicar reglas exclusivas (consultar `category_relations`).
6. Suprimir ruido por heurísticas de evidencia regional.
7. Retornar lista estructurada: detectadas, suprimidas, candidatos ruido.

## 6. Panel Simplificado para Usuarios
En lugar de exponer toda la configuración técnica:
- Checkbox “Estas dos categorías chocan” → internamente crea relación exclusive.
- Selector simple de “Región principal” (dropdown). Explicaciones breves:
  - Torso (camisas, chaquetas, delantal completo)
  - Cintura (medios delantales, cinturones)
  - Cabeza (gorros, gorras)
  - Inferior (pantalones, calzado)
  - Completo (monos, vestidos largos)
- Botón “Mejorar prompt” que dispara enriquecimiento automático (traducción + features).

## 7. Métricas Clave a Medir Antes de Configuración Completa
| Métrica | Objetivo inicial |
|---------|------------------|
| Gap delantal completo vs medio | > 0.25 tras mejoras |
| Falsos positivos headwear sin cabeza visible | < 5% |
| Varianza score categoría correcta entre crops | < 0.10 |
| Tiempo promedio detección (8 crops) | < 1.2s CPU |
| Aciertos Top-1 en lote de prueba | +5 puntos vs baseline single crop |

## 8. Roadmap
Fase 0 (actual): Hardcode de reglas críticas (delantal, headwear). Log JSONL.
Fase 1: Documentar + agregar campos en modelo (sin usar todavía).
Fase 2: Implementar selección dinámica de crops por región_profile.
Fase 3: Persistencia y edición de relaciones exclusivas básicas en panel.
Fase 4: Enriquecimiento de prompts con LLM local y traducción guardado en BD.
Fase 5: Evaluación batch y posible migración embeddings multi-crop persistidos.

## 9. Riesgos y Mitigación
| Riesgo | Mitigación |
|--------|-----------|
| Complejidad para usuario final | Panel con etiquetas sencillas y help tooltips |
| Overfitting a pocas imágenes | Lote mínimo de validación por categoría (>10) antes de activar regla |
| Latencia por exceso de crops | Activar sólo crops relevantes por perfiles |
| Prompts demasiado largos | Límite 55 tokens + truncamiento controlado |

## 10. Próximos Pasos (Inmediatos si se aprueba)
- Añadir campos `region_profile`, `suppression_group` al modelo `Category` (sin lógica aún).
- Mantener reglas actuales “clavadas” hasta confirmar mejora consistente.
- Preparar script evaluación multicrop vs single-crop (CSV de pruebas internas).

## 11. Ejemplo de Salida Esperada (Compacta)
```json
{
  "detected": [
    {"id": "...", "name": "Delantal Completo", "score": 0.82, "best_crop": "upper_torso"},
    {"id": "...", "name": "Casaca", "score": 0.60, "best_crop": "left_50"}
  ],
  "suppressed": [
    {"id": "...", "name": "Medio Delantal", "raw_score": 0.24, "reason": "bib_detected"}
  ],
  "noise_candidates": [
    {"name": "Gorros", "raw_score": 0.19, "reason": "headwear_not_visible"}
  ]
}
```

## 12. Conclusión
El enfoque multi-crop + reglas ligeras muestra potencial para mejorar precisión en categorías visualmente próximas sin requerir modelos de detección pesada. La generalización controlada mediante perfiles y relaciones exclusivas permitirá escalar a múltiples clientes en forma manejable para usuarios no técnicos.

---
**Fin del documento.**
