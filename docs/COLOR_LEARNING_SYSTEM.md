# Sistema de Aprendizaje de Colores

## Objetivo
Permitir que el sistema se adapte automáticamente a los colores usados por cada cliente, sin necesidad de hardcodear nuevos colores para cada caso.

## Arquitectura

### 1. Tabla `color_mappings`
```sql
CREATE TABLE color_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    raw_color VARCHAR(100) NOT NULL,      -- Color tal como está en el producto
    normalized_color VARCHAR(50),          -- Color normalizado por LLM
    similarity_group VARCHAR(50),          -- Grupo de similitud (ej: "NARANJA")
    usage_count INTEGER DEFAULT 1,
    confidence FLOAT,                      -- Confianza del LLM (0-1)
    last_used_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(client_id, raw_color)
);

CREATE INDEX idx_color_mappings_client ON color_mappings(client_id);
CREATE INDEX idx_color_mappings_usage ON color_mappings(client_id, usage_count DESC);
```

### 2. Flujo de trabajo

#### Primera vez que aparece un color
1. Usuario crea producto con color "coral vibrante"
2. Sistema busca en `color_mappings` para ese cliente
3. No existe → LLM normaliza a "CORAL"
4. Sistema busca colores similares en la BD del cliente
5. Si encuentra match (LLM > 0.85), asigna al mismo `similarity_group`
6. Guarda en `color_mappings`:
   ```json
   {
     "raw_color": "coral vibrante",
     "normalized_color": "CORAL",
     "similarity_group": "NARANJA",  // Si encontró "salmón" previamente
     "usage_count": 1,
     "confidence": 0.92
   }
   ```

#### Usos subsecuentes
1. Usuario usa "coral vibrante" en otro producto
2. Sistema consulta `color_mappings` → encuentra match instantáneo
3. Incrementa `usage_count`, actualiza `last_used_at`
4. No necesita llamar al LLM de nuevo

#### Búsqueda visual
1. CLIP detecta "CORAL"
2. Sistema busca en `color_mappings` todos los colores del grupo "NARANJA"
3. Aplica boost a productos con "coral", "salmón", "durazno", etc.

### 3. Panel de administración (futuro)

**Ruta:** `/clients/{id}/colors`

**Funcionalidades:**
- Ver todos los colores usados por el cliente
- Ver agrupaciones automáticas
- Editar/corregir grupos manualmente
- Mergear grupos ("coral" + "salmón" → "NARANJA")
- Ver estadísticas de uso

**Mockup:**
```
┌─────────────────────────────────────────────────┐
│ Colores de Demo Fashion Store                  │
├─────────────────────────────────────────────────┤
│                                                 │
│ Grupo: NARANJA (3 colores)                     │
│   • Coral vibrante (12 productos) [editar]     │
│   • Salmón (8 productos)                        │
│   • Durazno (3 productos)                       │
│                                                 │
│ Grupo: AZUL (5 colores)                         │
│   • Azul marino (45 productos)                  │
│   • Azul celeste (23 productos)                 │
│   • Jean (18 productos)                         │
│   • Denim (15 productos)                        │
│   • Petróleo (2 productos)                      │
│                                                 │
│ Sin grupo (sugerencias):                        │
│   • Fucsia eléctrico (1 producto)               │
│     → ¿Agrupar con ROSA? [Sí] [No]             │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 4. API endpoints

#### Obtener colores del cliente
```
GET /api/clients/{client_id}/colors
Response:
{
  "groups": [
    {
      "name": "NARANJA",
      "colors": [
        {"raw": "coral vibrante", "count": 12},
        {"raw": "salmón", "count": 8}
      ]
    }
  ],
  "ungrouped": [
    {"raw": "fucsia eléctrico", "count": 1, "suggested_group": "ROSA"}
  ]
}
```

#### Actualizar agrupación
```
POST /api/clients/{client_id}/colors/group
Body:
{
  "colors": ["coral vibrante", "salmón", "durazno"],
  "group": "NARANJA"
}
```

## Migración gradual

1. **Fase 1 (actual):** Grupos hardcoded + LLM fallback
2. **Fase 2:** Auto-aprendizaje en background (sin UI)
3. **Fase 3:** Panel de administración para clientes avanzados
4. **Fase 4:** Sugerencias automáticas basadas en uso

## Ventajas del sistema

✅ **Escalable:** Funciona con 10 o 10,000 clientes
✅ **Auto-adaptable:** Aprende los colores de cada cliente
✅ **Sin mantenimiento:** No requiere updates de código
✅ **Performante:** Colores frecuentes son instantáneos
✅ **Flexible:** Clientes pueden afinar manualmente si lo desean

## Ejemplo de uso

**Cliente nuevo: Tienda de ropa de playa**
- Usan colores: "coral", "turquesa caribeño", "arena", "verde agua"
- Sistema los detecta automáticamente
- Agrupa: coral → NARANJA, turquesa/verde agua → AZUL, arena → BEIGE
- En 1 semana, el sistema ya conoce su paleta completa
- No se requirió configuración manual

**Cliente avanzado: Fashion brand**
- Tienen 50+ colores específicos con nombres de marca
- Usan el panel para crear grupos personalizados
- Ej: "Midnight Blue Collection" + "Navy Signature" → Grupo "AZUL OSCURO"
- El sistema respeta sus agrupaciones manuales
