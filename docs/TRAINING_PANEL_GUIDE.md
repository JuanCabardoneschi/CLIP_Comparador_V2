# Guía de Uso: Panel de Entrenamiento Visual

## ¿Qué es y para qué sirve?

El panel de **Entrenamiento Visual** te permite enseñarle al sistema a distinguir entre diferentes subtipos dentro de una misma categoría de productos.

**Ejemplo práctico:** Si tu catálogo tiene "Delantales", el sistema detecta automáticamente esa categoría. Pero si querés que aprenda a diferenciar:
- Medio delantal (solo cintura)
- Delantal pechera (completo)
- Delantal utilitario (con bolsillos grandes)

...entonces creas **variantes** usando este panel.

---

## Flujo básico de entrenamiento

### 1. Preparar imágenes de referencia
- **10-15 fotos** del subtipo que querés entrenar (ej. medios delantales).
- **Importante para prendas que se usan CON otras (delantales, chalecos, etc.):**
  - Las fotos SIEMPRE van a tener otras prendas (ej. modelo con remera + medio delantal).
  - Esto es normal y esperado: un delantal solo sin persona es solo tela.
  - Por eso es CRÍTICO usar "Forzar categoría" (ver paso 3).
- Variá fondos, colores, ángulos para robustez.

### 2. Acceder al panel
**Ubicación:** Menú lateral → "Entrenamiento Visual"

### 3. Configuración inicial
1. **Cliente:** Seleccioná tu cliente (o ya aparece si sos Store Admin).
2. **Categoría:**
   - **OPCIÓN A (recomendada para entrenamiento):** Seleccionar categoría y activar **"Forzar categoría seleccionada"**.
   - **Por qué es crítico:** Las prendas como delantales, chalecos, etc. SIEMPRE se fotografían con otras prendas (modelo con remera + delantal). Sin forzar, el sistema detectaría la prenda superior (remera). Con forzar, buscás SOLO en la categoría correcta (delantales).
   - **OPCIÓN B:** Dejar vacío para autodetección (solo útil si la prenda está sola/aislada, poco común en catálogos reales).
3. **Imagen:** Arrastrá o seleccioná una foto del subtipo objetivo (ej. medio delantal con modelo).

### 4. Buscar productos similares
- Clic en **"Buscar Productos Similares"**.
- El sistema trae hasta **40 resultados** (aumentado para entrenamiento).

### 5. Etiquetar resultados
**Marcar positivos (✓):**
- Productos que SÍ son del subtipo buscado (ej. medios delantales).

**Marcar negativos (✗):**
- Productos que NO son del subtipo (ej. delantales completos, otras prendas).

**Regla de oro:** Necesitás mínimo **8-10 positivos** y **8-10 negativos** para crear una variante útil.

### 6. Crear la variante
1. Clic en **"+ Nueva"** (botón al lado del selector de variantes).
2. **Nombre de la Variante:** Texto descriptivo legible (ej. "Medio delantal").
3. **Clave:** Identificador único en minúsculas y guiones (ej. "medio-delantal").
   - **Importante:** Una vez creada, no cambies la clave (se usa para registrar historial).
4. Clic en **"Guardar"**.

### 7. Asignar entrenamiento a la variante
- En el selector "Asignar a Variante", elegí la variante recién creada.
- Clic en **"Guardar Entrenamiento"**.

### 8. Recalcular variantes
- Clic en **"Recalcular Variantes"**.
- El sistema calcula el **centroide** (promedio de embeddings) de los ejemplos positivos.
- Este centroide se usa para aplicar un **boost** en búsquedas futuras.

### 9. Iterar (refinamiento)
- Subir 3-5 imágenes más del mismo subtipo.
- Repetir pasos 4-8.
- Cada iteración mejora el centroide y hace el boost más preciso.

---

## ¿Cuándo usar "Forzar categoría"?

### USAR cuando:
- La imagen tiene **varias prendas** (ej. chaqueta + delantal) y querés entrenar solo una.
- Estás entrenando un subtipo específico y no querés que el sistema "adivine" otra categoría.
- Querés control total sobre qué categoría entrenar.

### NO USAR (dejar autodetección) cuando:
- La imagen tiene **una sola prenda clara**.
- Estás explorando resultados sin intención de entrenar aún.
- Confiás en que el sistema detecte correctamente.

---

## Estrategia recomendada: Entrenamiento progresivo

### Fase 1: Semilla (primera ronda)
- **10-12 imágenes** del subtipo.
- Etiquetar positivos/negativos.
- Crear variante.
- Recalcular.

### Fase 2: Validación (segunda ronda)
- **5-8 imágenes** nuevas (casos difíciles o atípicos).
- Marcar positivos/negativos.
- Guardar en la misma variante.
- Recalcular.

### Fase 3: Refinamiento (tercera ronda)
- **3-5 imágenes** con contextos variados (fondos distintos, ángulos extremos).
- Repetir ciclo.
- En este punto, el boost ya es robusto.

---

## Campos del modal "Nueva Variante"

### Nombre de la Variante
- **Ejemplo:** "Medio delantal", "Delantal pechera".
- **Uso:** Etiqueta visible para humanos en el panel.

### Clave (identificador interno)
- **Ejemplo:** "medio-delantal", "bib", "waist".
- **Formato:** Solo letras minúsculas, números y guiones (sin espacios ni tildes).
- **Uso:**
  - Asociar eventos de entrenamiento.
  - Identificar el centroide en la base de datos.
  - Aplicar boosts de similitud en búsquedas.
- **Importante:** Una vez creada, NO cambies la clave (rompe el historial de entrenamiento).

---

## Resultados esperados

Después de entrenar una variante con 10-15 ejemplos positivos:
- **Búsquedas con imágenes** del subtipo entrenado suben en ranking los productos correctos.
- El boost es **suave** (actualmente ~5%) para no distorsionar otras búsquedas.
- Cada nueva iteración de entrenamiento refuerza el centroide.

---

## Errores comunes

### 1. Entrenar con pocas imágenes (< 5)
**Problema:** Centroide débil, boost ineficaz.
**Solución:** Mínimo 8-10 positivos.

### 2. Usar imágenes con mezcla de categorías sin "Forzar categoría"
**Problema:** El sistema detecta la prenda dominante (chaqueta) en vez de la que querés entrenar (delantal).
**Solución:** Activar "Forzar categoría seleccionada".

### 3. Cambiar la "Clave" de una variante existente
**Problema:** Se pierde el historial de entrenamiento y los eventos previos quedan huérfanos.
**Solución:** Crear una nueva variante con otra clave.

### 4. No recalcular después de guardar entrenamiento
**Problema:** El centroide no se actualiza, el boost no se aplica.
**Solución:** Siempre hacer clic en "Recalcular Variantes" tras cada tanda.

---

## Preguntas frecuentes

### ¿Puedo entrenar varias variantes en la misma categoría?
Sí. Ejemplo: "Medio delantal" (clave: medio-delantal) y "Delantal pechera" (clave: bib).

### ¿Las variantes afectan otras categorías?
No. Cada variante está ligada a una categoría específica.

### ¿Cuánto tiempo lleva entrenar una variante útil?
- Fase semilla (10 imágenes): ~10 minutos.
- Total con 2-3 iteraciones: ~30 minutos.

### ¿El entrenamiento afecta al widget público?
Sí, pero solo aplica un boost suave. Las búsquedas sin variante siguen funcionando normalmente.

### ¿Qué hago si los resultados no mejoran?
- Verificar que recalculaste variantes tras cada entrenamiento.
- Asegurar que los positivos son realmente del subtipo (revisar manualmente).
- Añadir más ejemplos (iteración 3-4).

---

## Resumen ejecutivo

1. **Preparar 10-15 fotos** del subtipo (recordar: prendas como delantales SIEMPRE se fotografían con otras prendas).
2. **SIEMPRE forzar categoría** cuando entrenás subtipos de prendas que se usan con otras (delantales, chalecos, etc.).
3. **Buscar** → **Marcar 8-10 positivos y 8-10 negativos** → **Crear variante** → **Guardar entrenamiento** → **Recalcular**.
4. **Iterar** 2-3 veces para refinar.
5. **Verificar** que el boost mejora los rankings en búsquedas reales.

**Clave:** El sistema aprende patrones discriminantes (ej. delantal sin pechera vs con pechera) aunque haya otras prendas. Por eso forzar categoría es crítico.

---

**Última actualización:** 7 de noviembre de 2025
