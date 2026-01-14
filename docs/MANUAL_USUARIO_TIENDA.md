# 📘 Manual de Usuario - Administrador de Tienda
## CLIP Comparador V2 - Sistema de Búsqueda Visual

---

## 📖 Introducción

### Objetivo del Sistema

**CLIP Comparador V2** es un sistema de búsqueda visual inteligente diseñado para potenciar la experiencia de compra de sus clientes. Permite que los usuarios encuentren productos en su catálogo de manera rápida e intuitiva, simplemente **subiendo una imagen o foto**.

#### ¿Por qué buscar por imagen?

En lugar de escribir palabras clave o navegar por categorías, sus clientes pueden:
- 📸 Fotografiar un producto que les interesa
- 🔍 Subirlo a la búsqueda visual
- ✨ Recibir productos similares al instante

Esto aumenta las conversiones, reduce el bounce rate y mejora la satisfacción del cliente.

---

### ¿Qué es lo que gestiona usted?

Como **Administrador de Tienda**, su rol es mantener el catálogo de productos correctamente configurado para que la búsqueda visual funcione de manera óptima. Sus tareas principales son:

| Tarea | Descripción |
|-------|-------------|
| **Crear Categorías** | Organizar sus productos en grupos temáticos (ej: Camisetas, Pantalones, Accesorios) |
| **Gestionar Productos** | Agregar, editar y eliminar productos con sus atributos (colores, tallas, precios, etc.) |
| **Cargar Imágenes** | Subir fotografías de productos que serán analizadas para la búsqueda visual |
| **Configurar Atributos** | Definir características dinámicas específicas de su negocio |
| **Monitorear Inventario** | Controlar el stock disponible de cada producto |
| **Ver Analytics** | Entender cómo buscan sus clientes y qué productos encuentran |

---

### Conceptos Clave

Antes de empezar, le recomendamos entender estos conceptos:

#### 🤖 CLIP (Contrastive Language-Image Pre-training)
Es la tecnología de IA que alimenta la búsqueda visual. Analiza las imágenes para entender su contenido visual (colores, formas, estilos) y permite encontrar productos similares. **No necesita hacer nada especial** - el sistema funciona automáticamente.

#### 📁 Categorías
Son grupos de productos similares. Cada categoría tiene su propia configuración de búsqueda. Las categorías bien definidas mejoran significativamente la precisión de resultados.

#### 🏷️ Atributos
Son características de sus productos: colores, tallas, materiales, precios, etc. Pueden ser:
- **Predefinidos**: Usted establece opciones fijas (ej: Colores = Rojo, Azul, Negro)
- **Dinámicos**: Los crea según su necesidad
- **Expuestos en búsqueda**: Algunos atributos aparecen como filtros en la búsqueda visual

#### 📦 Imágenes & Embeddings
Cada imagen de producto se analiza con CLIP para crear un "resumen visual" llamado **embedding**. Este embedding permite comparar productos por similitud visual. El sistema procesa esto automáticamente en segundo plano.

#### 📊 Analytics
Datos sobre cómo sus clientes usan la búsqueda visual. Le ayuda a entender qué funciona y qué no.

---

## 🎯 Flujo General de Uso

El workflow típico es:

```
1. PREPARAR TIENDA
   ├─ Crear Categorías
   ├─ Definir Atributos
   └─ Configurar Búsqueda

2. CARGAR PRODUCTOS
   ├─ Crear Productos
   ├─ Agregar Imágenes
   └─ Esperar Procesamiento de Embeddings

3. USAR Y MONITOREAR
   ├─ Ver Analytics
   ├─ Ajustar Inventario
   └─ Optimizar Configuración
```

---

## 📍 Dónde Encontrar Cada Función

Después de iniciar sesión, el menú lateral izquierdo muestra todas las secciones disponibles:

### Sección "Mi Tienda"
- **Mis Categorías** - Crear y organizar grupos de productos
- **Mis Productos** - Gestionar catálogo completo
- **Inventario** - Control de stock
- **Atributos** - Definir características de productos
- **Mis Embeddings CLIP** - Estado del procesamiento de imágenes
- **Analytics de Tienda** - Estadísticas de búsqueda

### Sección "Configuración"
- **Sincronización Tiendanube** - (Solo si está integrado con TiendaNube)
- **Configuración de Búsqueda** - Ajustar sensibilidad y umbrales
- **Perfiles de Búsqueda** - Crear variantes personalizadas de búsqueda
- **Mi API Key** - Ver datos técnicos de integración
- **Usuarios** - Gestionar otros administradores de tienda

---

## ✅ Requisitos Previos

Antes de empezar, asegúrese de tener:

- ✔️ Una **cuenta creada** en CLIP Comparador V2
- ✔️ Acceso con rol **Administrador de Tienda**
- ✔️ Acceso a las imágenes de sus productos (recomendado: 500x500px mínimo)
- ✔️ Información sobre sus productos (nombres, precios, características)

---

## 📞 Soporte y Ayuda

Si tiene preguntas mientras usa el sistema:
- Consulte las secciones específicas de este manual
- Verifique los **Apéndices** al final para configuración técnica
- Contacte al equipo de soporte (información en su dashboard)

---

## 📑 Contenido de Este Manual

1. **Dashboard Principal** - Comprenda la página de inicio
2. **Gestión de Categorías** - Cómo crear y organizar categorías
3. **Gestión de Productos** - Agregar, editar y eliminar productos
4. **Carga de Imágenes** - Fotografías para búsqueda visual
5. **Configuración de Atributos** - Características personalizadas
6. **Gestión de Inventario** - Control de stock
7. **Analytics y Reportes** - Entender el uso de búsqueda
8. **Configuración de Búsqueda** - Ajustes avanzados
9. **Perfiles de Búsqueda** - Búsqueda personalizada por perfil

### Apéndices
- **A. Integración TiendaNube** - Si usa TiendaNube
- **B. API Key y Configuración Técnica** - Para desarrolladores
- **C. Webhooks e Integraciones** - Conexiones externas
- **D. Preguntas Frecuentes** - Respuestas a dudas comunes
- **E. Referencia Rápida** - Accesos directos y atajos

---

### 🚀 ¿Listo para empezar?
Vaya a la siguiente sección: **[1. Dashboard Principal](#1-dashboard-principal)**

---

## Notas Importantes

- Las imágenes se procesan automáticamente en segundo plano (pueden tardar algunos minutos)
- Los cambios en productos y atributos se aplican inmediatamente
- Siempre puede editar o eliminar productos después de crearlos
- El sistema guarda automáticamente - no hay botón "Guardar" separado

---

# 1. Dashboard Principal

## 📊 ¿Qué es el Dashboard?

El **Dashboard** es la primera pantalla que ve al iniciar sesión. Es su centro de control personal donde se muestran las estadísticas más importantes de su tienda y accesos rápidos a las funciones principales.

Aquí puede:
- 👀 Ver de un vistazo el estado de su catálogo
- 🚀 Acceder rápidamente a tareas frecuentes
- 📈 Monitorear actividad (búsquedas, productos, imágenes)

---

## 🎨 Estructura del Dashboard

El dashboard está organizado en varias secciones:

### Encabezado de Bienvenida

```
🏪 Mi Tienda: [Nombre de su Tienda]
Panel de administración de mi catálogo
```

Muestra el nombre de su tienda y confirma que está en la vista de administrador.

---

## 📊 Tarjetas de Estadísticas

El dashboard muestra **4 tarjetas principales** con información en tiempo real:

### 1️⃣ Mis Productos
| Elemento | Descripción |
|----------|-------------|
| **Título** | Mis Productos |
| **Número** | Total de productos en su catálogo |
| **Subtítulo** | "En mi catálogo" |
| **Icono** | 📦 Caja |
| **Significado** | Cantidad total de productos que ha creado/importado |

**¿Qué incluye?**
- Productos activos e inactivos
- Productos vinculados a cualquier categoría

**Ejemplo:** Si ve "247", tiene 247 productos en total

---

### 2️⃣ Mis Imágenes
| Elemento | Descripción |
|----------|-------------|
| **Título** | Mis Imágenes |
| **Número** | Total de imágenes cargadas |
| **Subtítulo** | "Total cargadas" |
| **Icono** | 🖼️ Imágenes |
| **Significado** | Cantidad de fotografías subidas a todos los productos |

**¿Qué incluye?**
- Imágenes principales de productos
- Imágenes secundarias/adicionales

**Ejemplo:** Si ve "892", tiene 892 imágenes cargadas en total

---

### 3️⃣ Mis Embeddings
| Elemento | Descripción |
|----------|-------------|
| **Título** | Mis Embeddings |
| **Número** | Imágenes procesadas / Total de imágenes |
| **Porcentaje** | % de imágenes analizadas |
| **Icono** | ⚙️ Procesador |
| **Significado** | Qué porcentaje de sus imágenes ya fueron analizadas por CLIP |

**¿Qué significa?**
- **Embeddings** = "Análisis visual" de la imagen
- El sistema crea un "resumen" de cada imagen para poder compararla con búsquedas
- Este proceso es automático y ocurre en segundo plano

**Ejemplo:** Si ve "750 / 892 (84%)" significa:
- Tiene 892 imágenes
- 750 ya fueron analizadas
- Espere a que el 100% esté completo para resultados óptimos

**⏳ Nota de Paciencia:** Las imágenes pueden tardar minutos u horas en procesarse dependiendo de la cantidad. El sistema trabaja continuamente en segundo plano.

---

### 4️⃣ Búsquedas Hoy
| Elemento | Descripción |
|----------|-------------|
| **Título** | Búsquedas Hoy |
| **Número** | Cantidad de búsquedas visuales realizadas hoy |
| **Subtítulo** | "En mi tienda" |
| **Icono** | 🔍 Lupa |
| **Significado** | Cuántos clientes realizaron búsqueda visual en su tienda hoy |

**¿Qué indica?**
- Número de veces que clientes utilizaron la función de buscar por imagen
- Se reinicia cada día (medianoche)
- Ayuda a entender si está usando la búsqueda visual

**Ejemplo:** Si ve "34", significa que hoy 34 personas buscaron usando una imagen en su tienda

---

## ⚡ Acciones Rápidas

En la sección **"Acciones Rápidas"** encontrará 4 botones para llegar rápidamente a las funciones más usadas:

| Botón | Función | Ir a... |
|-------|---------|---------|
| 📦 **Gestionar Productos** | Crear, editar, eliminar productos | [Capítulo 3: Gestión de Productos](#3-gestión-de-productos) |
| ⚙️ **Procesar Embeddings** | Ver estado de análisis de imágenes | [Capítulo 5: Carga de Imágenes](#5-carga-de-imágenes) |
| 🏷️ **Mis Categorías** | Organizar productos en grupos | [Capítulo 2: Gestión de Categorías](#2-gestión-de-categorías) |
| 📊 **Ver Analytics** | Estadísticas de búsqueda | [Capítulo 7: Analytics](#7-analytics-y-reportes) |

**Tip:** Use estos botones como atajos para no tener que navegar por el menú lateral.

---

## 📍 Menú Lateral Izquierdo

Desde el dashboard también puede acceder al **menú lateral** que lista todas las secciones disponibles:

### Sección "Mi Tienda"
- **Mis Categorías** - Crear/editar grupos de productos
- **Mis Productos** - Gestión completa del catálogo
- **Inventario** - Control de stock
- **Atributos** - Características de productos
- **Mis Embeddings CLIP** - Estado del procesamiento
- **Analytics de Tienda** - Reportes de búsqueda

### Sección "Configuración"
- **Sincronización TiendaNube** - (Si está integrado)
- **Configuración de Búsqueda** - Ajustes de sensibilidad
- **Perfiles de Búsqueda** - Personalización por industria
- **Mi API Key** - Datos técnicos
- **Usuarios** - Gestionar otros admins

---

## 💡 Consejos de Uso

### ✅ Qué hacer regularmente

- **Cada semana:** Revise "Mis Embeddings" para asegurar que están al 100%
- **Cada día:** Verifique "Búsquedas Hoy" para ver si está siendo usado
- **Siempre que agregue productos:** Venga al dashboard a ver cómo crecen las estadísticas

### 🎯 Objetivos para optimizar

Para que la búsqueda visual funcione bien:
1. Tenga **todas sus imágenes procesadas** (100% en Embeddings)
2. Tenga sus productos **bien categorizados**
3. Tenga sus **atributos bien configurados**

Si cumple estos 3 puntos, sus clientes encontrarán exactamente lo que buscan.

---

## ⚠️ ¿Qué significan los números bajos?

| Caso | Interpretación | Acción |
|------|---|---|
| **Pocas imágenes** | Catálogo poco poblado | Agregue más productos/imágenes |
| **Embeddings bajo 100%** | Imágenes aún procesándose | Espere, el sistema está trabajando |
| **Búsquedas = 0** | Nadie ha usado búsqueda visual | Promueva esta función entre clientes |

---

## 🚀 Próximo Paso

Ahora que entiende el dashboard, el siguiente paso depende de dónde está:

- **Si NO tiene productos:** Vaya a [Capítulo 2: Gestión de Categorías](#2-gestión-de-categorías)
- **Si tiene productos SIN imágenes:** Vaya a [Capítulo 5: Carga de Imágenes](#5-carga-de-imágenes)
- **Si está todo configurado:** Vaya a [Capítulo 7: Analytics](#7-analytics-y-reportes)

---

---

# 2. Gestión de Categorías

## 📁 ¿Qué son las Categorías?

Las **categorías** son grupos de productos similares. Son la forma de **organizar su catálogo** para que tanto usted como sus clientes encuentren lo que buscan fácilmente.

### Ejemplos de Categorías
- Camisetas
- Pantalones
- Zapatos
- Accesorios
- Abrigos

Una buena estructura de categorías es **fundamental** para que la búsqueda visual funcione bien.

---

## 🎯 Por Qué son Importantes las Categorías

| Razón | Beneficio |
|-------|-----------|
| **Organización** | Sus productos están ordenados, no mezclados |
| **Búsqueda Mejorada** | CLIP puede comparar mejor dentro de la misma categoría |
| **Precisión** | "Una camiseta roja" busca SOLO en camisetas, no en todas las prendas |
| **Experiencia Cliente** | Los usuarios saben dónde buscar |
| **Mantenimiento** | Fácil de gestionar y actualizar |

---

## 📍 Acceso a Categorías

### Desde el Menú
En el menú lateral izquierdo, haga clic en:
```
🏪 MI TIENDA
  └─ 🏷️ Mis Categorías
```

### Desde el Dashboard
En la sección **Acciones Rápidas**, haga clic en:
```
🏷️ Mis Categorías
```

---

## 📋 Pantalla Principal de Categorías

La pantalla **"Mis Categorías"** le muestra un resumen completo:

### Tarjetas de Estadísticas

En la parte superior encontrará **4 números importantes**:

| Tarjeta | Significa |
|---------|-----------|
| 📊 **Total Categorías** | Cuántas categorías ha creado |
| ✅ **Activas** | Categorías disponibles para asignar productos |
| ⛔ **Inactivas** | Categorías desactivadas (ocultas) |
| 📦 **Con Productos** | Cuántas categorías tienen productos |

**Ejemplo:**
- Total: 10
- Activas: 10
- Inactivas: 0
- Con Productos: 8

Significa: Tiene 10 categorías, todas activas, 8 de ellas con productos asignados.

---

### Sección de Optimización de Búsquedas

Verá un **recuadro amarillo importante** con este título:
```
⚡ Optimización de Búsquedas
```

**¿Qué dice?**

Para mejorar la detección de categorías en búsquedas, es **fundamental** que cada cliente configure manualmente los **Términos Alternativos** de cada categoría según su inventario específico.

**¿Qué significa?**

- El sistema PUEDE generar términos automáticamente con IA, pero no son 100% precisos
- **Usted debe revisar y personalizar** los sinónimos y variantes en inglés para cada categoría
- Ejemplos: "remera" → "t-shirt, tee, shirt"

**¿Por qué?**

Porque cada tienda es diferente. Sus clientes usan palabras específicas de su rubro, región o estilo.

---

### Tabla de Categorías

En el centro de la pantalla, verá una **tabla con todas sus categorías**:

#### Columnas de la Tabla

| Columna | Qué Muestra |
|---------|-------------|
| 🎨 **Color** | Cuadrado de color identificativo |
| 📝 **Nombre** | Nombre de la categoría (+ ID técnico) |
| 📄 **Descripción** | Texto descriptivo (o "Sin descripción") |
| ✔️ **Estado** | Si está Activa (verde) o Inactiva (gris) |
| 📦 **Productos** | Cuántos productos hay en esa categoría |
| 📅 **Fecha Creación** | Cuándo se creó |
| ⚙️ **Acciones** | Botones para editar o eliminar |

#### Filtros y Búsqueda

Encima de la tabla encontrará:

1. **Buscador** - Escriba el nombre de la categoría para encontrarla rápido
2. **Filtro por Estado** - Ver todas, solo activas, solo inactivas
3. **Ordenar por** - Cambiar el orden (Nombre, Fecha, etc.)

---

## ➕ Crear una Nueva Categoría

### Paso 1: Iniciar Creación

Haga clic en el botón **azul "Nueva Categoría"** en la esquina superior derecha.

Se abrirá el formulario de **"Nueva Categoría"**.

---

### Paso 2: Rellenar Información Básica

#### Campo 1: Nombre de la Categoría ⭐ Obligatorio

```
Nombre de la Categoría *
Ej: Camisetas, Pantalones, Zapatos...
Máximo 100 caracteres
```

**¿Qué escribir?**
- Un nombre **claro y descriptivo**
- En **español** (el idioma de su tienda)
- Ejemplos:
  - ✅ "Camisetas de Algodón"
  - ✅ "Zapatos Deportivos"
  - ❌ "Ropa 1" (muy vago)
  - ❌ "Asdfgh" (no tiene sentido)

---

#### Campo 2: Color Identificativo

```
Color Identificativo
#007bff (ejemplo)
```

**¿Para qué?**
- Cada categoría tiene un color único
- Aparece en listas y formularios para identificarla visualmente
- No afecta la búsqueda

**¿Cómo elegir?**
- Haga clic en el cuadrado de color
- Se abrirá un selector de colores
- Elige el que más le guste
- **Consejo:** Use colores diferentes para cada categoría para identificarlas rápido

---

#### Campo 3: Nombre en Inglés (para CLIP) ⭐ Obligatorio

```
Nombre en Inglés (para CLIP) *
Se completará automáticamente con la traducción...
```

**¿Qué es esto?**
- CLIP (el motor de IA visual) trabaja principalmente en **inglés**
- El sistema automáticamente traduce el nombre español al inglés
- Ejemplo: "Camisetas" → "T-shirts"

**¿Puedo editarlo?**
- ✅ SÍ, puede modificarlo
- Si la traducción automática no es exacta, cámbiela
- Escriba el término más común en inglés

**Ejemplos:**
| Español | Inglés (automático) | Inglés (optimizado) |
|---------|---|---|
| Camisetas | T-shirts | t-shirt, tee |
| Pantalones | Trousers | pants, jeans |
| Zapatos | Shoes | shoes, footwear |

---

#### Campo 4: Términos Alternativos ⭐ IMPORTANTE

```
Términos Alternativos
Ej: shirt, t-shirt, blouse, top (separados por coma)
Sinónimos y variaciones en inglés para mejorar CLIP
```

**¿Qué son?**
Son **sinónimos y variantes** en inglés de su categoría.

**¿Para qué sirven?**
- Cuando un cliente busca por imagen, CLIP compara la imagen con estos términos
- Si dice "remera", pero usted puso "t-shirt", seguirá encontrando la categoría
- Mejoran la **precisión de búsqueda**

**¿Cómo rellenarlos?**
1. Piense en palabras **similares o relacionadas** a su categoría
2. Escriba en **inglés** (separadas por comas)
3. Incluya variantes regionales

**Ejemplos por Categoría:**

| Categoría | Términos Alternativos |
|-----------|-----|
| **Camisetas** | shirt, t-shirt, blouse, top, tee, casual shirt |
| **Pantalones** | pants, jeans, trousers, denim, slacks, casual pants |
| **Zapatos** | shoes, footwear, sneakers, athletic shoes, boots, sandals |
| **Bermudas** | shorts, bermuda shorts, short pants, knee-length shorts |

**⚠️ Nota Importante:**
- Use **palabras reales**, no inventadas
- Escriba en **inglés**
- Separe cada término con **coma y espacio**
- El sistema valida que sean válidas

---

#### Campo 5: Descripción (Opcional)

```
Descripción
Descripción opcional de la categoría...
Máximo 500 caracteres
```

**¿Qué escribir?**
- Una **descripción breve** de la categoría
- Úsela para detalles internos o notas
- **Ejemplo:**
  - "Prendas superiores de algodón y mezclas"
  - "Ropa deportiva para entrenamiento"

**¿Es obligatorio?**
- ❌ NO, es opcional
- Pero es buena práctica agregar para recordar qué incluye

---

#### Campo 6: Aclaración para GPT-4 Vision (Opcional)

```
Aclaración para GPT-4 Vision (opcional)
Ej: SHORT DE TIRO ALTO: cintura por encima del ombligo-
SHORT DE TIRO BAJO: cintura por debajo del ombligo-
Diferencia del bermuda por el largo (bermuda llega a la rodilla)
```

**¿Qué es esto?**
- Instrucciones **especiales para la IA visual**
- Le dice al sistema cómo **diferenciar visualmente** esta categoría

**¿Cuándo usarlo?**
Cuando su categoría tiene **características visuales específicas** que podrían confundirse con otras.

**Ejemplos:**

1. **Para "Shorts":**
   ```
   Largo hasta la mitad del muslo (no llega a la rodilla)
   Cintura alta o baja según el estilo
   Diferentes del bermuda (bermuda llega a la rodilla)
   ```

2. **Para "Jeans Rotos":**
   ```
   Pantalones con roturas, agujeros o diseño desgastado
   Diferentes de jeans normales por las roturas visibles
   ```

3. **Para "Abrigos de Invierno":**
   ```
   Prendas largas que cubren hasta cintura o más abajo
   Gruesas y abrigadas, diferentes de chaquetas (más cortas)
   ```

**Consejo:** Use esto si tiene categorías parecidas que podrían confundirse (ej: camisetas vs blusas).

---

#### Checkbox: Categoría Activa

```
☑ Categoría activa
Las categorías activas aparecen disponibles para asignar a productos
```

**¿Qué significa?**
- ✅ **Marcado:** La categoría está visible y activa
- ❌ **Desmarcado:** La categoría está "oculta" (inactiva)

**¿Cuándo desactivar?**
- Si descontinúa una línea de productos temporalmente
- Si quiere "congelar" una categoría sin eliminarla

**Nota:** Las categorías inactivas NO aparecen en los formularios de productos, pero sus productos existentes se mantienen.

---

### Paso 3: Vista Previa

En la **derecha de la pantalla** verá la **"Vista Previa"** de cómo se vería la categoría.

Muestra:
- 🏷️ Nombre de la categoría
- 📄 Descripción
- ✅ Estado (Activa/Inactiva)
- 💡 Consejos de uso

Esta preview se actualiza **en tiempo real** mientras completa el formulario.

---

### Paso 4: Guardar la Categoría

En la parte inferior, haga clic en:
```
🔵 Crear Categoría
```

El sistema mostrará un mensaje:
```
✅ Categoría "[Nombre]" creada correctamente
```

¡Listo! Su categoría está creada y lista para usar.

---

## ✏️ Editar una Categoría Existente

### Paso 1: Abrir Edición

En la tabla de categorías, haga clic en el **botón lápiz** (✏️) en la columna "Acciones".

Se abrirá el formulario de edición.

---

### Paso 2: Modificar Información

Todos los campos son **editables**:
- ✏️ Nombre
- 🎨 Color
- 🇬🇧 Nombre en Inglés
- 🔤 Términos Alternativos
- 📝 Descripción
- 🤖 Aclaración para visión
- ✅ Estado Activa/Inactiva

**Cambiar solo lo que necesita** - No tiene que rellenar todo de nuevo.

---

### Paso 3: Guardar Cambios

En la parte inferior, haga clic en:
```
🔵 Actualizar Categoría
```

Se mostrará confirmación:
```
✅ Categoría "[Nombre]" actualizada correctamente
```

---

## 🗑️ Eliminar una Categoría

### Paso 1: Localizar la Categoría

En la tabla de categorías, encuentre la que desea eliminar.

### Paso 2: Abrir Opciones

En la columna "Acciones", verá dos botones:
- ✏️ Editar
- 🗑️ Eliminar (papelera roja)

Haga clic en el botón de **papelera roja**.

---

### Paso 3: Confirmar Eliminación

Se abrirá un **diálogo de confirmación**:
```
⚠️ ¿Eliminar esta categoría?
Esta acción no se puede deshacer
Cancelar  |  Eliminar
```

**⚠️ Advertencias:**
- Si la categoría tiene **productos asignados**, se desvincularán
- Los productos NO se eliminarán, solo perderán su categoría
- Esta acción **no se puede deshacer**

Haga clic en **"Eliminar"** para confirmar.

---

## 💡 Mejores Prácticas para Categorías

### ✅ CORRECTO

| Práctica | Ejemplo |
|----------|---------|
| Nombres claros | "Camisetas Manga Corta" |
| Colores distintos | Usar 10+ colores diferentes |
| Términos específicos | "polo, casual shirt, button-up" |
| Descripción breve | "Camisetas de algodón 100% para hombre" |
| Revisar sinónimos | Verificar que los términos sean palabras reales |

### ❌ EVITAR

| Práctica | Problema |
|----------|----------|
| Nombres vagos | "Ropa", "Cosas", "Varios" |
| Colores iguales | Todas azul, difícil de distinguir |
| Términos en español | CLIP trabaja en inglés |
| Términos inventados | "xyzabc", "asdfgh" |
| Muchas categorías sin productos | Desorden en el catálogo |

---

## 📊 Relación entre Categorías y Búsqueda

### Sin Categorías Bien Definidas
```
Cliente busca: "Camiseta roja"
Sistema devuelve: Camisetas, blusas, vestidos, suéteres
❌ Resultados confusos
```

### Con Categorías Bien Definidas
```
Cliente busca: "Camiseta roja"
Sistema busca EN la categoría "Camisetas"
Sistema devuelve: Solo camisetas rojas
✅ Resultados precisos
```

---

## 🎯 Próximo Paso

Una vez que tenga sus **categorías creadas**, el siguiente paso es:

**→ [Capítulo 3: Gestión de Productos](#3-gestión-de-productos)**

Allí creará productos y los asignará a estas categorías.

---

**Versión**: 1.0
**Última Actualización**: Enero 2026
**Sistema**: CLIP Comparador V2

---

# 3. Gestión de Productos

## 📦 ¿Qué son los Productos?

Los **productos** son los artículos que vende en su tienda. Cada producto contiene:
- ✅ Información básica (nombre, precio, descripción)
- ✅ Categoría de clasificación
- ✅ Atributos personalizados (colores, tallas, materiales, etc.)
- ✅ Imágenes para búsqueda visual
- ✅ Datos de control (SKU, stock)

Un buen catálogo de productos es la **base** de la búsqueda visual efectiva.

---

## 📍 Acceso a Productos

### Desde el Menú
En el menú lateral izquierdo, haga clic en:
```
🏪 MI TIENDA
  └─ 📦 Mis Productos
```

### Desde el Dashboard
En la sección **Acciones Rápidas**, haga clic en:
```
📦 Gestionar Productos
```

---

## 📋 Pantalla Principal de Productos

La pantalla **"Mis Productos"** le muestra un resumen de su catálogo.

### Estadísticas Principales

En la parte superior, **4 tarjetas** muestran el estado:

| Tarjeta | Significa |
|---------|-----------|
| 📦 **Total de Productos** | Cuántos productos ha creado |
| 🏷️ **Categorías** | En cuántas categorías están distribuidos |
| 🖼️ **Total Imágenes** | Cuántas fotografías ha subido |
| ⏳ **Pendientes** | Productos sin imágenes o sin procesamiento |

**Ejemplo:**
- Total: 47 productos
- Categorías: 10
- Imágenes: 54
- Pendientes: 0

Significa: Tiene 47 productos bien distribuidos, con 54 imágenes cargadas, todo procesado.

---

### Búsqueda y Filtros

Debajo de las estadísticas encontrará herramientas para filtrar:

#### 1. Buscador de Productos
```
🔍 Buscar productos
Nombre, descripción, SKU o tags...
```

**¿Cómo usarlo?**
- Escriba parte del nombre del producto
- También busca en descripción, SKU y tags
- **Ejemplo:** Escribir "cami" encontrará "Camiseta azul", "Camiseta roja", etc.

#### 2. Filtro por Categoría
```
📂 Todas las categorías ▼
```

**¿Cómo usarlo?**
- Haga clic en el dropdown
- Seleccione una categoría
- Verá SOLO productos de esa categoría
- Seleccione "Todas las categorías" para volver a ver todo

**Ejemplo:** Si selecciona "Camisetas", solo verá productos de esa categoría.

#### 3. Botones Adicionales
- 🔍 Icono de búsqueda avanzada
- ⚙️ Opciones de vista/configuración

---

## 🎨 Vista Grid de Productos

Los productos se muestran en **tarjetas** (grid layout):

### Contenido de Cada Tarjeta

```
┌─────────────────────────┐
│    [IMAGEN PRODUCTO]    │  ← Foto principal
├─────────────────────────┤
│ Nombre del Producto     │
│ ✏️ categoría            │
│ Descripción breve...    │  ← Primera línea descripción
├─────────────────────────┤
│ $3500.00                │  ← Precio
│ SKU: tea.48             │  ← Código de producto
│ 📷 2                    │  ← Cantidad de imágenes
├─────────────────────────┤
│ [👁️] [✏️] [🗑️]          │  ← Botones de acción
└─────────────────────────┘
```

### Elementos de la Tarjeta

| Elemento | Descripción |
|----------|-------------|
| **Imagen** | Foto principal del producto |
| **Nombre** | Nombre del producto |
| **Categoría** | (Con icono ✏️) |
| **Descripción** | Primera línea de la descripción |
| **Precio** | En formato moneda ($) |
| **SKU** | Código de referencia |
| **Imágenes** | 📷 Número de fotos cargadas |
| **Botones** | Ver, Editar, Eliminar |

### Botones de Acción

| Botón | Función | Ir a... |
|-------|---------|---------|
| 👁️ **Ojo** | Ver detalles del producto | Capítulo siguiente |
| ✏️ **Lápiz** | Editar producto | Sección "Editar" |
| 🗑️ **Papelera** | Eliminar producto | Sección "Eliminar" |

---

## ➕ Crear un Nuevo Producto

### Paso 1: Iniciar Creación

En la esquina superior derecha, haga clic en:
```
🔵 Nuevo Producto
```

Se abrirá la pantalla **"Crear Producto"** en dos columnas.

---

### Paso 2: Información del Producto (Columna Izquierda)

#### Campo 1: Nombre del Producto ⭐ Obligatorio

```
Nombre del Producto *
Ej: Camiseta de algodón azul
```

**¿Qué escribir?**
- Nombre **claro y descriptivo**
- Incluyendo características principales
- **Máximo 100 caracteres**

**Ejemplos:**
- ✅ "Camiseta de algodón 100% azul marino"
- ✅ "Pantalón jeans recto para hombre"
- ❌ "Producto 1" (vago)
- ❌ "Cosa" (sin detalle)

---

#### Campo 2: Categoría ⭐ Obligatorio

```
Categoría *
Seleccionar categoría...
```

**¿Cómo elegir?**
- Haga clic en el dropdown
- Seleccione la categoría que creó anteriormente
- El producto aparecerá en esa categoría

**Ejemplo:** Si selecciona "Camisetas", el producto se asignará a esa categoría.

**⚠️ Nota:** Solo puede elegir categorías **activas**.

---

#### Campo 3: Descripción (Opcional)

```
Descripción
Descripción detallada del producto...
```

**¿Qué escribir?**
- Detalles del producto
- Material, composición, cuidados
- Características especiales

**Ejemplo:**
```
Camiseta 100% algodón de alta calidad.
Material suave y transpirable.
Disponible en varios colores.
Cuidado: Lavar en agua fría.
```

**Límite:** Máximo 500 caracteres.

---

#### Campo 4: SKU / Código ⭐ Recomendado

```
SKU / Código
Ej: CAM-001
```

**¿Qué es SKU?**
- **Stock Keeping Unit**
- Código único de referencia del producto
- Facilita control de inventario

**¿Cómo elegir?**
- Cree un código **único** para cada producto
- Ejemplo: **CAM-001** (primeras letras + número)
- O use el código del proveedor

**Ejemplos:**
- CAM-001, CAM-002, CAM-003 (Camisetas)
- PAN-001, PAN-002 (Pantalones)
- ZAP-001 (Zapatos)

---

#### Campo 5: Precio

```
Precio
$ 0.00
```

**¿Qué escribir?**
- Precio de venta del producto
- En la moneda de su tienda
- Sin símbolos, solo números

**Ejemplo:**
- Escriba: `3500.00`
- Se mostrará: `$ 3500.00`

---

#### Campo 6: Stock

```
Stock
0
```

**¿Qué significa?**
- Cantidad de unidades disponibles

**¿Cuándo llenar?**
- Si gestiona inventario
- Si está integrado con TiendaNube, puede que sea automático

**Ejemplo:**
- Stock 0 = No disponible
- Stock 50 = Tiene 50 unidades

---

#### Campo 7: Tags (Opcional)

```
Tags
algodon, azul, casual
Separar múltiples tags con comas
```

**¿Qué son?**
- Palabras clave adicionales para búsqueda
- Mejoran cómo se encuentra el producto

**¿Cómo rellenar?**
- Escriba palabras separadas por **comas**
- Sin límite de cantidad

**Ejemplos:**
```
algodon, azul, casual, hombre, verano
material:algodon, color:azul, estacion:verano
```

**Consejo:** Use palabras que sus clientes usan para buscar.

---

#### Campo 8: Atributos Personalizados ⭐ Dinámicos

```
🎨 Atributos Personalizados

Color
[Seleccionar...]
```

**¿Qué es esto?**
- Campos **adicionales y personalizados** según su negocio
- Los que definió en el capítulo anterior
- **Aparecen automáticamente** si los creó

**¿Cómo rellenar?**
- Cada atributo tiene su propio control
- Dropdown, texto, número, fecha, etc.
- Rellene los que apliquen al producto

**Tipos de Atributos que puede encontrar:**

| Tipo | Ejemplo | Entrada |
|------|---------|---------|
| **Lista** | Color: Rojo, Azul, Negro | Dropdown o Multi-select |
| **Texto** | Material: Algodón | Caja de texto |
| **Número** | Talla: 42 | Campo numérico |
| **Fecha** | Fecha de lanzamiento | Selector de fecha |
| **URL** | Enlace de referencia | Campo de texto |

**Ejemplo de llenado:**
```
Color: Azul
Talla: L
Material: Algodón 100%
```

---

### Paso 3: Imágenes del Producto (Columna Derecha)

En la columna derecha, verá la sección:
```
🖼️ Imágenes del Producto
```

#### Área de Carga

```
☁️ Arrastra y suelta tus imágenes aquí
o haz clic para seleccionar archivos

Formatos: JPG, PNG, GIF, WEBP, BMP, TIFF
Máximo: 50MB por imagen
```

**¿Cómo cargar imágenes?**

Opción 1 - Arrastrar y soltar:
1. Abra su carpeta de imágenes
2. Arrastre las fotos al área blanca
3. Las imágenes se cargarán automáticamente

Opción 2 - Hacer clic:
1. Haga clic en el área blanca
2. Seleccione archivos de su computadora
3. Haga clic en "Abrir"

---

#### Especificaciones de Imágenes

| Aspecto | Requisito |
|---------|-----------|
| **Formatos** | JPG, PNG, GIF, WEBP, BMP, TIFF |
| **Tamaño máximo** | 50 MB por imagen |
| **Resolución recomendada** | 500x500 píxeles mínimo |
| **Cantidad** | Sin límite (pero 3-10 ideales) |

**💡 Consejos:**
- ✅ Use imágenes de **buena calidad**
- ✅ Fondo **limpio y uniforme**
- ✅ Producto bien **visible y centrado**
- ✅ Múltiples ángulos mejoran búsqueda
- ❌ Evite imágenes borrosas o pequeñas

---

#### Procesamiento de Imágenes

Después de cargar:
1. Las imágenes se suben a **Cloudinary**
2. Se procesan con **CLIP** automáticamente
3. Se crea un "resumen visual" (embedding)
4. **Puede tardar minutos u horas**

Ver progreso en: [Capítulo 5: Carga de Imágenes](#5-carga-de-imágenes)

---

### Paso 4: Guardar el Producto

En la parte inferior, tiene dos botones:

```
❌ Cancelar                    ✅ Crear Producto
```

Haga clic en **"Crear Producto"** para guardar.

Sistema mostrará:
```
✅ Producto "[Nombre]" creado correctamente
```

¡Listo! El producto está creado.

---

## ✏️ Editar un Producto Existente

### Paso 1: Abrir Edición

En la tarjeta del producto, haga clic en el **botón lápiz** (✏️).

Se abrirá el formulario de edición (igual al de creación).

---

### Paso 2: Modificar Información

Todos los campos son **editables**:
- ✏️ Nombre
- 📂 Categoría
- 📝 Descripción
- 🔢 SKU
- 💵 Precio
- 📦 Stock
- 🏷️ Tags
- 🎨 Atributos
- 🖼️ Imágenes

Cambiar solo lo que necesita.

---

### Paso 3: Agregar o Cambiar Imágenes

En la sección de imágenes:
- **Agregar más:** Arrastre nuevas imágenes
- **Eliminar:** Haga clic en la X sobre la imagen (si aparece)
- **Reordenar:** Algunos sistemas permiten drag & drop

---

### Paso 4: Guardar Cambios

En la parte inferior, haga clic en:
```
✅ Actualizar Producto
```

Se mostrará confirmación:
```
✅ Producto "[Nombre]" actualizado correctamente
```

---

## 👁️ Ver Detalles de un Producto

### Paso 1: Abrir Vista de Detalles

En la tarjeta del producto, haga clic en el **botón ojo** (👁️).

Se abrirá una vista **completa** del producto con toda su información.

---

### Paso 2: Información Visible

Verá:
- 🖼️ Galería completa de imágenes
- 📝 Nombre, descripción, precio
- 📂 Categoría
- 🔢 SKU, Stock
- 🎨 Atributos
- 📊 Estado de procesamiento de imágenes
- 🔗 Enlaces a acciones (editar, eliminar)

---

## 🗑️ Eliminar un Producto

### Paso 1: Abrir Opciones de Eliminación

En la tarjeta del producto, haga clic en el **botón papelera** (🗑️).

O desde la vista de detalles, busque el botón de eliminar.

---

### Paso 2: Confirmar Eliminación

Se abrirá un **diálogo de confirmación**:
```
⚠️ ¿Eliminar este producto?
Esta acción no se puede deshacer
Cancelar  |  Eliminar
```

**⚠️ Advertencias:**
- Las imágenes asociadas se eliminarán
- El producto desaparecerá del catálogo
- Esta acción **no se puede deshacer**
- Si tiene ventas registradas, se perderá el historial

Haga clic en **"Eliminar"** para confirmar.

---

## 🔄 Relación entre Productos e Imágenes

### Flujo Completo

```
1. CREAR PRODUCTO
   └─ Nombre, Categoría, Precio, Atributos

2. CARGAR IMÁGENES
   └─ Subir fotos (formato JPG, PNG, etc.)

3. PROCESAMIENTO AUTOMÁTICO
   └─ Sistema analiza con CLIP (puede tardar)

4. BÚSQUEDA LISTA
   └─ Clientes pueden buscar por imagen
```

### Importancia de las Imágenes

| Aspecto | Impacto |
|---------|---------|
| **Sin imágenes** | Producto invisible en búsqueda visual |
| **Imágenes borrosas** | Búsqueda imprecisa |
| **Imágenes de calidad** | Búsquedas exactas y rápidas |
| **Múltiples ángulos** | Mejor reconocimiento |

---

## 💡 Mejores Prácticas para Productos

### ✅ CORRECTO

| Práctica | Ejemplo |
|----------|---------|
| Nombres descriptivos | "Camiseta algodón azul marino L" |
| Categoría clara | Asignar a categoría específica |
| Precio realista | Precio de venta actual |
| Imágenes de calidad | Foto clara en fondo limpio |
| Atributos completos | Color, Talla, Material rellenados |
| SKU único | CAM-001, CAM-002, etc. |
| Tags relevantes | Palabras que clientes usan |

### ❌ EVITAR

| Práctica | Problema |
|----------|----------|
| Nombres vagos | "Producto", "Cosa", "Item" |
| Sin categoría | Desorientación del usuario |
| Precio en 0 | Parece producto de prueba |
| Imágenes borrosas | Búsqueda fallida |
| Atributos vacíos | Filtros no funcionan |
| SKU duplicado | Confusión en inventario |
| Sin imágenes | No aparece en búsqueda visual |

---

## 📊 Estadísticas de Productos

En la pantalla principal, las tarjetas le dicen:

| Métrica | Acción Recomendada |
|---------|---|
| **Pendientes > 0** | Tiene productos sin imágenes, agregue fotos |
| **Total Imágenes bajo** | Agregue más productos o fotos |
| **Embeddings < 100%** | Espere, el sistema está procesando |

---

## 🎯 Próximos Pasos

Después de crear productos:

1. **[Capítulo 4: Carga de Imágenes](#5-carga-de-imágenes)** - Revisar estado de procesamiento
2. **[Capítulo 5: Atributos](#6-configuración-de-atributos)** - Optimizar atributos
3. **[Capítulo 6: Inventario](#7-gestión-de-inventario)** - Si necesita controlar stock
4. **[Capítulo 7: Analytics](#8-analytics-y-reportes)** - Ver cómo buscan clientes

---

**Versión**: 1.0
**Última Actualización**: Enero 2026
**Sistema**: CLIP Comparador V2

---

# 4. Configuración de Atributos Dinámicos

## 🎨 ¿Qué son los Atributos?

Los **atributos** son características adicionales de sus productos. Mientras que todos los productos tienen nombre, precio y categoría, los atributos son **campos personalizados** según su negocio.

### Ejemplos de Atributos
- **Color:** Rojo, Azul, Negro, Verde
- **Talla:** XS, S, M, L, XL, XXL
- **Material:** Algodón, Poliéster, Lino, Mezcla
- **Peso:** 500g, 1kg, etc.
- **Temporada:** Verano, Invierno, Primavera, Otoño

---

## 🎯 ¿Por Qué Importan los Atributos?

| Razón | Beneficio |
|-------|-----------|
| **Flexibilidad** | Cada tienda tiene características diferentes |
| **Filtros en Búsqueda** | Clientes pueden filtrar por color, talla, etc. |
| **Precisión** | CLIP busca dentro de atributos específicos |
| **Información Completa** | Clientes saben exactamente qué compran |
| **Gestión de Inventario** | Controlar stock por talla/color |

---

## 📍 Acceso a Atributos

### Desde el Menú
En el menú lateral izquierdo, haga clic en:
```
🏪 MI TIENDA
  └─ 🎨 Atributos
```

### Desde el Dashboard (Formulario de Producto)
Al crear un producto, los atributos aparecen **automáticamente** como campos adicionales.

---

## 📋 Pantalla Principal de Atributos

La pantalla **"Atributos de Productos"** muestra una tabla con todos los atributos configurados.

### Tabla de Atributos

| Columna | Significa |
|---------|-----------|
| **Orden** | Número de posición en el formulario |
| **Nombre Interno** | Identificador técnico (ej: `color`, `talla`) |
| **Etiqueta** | Nombre que ve el usuario (ej: "Color", "Talla") |
| **Tipo** | Qué tipo de datos (Texto, Número, Lista, etc.) |
| **Obligatorio** | Si es requerido llenar este campo |
| **En Búsqueda** | Si aparece como filtro en búsqueda visual |
| **Multi-select** | Si se pueden seleccionar múltiples opciones |
| **Acciones** | Botones para editar o eliminar |

### Ejemplo de Fila

```
Orden: 1
Nombre Interno: color
Etiqueta: Color
Tipo: Lista
Obligatorio: ❌ (no está marcado)
En Búsqueda: ✅ (está marcado)
Multi-select: ✅ (soporta múltiples valores)
Acciones: [✏️] [🗑️]
```

---

## ➕ Crear un Nuevo Atributo

### Paso 1: Iniciar Creación

En la esquina superior derecha, haga clic en:
```
🔵 Nuevo Atributo
```

Se abrirá el formulario **"Crear Nuevo Atributo"**.

---

### Paso 2: Nombre Interno ⭐ Obligatorio

```
Nombre Interno *
Ej: talla, material, color
Solo letras minúsculas, números y guiones bajos
```

**¿Qué es?**
- Identificador **técnico** del atributo
- Se usa internamente en el sistema
- **No lo ven los clientes**

**¿Cómo elegir?**
- Solo **letras minúsculas** (a-z)
- Solo **números** (0-9)
- Solo **guiones bajos** (_)
- **SIN espacios, puntuación o caracteres especiales**

**Conversión automática:**
- Si escribe "Mi Color" → Se convierte a "mi_color"
- Si escribe "Talla XL" → Se convierte a "talla_xl"

**Ejemplos:**
- ✅ `color` - Simple y claro
- ✅ `talla_ropa` - Descriptivo con guión bajo
- ✅ `peso_kg` - Incluye unidad
- ❌ `color-bonito` - Tiene guión, no guión bajo
- ❌ `TALLA` - Mayúsculas (se convertirán)
- ❌ `talla especial` - Tiene espacio

**Consejo:** Use nombres que recuerde fácilmente.

---

### Paso 3: Etiqueta ⭐ Obligatorio

```
Etiqueta *
Ej: Talla, Material, Color
Texto que se mostrará en los formularios
```

**¿Qué es?**
- Nombre **visible** para el usuario
- Aparece en formularios de productos
- Aparece en filtros de búsqueda

**¿Cómo elegir?**
- Nombre **claro y descriptivo**
- Puede tener **espacios y mayúsculas**
- **Máximo 100 caracteres**

**Relación Nombre Interno ↔ Etiqueta:**

| Nombre Interno | Etiqueta (Visible) |
|---|---|
| `color` | Color |
| `talla_ropa` | Talla de Ropa |
| `peso_kg` | Peso (kg) |
| `temporada` | Temporada del Año |
| `material_principal` | Material Principal |

---

### Paso 4: Tipo de Campo ⭐ Obligatorio

```
Tipo de Campo *
```

Este es el campo más importante. Elegir el tipo determina cómo se rellena el atributo.

#### 4.1 - Tipo: Texto

```
Tipo: Texto
```

**¿Qué es?**
- Campo de texto libre
- El usuario escribe cualquier texto

**¿Cuándo usarlo?**
- Descripción libre
- Comentarios
- Detalles específicos

**Ejemplo:**
```
Atributo: Descripción de Diseño
Usuario escribe: "Rayitas horizontales de colores"
```

---

#### 4.2 - Tipo: Número

```
Tipo: Número
```

**¿Qué es?**
- Solo números
- Puede incluir decimales

**¿Cuándo usarlo?**
- Medidas
- Pesos
- Cantidades
- Tallas numéricas

**Ejemplos:**
- Atributo: Peso (kg)
  - Usuario escribe: `500` (para 500 gramos)

- Atributo: Ancho (cm)
  - Usuario escribe: `42.5` (con decimal)

---

#### 4.3 - Tipo: Fecha

```
Tipo: Fecha
```

**¿Qué es?**
- Campo de fecha
- Se selecciona con calendario

**¿Cuándo usarlo?**
- Fecha de lanzamiento
- Fecha de expiración
- Temporal de uso

**Ejemplo:**
```
Atributo: Temporal de Venta
Usuario selecciona: 21/12/2025
```

---

#### 4.4 - Tipo: Lista de Opciones ⭐ MÁS COMÚN

```
Tipo: Lista de Opciones
```

**¿Qué es?**
- El usuario **selecciona de una lista predefinida**
- No puede escribir valores nuevos
- Perfecto para categorías fijas

**¿Cuándo usarlo?**
- **Color:** Rojo, Azul, Negro, etc.
- **Talla:** XS, S, M, L, XL, XXL
- **Material:** Algodón, Poliéster, Lino
- **Temporada:** Verano, Invierno, etc.

**¿Cómo rellenar opciones?**
Ver sección "Paso 7: Opciones" más abajo.

---

#### 4.5 - Tipo: URL

```
Tipo: URL
```

**¿Qué es?**
- Campo para enlaces/URLs

**¿Cuándo usarlo?**
- Enlace a referencia
- Enlace a vídeo
- Enlace a documentación

**Ejemplo:**
```
Atributo: Video Demostración
Usuario escribe: https://youtube.com/watch?v=xyz
```

---

### Paso 5: Orden

```
Orden
0
Posición en el formulario
```

**¿Qué es?**
- Número que determina el **orden** de aparición
- Cuanto menor el número, más arriba aparece

**¿Cómo funciona?**
- Orden 1 → Aparece primero
- Orden 2 → Aparece segundo
- Orden 10 → Aparece décimo

**Ejemplo:**
```
Color (Orden 1) - Aparece primero
Talla (Orden 2) - Aparece segundo
Material (Orden 3) - Aparece tercero
```

**Consejo:** Ordene por **importancia** del atributo.

---

### Paso 6: Checkboxes de Opciones

En la derecha del formulario, verá **dos checkboxes importantes**:

#### Checkbox 1: Obligatorio

```
☑ Obligatorio
```

**¿Qué significa?**
- ✅ **Marcado:** El usuario **DEBE** rellenar este atributo
- ❌ **Desmarcado:** El usuario **puede** dejarlo vacío

**¿Cuándo marcar?**
- Atributos esenciales: Color, Talla
- Información requerida

**¿Cuándo desmarcar?**
- Atributos opcionales: Comentarios, Detalles adicionales

**Ejemplo:**
- ✅ Obligatorio: Color (siempre necesario)
- ❌ Opcional: Modelo/Versión (a veces no aplica)

---

#### Checkbox 2: Exponer en Búsqueda

```
☑ Exponer en búsqueda
```

**¿Qué significa?**
- ✅ **Marcado:** El atributo aparece como **filtro** en búsqueda visual
- ❌ **Desmarcado:** Es solo información, no se filtra

**¿Cuándo marcar?**
- Atributos que clientes usan para filtrar:
  - Color (clientes buscan "rojo", "azul")
  - Talla (clientes buscan "L", "XL")
  - Material (clientes buscan "algodón")

**¿Cuándo desmarcar?**
- Información de referencia interna
- Datos técnicos que no son relevantes

**Ejemplo:**
```
Color: ✅ Exponer (clientes filtran por color)
SKU Proveedor: ❌ No exponer (solo referencia interna)
```

---

### Paso 7: Opciones (Solo si Tipo = "Lista de Opciones")

```
Opciones
Ej: shirt, t-shirt, blouse, top (separados por coma)
```

**SOLO aparece este campo si eligió "Lista de Opciones"**

**¿Qué escribir?**
- Cada opción separada por **coma**
- Una opción por línea (o separadas por comas)

**Formato:**
```
Opción 1, Opción 2, Opción 3, Opción 4
```

O:
```
Opción 1
Opción 2
Opción 3
```

**Ejemplos:**

**Ejemplo 1 - Color:**
```
Rojo, Azul, Negro, Verde, Amarillo, Rosa, Blanco
```

**Ejemplo 2 - Talla:**
```
XS, S, M, L, XL, XXL
```

**Ejemplo 3 - Material:**
```
Algodón 100%, Poliéster, Lino, Mezcla algodón-poliéster
```

**⚠️ Validación del Sistema:**
- El sistema valida que sean opciones válidas
- No pueden estar vacías
- No pueden ser duplicadas

---

### Paso 8: Multi-select (Para Tipo Lista)

Si está en "Lista de Opciones", el sistema **automáticamente soporta multi-select**, lo que significa:

**¿Qué es multi-select?**
- El usuario puede seleccionar **múltiples opciones** a la vez
- No solo una

**Ejemplo:**
```
Atributo: Color
Usuario puede seleccionar: Rojo Y Azul Y Negro (juntos)

NO: Solo puede elegir UN color
```

**Cuándo es útil:**
- Productos con múltiples colores (a rayas)
- Paquetes con múltiples opciones
- Personalizaciones complejas

---

### Paso 9: Guardar el Atributo

En la parte inferior derecha, haga clic en:
```
🔵 Crear Atributo
```

Sistema mostrará confirmación:
```
✅ Atributo "[Etiqueta]" creado correctamente
```

¡Listo! El atributo aparecerá en todos los formularios de producto.

---

## ✏️ Editar un Atributo

### Paso 1: Abrir Edición

En la tabla de atributos, haga clic en el **botón lápiz** (✏️) en la columna "Acciones".

Se abrirá el formulario de edición.

---

### Paso 2: Modificar Información

Todos los campos son **editables**:
- ✏️ Nombre Interno (con restricciones)
- ✏️ Etiqueta
- ✏️ Tipo de Campo
- ✏️ Orden
- ✏️ Opciones (si aplica)
- ✏️ Obligatorio
- ✏️ Exponer en búsqueda

**⚠️ Nota Importante:**
Si cambia el tipo de un atributo que ya tiene datos, los valores **pueden perderse o convertirse**.

Ejemplo:
- Cambiar de "Texto" a "Número" puede causar problemas si hay texto guardado

---

### Paso 3: Guardar Cambios

En la parte inferior, haga clic en:
```
🔵 Actualizar Atributo
```

Se mostrará confirmación:
```
✅ Atributo "[Etiqueta]" actualizado correctamente
```

---

## 🗑️ Eliminar un Atributo

### Paso 1: Localizar el Atributo

En la tabla de atributos, encuentre el que desea eliminar.

### Paso 2: Eliminar

En la columna "Acciones", haga clic en el **botón papelera** (🗑️).

Se abrirá un **diálogo de confirmación**:
```
⚠️ ¿Eliminar este atributo?
Esta acción no se puede deshacer
Cancelar  |  Eliminar
```

**⚠️ Advertencias:**
- Los valores del atributo en los productos se perderán
- Los productos NO se eliminarán, solo perderán ese atributo
- Esta acción **no se puede deshacer**

Haga clic en **"Eliminar"** para confirmar.

---

## 💡 Ejemplos Completos de Atributos

### Ejemplo 1: Color

```
Nombre Interno: color
Etiqueta: Color
Tipo: Lista de Opciones
Orden: 1
Obligatorio: ✅ Sí
Exponer en Búsqueda: ✅ Sí
Opciones: Rojo, Azul, Negro, Verde, Blanco, Rosa, Amarillo
Multi-select: ✅ Sí
```

**Resultado:**
- Aparece en primer lugar en el formulario
- Usuario **debe** seleccionar un color
- Color aparece como **filtro** en búsqueda visual
- Puede seleccionar múltiples colores

---

### Ejemplo 2: Talla

```
Nombre Interno: talla
Etiqueta: Talla
Tipo: Lista de Opciones
Orden: 2
Obligatorio: ✅ Sí
Exponer en Búsqueda: ✅ Sí
Opciones: XS, S, M, L, XL, XXL
Multi-select: ❌ No (solo una talla)
```

**Resultado:**
- Aparece en segundo lugar
- Usuario **debe** seleccionar talla
- Talla aparece como **filtro** en búsqueda
- Solo puede seleccionar UNA talla

---

### Ejemplo 3: Material

```
Nombre Interno: material
Etiqueta: Material
Tipo: Lista de Opciones
Orden: 3
Obligatorio: ❌ No
Exponer en Búsqueda: ✅ Sí
Opciones: Algodón 100%, Poliéster, Lino, Mezcla
```

**Resultado:**
- Aparece en tercer lugar
- Usuario puede **dejar vacío** si quiere
- Material es **opcional** pero filtrable

---

### Ejemplo 4: Peso

```
Nombre Interno: peso_kg
Etiqueta: Peso (kg)
Tipo: Número
Orden: 4
Obligatorio: ❌ No
Exponer en Búsqueda: ❌ No
```

**Resultado:**
- Información técnica
- Usuario escribe un número
- NO aparece como filtro en búsqueda
- Uso interno

---

### Ejemplo 5: Descripción Especial

```
Nombre Interno: descripcion_especial
Etiqueta: Descripción Especial
Tipo: Texto
Orden: 5
Obligatorio: ❌ No
Exponer en Búsqueda: ❌ No
```

**Resultado:**
- Campo libre de texto
- Usuario puede escribir detalles adicionales
- No se filtra en búsqueda
- Para notas internas

---

## 📊 Relación entre Atributos y Búsqueda

### Con Atributos Mal Configurados
```
Cliente busca: "Camiseta roja talla L"
Sistema no encuentra filtros
❌ Resultados imprecisos
```

### Con Atributos Bien Configurados
```
Cliente busca: "Camiseta"
✅ Filtro 1: Color = Rojo
✅ Filtro 2: Talla = L
Sistema busca: Camisetas rojas talla L
✅ Resultados exactos
```

---

## ✅ Checklist de Atributos

Antes de crear muchos productos, prepare sus atributos:

```
☐ Identificar qué características tiene cada producto
☐ Crear atributo para cada característica
☐ Decidir Nombre Interno (técnico)
☐ Decidir Etiqueta (visible)
☐ Elegir Tipo (Texto, Número, Fecha, Lista, URL)
☐ Si es Lista: escribir todas las opciones
☐ Marcar como Obligatorio si es esencial
☐ Marcar como "Exponer en Búsqueda" si clientes filtran por eso
☐ Ordenar por importancia
☐ Crear atributo
☐ Verificar que aparece en formulario de producto
```

---

## 💡 Mejores Prácticas

### ✅ CORRECTO

| Práctica | Ejemplo |
|----------|---------|
| Atributos esenciales | Color, Talla, Material |
| Nombres internos simples | `color`, `talla`, `material` |
| Etiquetas claras | "Talla de Ropa", "Material Principal" |
| Tipo apropiado | Lista para Color, Número para Peso |
| Exponer lo relevante | Filtros que clientes usan |
| Opciones completas | Rojo, Azul, Negro (no "Rojo y azul") |
| Orden lógico | Por importancia o uso frecuente |

### ❌ EVITAR

| Práctica | Problema |
|----------|----------|
| Demasiados atributos | Abruma al usuario |
| Nombres internos confusos | `x1`, `cosa2`, `data_especial` |
| Etiquetas vagas | "Campo 1", "Información" |
| Tipo equivocado | Peso como "Texto" en vez de "Número" |
| Exponer todo | Filtros irrelevantes confunden |
| Opciones incompletas | Falta el color rojo cuando existe |
| Sin orden | Atributos desordenados |

---

## 🎯 Próximo Paso

Después de crear atributos, continúe con:

**→ [Capítulo 3: Gestión de Productos](#3-gestión-de-productos)** (si no lo hizo)

Allí verá cómo los atributos aparecen automáticamente en los formularios de producto.

---

# 5. Carga de Imágenes y Embeddings CLIP

## 📸 ¿Qué son los Embeddings?

Los **embeddings** son "resúmenes visuales" que el sistema CLIP crea automáticamente a partir de sus imágenes. Son la **base de la búsqueda visual**.

### ¿Cómo funcionan?

```
1. USTED CARGA una imagen (JPG, PNG, etc.)
   ↓
2. CLIP ANALIZA la imagen (automático en segundo plano)
   ├─ Reconoce colores
   ├─ Identifica formas
   └─ Comprende el contenido visual
   ↓
3. CLIP CREA un "resumen" (embedding = vector numérico)
   ↓
4. SISTEMA ALMACENA el resumen
   ↓
5. CUANDO CLIENTE BUSCA POR IMAGEN
   └─ Compara el resumen de su búsqueda con sus resúmenes
   └─ Encuentra productos similares
```

---

## 🎯 ¿Por Qué son Importantes?

| Aspecto | Beneficio |
|--------|-----------|
| **Sin Embeddings** | Las imágenes son solo fotos, no se pueden comparar |
| **Con Embeddings** | Las imágenes se pueden buscar por similitud visual |
| **Más Rápido** | Búsquedas comparando vectores = muy rápido |
| **Más Preciso** | Entiende contenido visual, no solo palabras clave |
| **Automático** | Todo ocurre en segundo plano, usted no hace nada |

---

## 📍 Acceso a Embeddings

### Desde el Menú
En el menú lateral izquierdo, haga clic en:
```
🏪 MI TIENDA
  └─ ⚙️ Mis Embeddings CLIP
```

### Desde el Dashboard
En la sección **Acciones Rápidas**, haga clic en:
```
⚙️ Procesar Embeddings
```

---

## 📊 Pantalla Principal de Embeddings

La pantalla **"Administración de Embeddings CLIP"** es su **centro de control** para el procesamiento de imágenes.

### Encabezado

```
🔮 Administración de Embeddings CLIP
Control total sobre el procesamiento de embeddings para búsqueda visual
```

Con un botón de **"Actualizar"** para recargar las estadísticas.

---

## 📈 Estadísticas de Procesamiento

En la parte superior, **4 tarjetas** muestran el estado actual:

### 1️⃣ Total Imágenes
**Cantidad total de imágenes cargadas** en todos sus productos.

Ejemplo: Si ve "54", tiene 54 imágenes en total.

### 2️⃣ Procesadas
**Imágenes analizadas correctamente** por CLIP.

Ejemplo: Si ve "47", 47 imágenes ya tienen embeddings.

### 3️⃣ Pendientes
**Imágenes que aún no han sido procesadas**.

Ejemplo: Si ve "7", quedan 7 imágenes para procesar.

**⏱️ ¿Por qué demoran?**
- El sistema procesa en segundo plano continuamente
- Puede tardar minutos u horas según cantidad
- No es instantáneo

### 4️⃣ Errores
**Imágenes que no se pudieron procesar**.

Ejemplo: Si ve "0", todo está bien.

**⚠️ Si tiene errores:**
- Pueden deberse a: imagen corrupta, formato no soportado
- Puede intentar recargar la imagen
- O usar "Limpiar Errores" para resetearlas

---

## 📊 Barra de Progreso

La **barra de progreso visual** muestra el avance en tiempo real:

```
┌──────────────────────────────────────┐
│ 📊 Progreso de Procesamiento    85% │
├──────────────────────────────────────┤
│ ████████████████████░░░ 85%        │
├──────────────────────────────────────┤
│ 47 de 55 imágenes procesadas       │
└──────────────────────────────────────┘
```

**Qué significa cada color:**
- 🟢 **Verde (completo):** 100% - Todo procesado
- 🔵 **Azul (procesando):** Imágenes en procesamiento
- 🟡 **Amarillo (pendiente):** Aún no comienza
- 🔴 **Rojo (errores):** Imágenes con fallos

---

## 🎛️ Controles de Procesamiento

En la sección **"Controles de Procesamiento"** encontrará **4 botones principales**:

### Botón 1: Procesar Pendientes

```
▶️ PROCESAR PENDIENTES
(7 imágenes)
```

**¿Qué hace?**
- Inicia el procesamiento de imágenes pendientes
- Se procesa en **segundo plano** (no bloquea la interfaz)
- Muestra progreso en tiempo real

**¿Cuándo usarlo?**
- Cuando ve imágenes "Pendientes" > 0
- Para acelerar el procesamiento
- Después de cargar muchas imágenes nuevas

**⏱️ Tiempo estimado:**
- 50-100 imágenes: 5-15 minutos
- 100-500 imágenes: 15-60 minutos
- 500+ imágenes: 1-3 horas

**Nota:** El botón está **deshabilitado** si no hay pendientes (todas procesadas).

---

### Botón 2: Limpiar Errores

```
🧹 LIMPIAR ERRORES
(2 errores)
```

**¿Qué hace?**
- Resetea imágenes con error al estado "Pendiente"
- Las vuelve a intentar procesar
- Útil para problemas temporales

**¿Cuándo usarlo?**
- Cuando tiene imágenes con "error"
- Después de corregir una imagen corrupta
- Para reintentar que procesen

**Nota:** Desaparece si no hay errores.

---

### Botón 3: Resetear Todo

```
↩️ RESETEAR TODO
(55 imágenes)
```

**⚠️ CUIDADO - Acción destructiva**

**¿Qué hace?**
- **Elimina TODOS los embeddings generados**
- Vuelve todas las imágenes al estado "Pendiente"
- Inicia desde cero

**¿Cuándo usarlo?**
- Solo si necesita reprocesar TODO (raramente)
- Si las búsquedas dan resultados muy malos
- Como último recurso para problemas graves

**Nota:** Esto tardará mucho. Úselo con cuidado.

---

### Botón 4: Recalcular Centroides

```
🔄 RECALCULAR CENTROIDES
Forzar para todas las categorías
```

**¿Qué hace?**
- Recalcula los "puntos centrales" de cada categoría
- Usado para detección automática de categoría
- Operación técnica, típicamente no es necesario

**¿Cuándo usarlo?**
- Si agrega muchos productos a una categoría
- Si cambios importantes en categorías
- Si categorías no se detectan correctamente

**Nota:** Operación rápida, se completa en segundos.

---

## 📋 Lista de Imágenes

Debajo de los controles, verá una **lista detallada de todas sus imágenes**:

### Elementos de la Lista

Para cada imagen se muestra:

| Elemento | Significa |
|----------|-----------|
| **Thumbnail** | Miniatura pequeña de la imagen |
| **Nombre Producto** | A qué producto pertenece |
| **Estado** | Procesada / Pendiente / Error |
| **Acciones** | Botones para interactuar |

### Estados Posibles

#### ✅ Procesada
```
[Miniatura] Camiseta Azul    [✅ Procesada]
```
- **Color:** Verde
- **Significado:** La imagen tiene embedding, está lista para búsqueda
- **Acción:** Nada, está completa

#### ⏳ Pendiente
```
[Miniatura] Pantalón Negro   [⏳ Pendiente]
```
- **Color:** Amarillo/Naranja
- **Significado:** Aún no se ha procesado
- **Acción:** Espere, el sistema la procesará

#### ❌ Error
```
[Miniatura] Zapato Rojo      [❌ Error]
```
- **Color:** Rojo
- **Significado:** Hubo un problema al procesar
- **Acción:** Use "Limpiar Errores" para reintentar

---

## 💡 ¿Qué Hacer en Cada Situación?

### Situación 1: Acabo de Cargar Productos

**Estado:** Muchas imágenes "Pendientes"

**Acción:**
1. Haga clic en **"Procesar Pendientes"**
2. Espere (verá progreso en tiempo real)
3. Las imágenes cambiarán a "Procesada"
4. ¡Listo!

**Tiempo:** Puede tardar minutos u horas

---

### Situación 2: Tengo Algunos Errores

**Estado:** 1-3 imágenes con "Error"

**Acción:**
1. Verifique que las imágenes sean válidas (JPG, PNG, etc.)
2. Si la imagen está corrupta, reemplácela
3. Haga clic en **"Limpiar Errores"**
4. Las imágenes se reintentan procesar

---

### Situación 3: Nada se Procesa

**Estado:** Muchas "Pendientes" después de 1 hora

**Posibles Causas:**
- Sistema ocupado (muchos usuarios)
- Servidor bajo en recursos
- Problema técnico

**Acción:**
1. Actualice la página (botón Actualizar)
2. Espere más
3. Intente de nuevo en 30 minutos

---

### Situación 4: Quiero Reprocesar Todo

**Estado:** Búsquedas dan resultados malos

**Acción:**
1. Haga clic en **"Resetear Todo"** (⚠️ cuidado)
2. Confirme la acción
3. Haga clic en **"Procesar Pendientes"**
4. Espere a completarse (puede tardar horas)

---

## ⚡ Flujo de Carga de Imágenes

### Paso 1: Crear Producto con Imágenes

Siga [Capítulo 3: Gestión de Productos](#3-gestión-de-productos)

```
1. Vaya a Mis Productos
2. Haga clic en "Nuevo Producto"
3. Rellene información
4. Arrastra imágenes al área de carga
5. Haga clic en "Crear Producto"
```

---

### Paso 2: Imágenes se Suben a Cloudinary

Automáticamente:
- Las imágenes se suben a **Cloudinary** (almacenamiento en nube)
- Se crea una URL segura
- Se guarda en la base de datos

**⏱️ Tiempo:** Segundos a minutos

---

### Paso 3: Sistema Crea Embeddings

Automáticamente (puede tardarse):
- El sistema analiza cada imagen con **CLIP**
- Crea un "resumen visual" (embedding)
- Almacena el embedding

**⏱️ Tiempo:** Minutos a horas (depende de cantidad)

**¿Cómo ver progreso?**
→ Vaya a **Mis Embeddings CLIP** (esta sección)

---

### Paso 4: ¡Búsqueda Lista!

Una vez que esté al 100%:
- Clientes **pueden buscar por imagen**
- Sistema encuentra **productos similares**
- ✅ Búsqueda visual funcionando

---

## 📊 Interpretación de Progreso

### 0-25%
```
Status: Recién comienza
Significa: Sistema está procesando
Acción: Espere
```

### 25-75%
```
Status: En progreso
Significa: Se procesa activamente
Acción: Puede hacer otras cosas
```

### 75-99%
```
Status: Casi completo
Significa: Últimas imágenes
Acción: Espere un poco más
```

### 100%
```
Status: Completado
Significa: Todas las imágenes tienen embeddings
Acción: ¡Búsqueda visual lista!
```

---

## 🚀 Buenas Prácticas

### ✅ CORRECTO

| Práctica | Por qué |
|----------|--------|
| Esperar a 100% antes de promocionar búsqueda | Resultados mejores |
| Cargar imágenes de buena calidad | CLIP analiza mejor |
| Múltiples ángulos del producto | Mejor reconocimiento |
| Revisar progreso regularmente | Saber dónde está |
| Procesar después de cargar lotes | Mantener actualizado |

### ❌ EVITAR

| Práctica | Por qué |
|----------|---------|
| Resetear constantemente | Reprocesamiento innecesario |
| Ignorar errores | Imágenes que no trabajan |
| Imágenes borrosas | CLIP no puede analizar bien |
| Cargar imágenes inválidas | Causarán errores |
| Presionarse "Procesar" repetidas veces | Ya se procesa en segundo plano |

---

## 📞 Preguntas Frecuentes sobre Embeddings

### P: ¿Por qué demora tanto?
**R:** CLIP analiza cada imagen visualmente. 100 imágenes pueden tardar 30 minutos.

### P: ¿Se procesan todas a la vez?
**R:** No, se procesan en lotes en segundo plano. El sistema continúa mientras usted trabaja.

### P: ¿Qué pasa si apago la computadora?
**R:** El procesamiento continúa en el servidor. La computadora no importa.

### P: ¿Puedo cancelar el procesamiento?
**R:** No hay botón de cancelar, pero el sistema deja de procesar si presiona otra cosa.

### P: ¿Qué significan los "errores"?
**R:** La imagen estaba corrupta, en formato no soportado, o fue demasiado grande.

### P: ¿Puedo buscar mientras se procesan?
**R:** Sí, pero resultados serán incompletos hasta llegar a 100%.

---

## 🎯 Próximo Paso

Después de que sus embeddings estén al **100%**:

**→ [Capítulo 6: Gestión de Inventario](#6-gestión-de-inventario)**

O si no necesita controlar stock:

**→ [Capítulo 7: Analytics de Tienda](#7-analytics-y-reportes)**

---

**Versión**: 1.0
**Última Actualización**: Enero 2026
**Sistema**: CLIP Comparador V2
