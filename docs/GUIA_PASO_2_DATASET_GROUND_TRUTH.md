# 📚 Guía Paso 2: Crear Dataset de Ground-Truth

## ¿Qué es "ground-truth" y para qué sirve?

**Ground-truth** = "verdad de referencia" → Son ejemplos donde **TÚ** le dices al sistema cuál es la respuesta correcta.

En lugar de que el sistema "adivine" qué categorías detectar, tú le das casos reales con la respuesta correcta, y el sistema aprende a calibrarse.

---

## 🎯 Objetivo del Paso 2

Recolectar **30–50 imágenes representativas** de tu catálogo y etiquetar manualmente qué categorías deberían detectarse en cada una.

**Importante**:
- ✅ **No se suben ni guardan imágenes nuevas**
- ✅ Solo se guardan **referencias** (URLs) a imágenes que ya están en tu catálogo
- ✅ Las imágenes ya están en Cloudinary (de tus productos)
- ✅ Solo etiquetás qué categorías corresponden a cada una
- ⚠️ Una vez calibrado, podés **borrar el dataset** si querés (no se usa para nada más)

Esto permite:
1. Calcular thresholds óptimos por categoría (en lugar de usar 75% fijo para todas)
2. Ajustar pesos texto/centroid según qué funciona mejor
3. Medir métricas (precisión, recall) para ver si mejora o empeora
4. Identificar categorías problemáticas (ej: camisas que nunca se detectan)

---

## 🖼️ ¿Qué imágenes recolectar?

### Casos prioritarios (20 imágenes):
1. **Prendas compuestas** (lo que más falla ahora):
   - Delantal + camisa
   - Chaleco + camisa
   - Chaqueta + remera
   - Ambo (pantalón + casaca)
   - Cardigan + camisa

2. **Prendas individuales claras** (para baseline):
   - Delantal solo
   - Camisa sola
   - Chaleco solo
   - Zuecos solos
   - Gorra sola

3. **Casos edge** (difíciles):
   - Múltiples accesorios (gorra + barbijo + cofia)
   - Prendas similares (casaca vs chaqueta vs chaleco)
   - Colores muy distintos al entrenamiento
   - Ángulos no frontales

### ¿De dónde sacar las imágenes?

**Única opción: Desde tu catálogo vía UI**
1. Andá a: **Administración → Calibración → Dataset**
2. Click en **"Agregar Imágenes"**
3. Seleccioná la imagen que querés etiquetar
4. Seleccioná las categorías que se ven en la imagen (multi-selección con Ctrl+click)
5. Click en **"Importar Imagen Seleccionada"**

**¿Por qué solo del catálogo?**
- ✅ **No consumís storage ni API de Cloudinary** (las imágenes ya están)
- ✅ **Nombres de categorías exactos** (selector con tus categorías reales)
- ✅ **Evita duplicados automáticamente**
- ✅ **Representa tu distribución real** de productos
- ✅ **Más rápido** (no hay upload)

**¿Y si quiero casos que no están en mi catálogo?**
No hace falta. El objetivo es **calibrar para tus productos reales**, no para casos hipotéticos. Si una situación no está en tu catálogo, probablemente no sea relevante para tu negocio.

---

## ✍️ Cómo etiquetar (manual)

### Formato JSON simple:

Crea un archivo: `dataset/ground_truth_labels.json`

```json
{
  "images": [
    {
      "filename": "delantal_con_camisa_01.jpg",
      "path": "dataset/delantal_con_camisa_01.jpg",
      "expected_categories": [
        "Delantal Completo",
        "CAMISAS HOMBRE- DAMA"
      ],
      "notes": "Persona usando delantal verde con camisa blanca debajo, vista frontal"
    },
    {
      "filename": "chaleco_dama_02.webp",
      "path": "dataset/chaleco_dama_02.webp",
      "expected_categories": [
        "CHALECO DAMA- HOMBRE",
        "CAMISAS HOMBRE- DAMA"
      ],
      "notes": "Chaleco marrón sobre camisa blanca, modelo femenino"
    },
    {
      "filename": "delantal_solo_03.jpg",
      "path": "dataset/delantal_solo_03.jpg",
      "expected_categories": [
        "Delantal Completo"
      ],
      "notes": "Solo delantal sin persona, fondo blanco"
    },
    {
      "filename": "gorra_barbijo_04.jpg",
      "path": "dataset/gorra_barbijo_04.jpg",
      "expected_categories": [
        "GORROS- COFIAS",
        "BARBIJOS"
      ],
      "notes": "Persona con gorra verde y barbijo blanco"
    }
  ]
}
```

### Reglas de etiquetado:

1. **Usar nombres exactos** de categorías (como aparecen en tu BD)
   - Consulta: `python local_db_tool.py sql -e "SELECT name FROM categories WHERE client_id='XXX' ORDER BY name;"`

2. **Listar TODAS las categorías visibles**, no solo la principal

3. **Incluir prendas secundarias** (camisa, remera) aunque estén "abajo" del delantal/chaleco

4. **NO incluir categorías "imaginadas"**:
   - ❌ Si no ves pantalón en la imagen, no pongas "PANTALON HOMBRE"
   - ✅ Si solo ves torso con camisa, solo pon "CAMISAS HOMBRE-DAMA"

5. **Casos dudosos**: Agregar en `notes` y decidir después

---

## 🔧 Herramienta de etiquetado rápido (opcional)

Puedo crear un script interactivo:

```bash
python tools/label_dataset.py --dataset-dir dataset/

# Te muestra cada imagen y te pregunta:
# "¿Qué categorías ves? (separadas por coma)"
# > Delantal Completo, CAMISAS HOMBRE-DAMA
#
# Guarda automáticamente en ground_truth_labels.json
```

---

## 📊 ¿Cuántas imágenes necesito?

| Mínimo | Recomendado | Ideal |
|--------|-------------|-------|
| 20 | 30–50 | 100+ |

**Distribución sugerida:**
- 10 casos con categoría única (baseline)
- 15 casos con 2 categorías (principal + secundaria)
- 5 casos con 3+ categorías (ambos completos, accesorios)

### Por categoría:
- Categorías problemáticas (CAMISAS, CHALECOS): **mínimo 10 ejemplos cada una**
- Categorías raras (ZUECOS, GORROS): **mínimo 3 ejemplos**
- Categorías principales (DELANTAL): **mínimo 15 ejemplos**

---

## ✅ Checklist Paso 2

- [ ] Ir a **Administración → Calibración → Dataset**
- [ ] Click en **"Agregar Imágenes"**
- [ ] Seleccionar y etiquetar **30+ imágenes del catálogo**
- [ ] Asegurarte de cubrir:
  - [ ] 10+ casos con categoría única (baseline)
  - [ ] 15+ casos con 2 categorías (principal + secundaria)
  - [ ] 5+ casos con 3+ categorías (compuestos, accesorios)
- [ ] Verificar que categorías problemáticas (CAMISAS, CHALECOS) tengan **mínimo 10 ejemplos**

**Recordar**: No se sube nada, solo se marcan categorías en imágenes existentes.

---

## 🚀 Próximos pasos (después del Paso 2)

Una vez tengas el dataset etiquetado (30+ imágenes):

**Paso 3:** Ejecutar calibración desde la UI
1. Ir a **Administración → Calibración**
2. Click en botón **"Calibrar Thresholds"**
3. El sistema:
   - Corre el diagnóstico multi-label en cada imagen
   - Compara resultados con tu etiquetado manual
   - Calcula métricas (precisión, recall, F1) por categoría
   - Sugiere thresholds óptimos
   - Genera reporte visual con casos de fallo

**Paso 4:** Aplicar thresholds calibrados
1. Revisar métricas en el reporte de calibración
2. Click en **"Aplicar Thresholds Sugeridos"**
3. Los nuevos thresholds se guardan en cada categoría
4. Probar búsquedas en el diagnóstico para validar mejoras

---

## 💡 Ejemplo práctico

### Antes (sin calibración):
- Threshold fijo: 75% para todas las categorías
- CAMISAS nunca pasa threshold (score ML 74.4% < 75%)
- Resultado: Solo detecta chaleco, pierde camisa ❌

### Después (con calibración):
- Threshold CAMISAS: 65% (ajustado según tus ejemplos)
- Threshold DELANTAL: 80% (más estricto porque es muy claro)
- Threshold GORROS: 55% (más laxo porque tiene pocos ejemplos)
- Resultado: Detecta chaleco + camisa ✅

---

## ❓ Preguntas frecuentes

**P: ¿Se suben imágenes nuevas a Cloudinary?**
R: **NO**. Solo se guardan referencias (URLs) a imágenes que ya están en tu catálogo. Cero consumo de storage adicional.

**P: ¿Puedo borrar el dataset después de calibrar?**
R: **SÍ**. Una vez calibrado y aplicados los thresholds, el dataset no se usa más. Podés borrarlo si querés. Solo sirve para recalibrar en el futuro.

**P: ¿Y si mi catálogo tiene 200 productos?**
R: No necesitás 200 imágenes. Con 30–50 **variadas** (casos típicos + edge cases) alcanza para calibrar.

**P: ¿Esto entrena el modelo CLIP?**
R: **NO**. CLIP ya está entrenado. Esto solo **calibra thresholds** (la línea de corte para decidir si una categoría se detecta o no).

**P: ¿Puedo ir agregando imágenes después?**
R: ¡Sí! Es iterativo. Empieza con 20, calibra, prueba, agrega 10 más de casos que fallen, recalibra.

**P: ¿Qué pasa con las imágenes que agrego al dataset?**
R: Se guarda en BD:
- URL de la imagen (ya existente en Cloudinary)
- Categorías que TÚ marcaste como correctas
- Nada más. No hay duplicación de imágenes.

---

## 📧 Resumen ejecutivo

**Lo que hace este módulo:**
1. Seleccionás 30–50 imágenes de tu catálogo
2. Marcás qué categorías se ven en cada una (etiquetado manual)
3. El sistema evalúa cada imagen y compara con tu etiquetado
4. Sugiere thresholds óptimos por categoría
5. Aplicás los thresholds sugeridos

**Lo que NO hace:**
- ❌ No entrena modelos de IA
- ❌ No sube imágenes nuevas a Cloudinary
- ❌ No guarda copias de imágenes
- ❌ No consume storage adicional

**Beneficio:**
En vez de 75% fijo para todas las categorías, tenés thresholds personalizados:
- CAMISAS: 65% (más laxo, porque es difícil de detectar)
- DELANTAL: 80% (más estricto, porque siempre es claro)
- GORROS: 55% (laxo, porque hay pocos ejemplos)

Resultado: **Mejor detección multi-label sin falsos positivos**.

---

**Siguiente:** Una vez tengas el dataset etiquetado (30+ imágenes), ejecutá **Paso 3: Calibración automática** desde la UI 🎯
