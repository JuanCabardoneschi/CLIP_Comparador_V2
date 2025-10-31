"""
Script para llenar automáticamente atributos JSONB usando CLIP (opción gratuita)
Analiza las imágenes de productos y clasifica atributos visuales como color, material, tipo.
"""
print("INICIO DEL SCRIPT - Auto Fill Attributes")

try:
    import os
    import sys
    import json
    import psycopg2
    import torch
    import clip
    from PIL import Image
    import requests
    from io import BytesIO
    from dotenv import load_dotenv
    import numpy as np

    print("Módulos importados correctamente")

    # Cargar variables de entorno
    load_dotenv('.env.local')
    DATABASE_URL = os.getenv('DATABASE_URL')
    print(f"DATABASE_URL: {DATABASE_URL}")

    # Inicializar modelo CLIP
    print("Cargando modelo CLIP...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/16", device=device)
    print(f"Modelo CLIP cargado en {device}")

    # Tags adicionales para clasificar (estilo, ocasión, etc.)
    # Los tags son genéricos y se aplican a todos los clientes
    TAG_OPTIONS = [
        "formal", "casual", "deportivo", "elegante", "moderno", "clásico",
        "vintage", "urbano", "profesional", "juvenil", "trabajo", "fiesta",
        "verano", "invierno", "unisex", "masculino", "femenino", "infantil",
        "premium", "económico", "cómodo", "ajustado", "holgado"
    ]

    # Mapeo de tipos de atributos comunes a templates de prompts CLIP
    ATTRIBUTE_PROMPT_TEMPLATES = {
        # Atributos de apariencia visual
        "color": "a {value} colored {category}",
        "colour": "a {value} colored {category}",
        "color_principal": "a {value} colored {category}",

        # Atributos de material/composición
        "material": "a {category} made of {value}",
        "tela": "a {category} made of {value}",
        "fabric": "a {category} made of {value}",

        # Atributos de estilo/tipo
        "estilo": "a {value} style {category}",
        "style": "a {value} style {category}",
        "tipo": "a {value} type {category}",
        "type": "a {value} type {category}",

        # Atributos de patrón/diseño
        "patron": "a {category} with {value} pattern",
        "pattern": "a {category} with {value} pattern",
        "estampado": "a {category} with {value} print",
        "print": "a {category} with {value} print",

        # Fallback genérico
        "_default": "a photo of a {value} {category}"
    }

    def get_prompt_template(attribute_key: str) -> str:
        """Determina el template de prompt adecuado para un atributo."""
        key_lower = attribute_key.lower()
        return ATTRIBUTE_PROMPT_TEMPLATES.get(key_lower, ATTRIBUTE_PROMPT_TEMPLATES["_default"])

    def classify_attribute(image, attribute_name, options, category_context: str, product_name: str = ""):
        """
        Clasifica un atributo usando CLIP comparando la imagen con opciones textuales.
        Retorna la opción con mayor similitud.

        El template de prompt se selecciona dinámicamente basado en el tipo de atributo.
        NOTA: product_name se mantiene por compatibilidad pero NO influye en la clasificación.
        Solo importa la categoría y lo que CLIP ve en la imagen.
        """
        # Preprocesar imagen
        image_input = preprocess(image).unsqueeze(0).to(device)

        # Obtener template de prompt adecuado para este atributo
        prompt_template = get_prompt_template(attribute_name)

        # Crear prompts textuales para cada opción
        text_prompts = [
            prompt_template.replace("{value}", option).replace("{category}", category_context)
            for option in options
        ]

        text_tokens = clip.tokenize(text_prompts).to(device)

        # Generar embeddings
        with torch.no_grad():
            image_features = model.encode_image(image_input)
            text_features = model.encode_text(text_tokens)

            # Normalizar
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # Calcular similitudes
            similarities = (image_features @ text_features.T).cpu().numpy()[0]

        # NO aplicamos boost por nombre del producto
        # El nombre es arbitrario (ej: "Juancito" puede ser un delantal)
        # Solo importa: categoría + visión CLIP pura

        # Encontrar la opción con mayor similitud
        best_idx = similarities.argmax()
        best_option = options[best_idx]
        confidence = float(similarities[best_idx])

        return best_option, confidence

    def classify_tags(image, tag_options, threshold=0.25, category_context: str = "garment"):
        """
        Clasifica múltiples tags que aplican a la imagen.
        Retorna lista de tags con confianza superior al umbral.
        """
        # Preprocesar imagen
        image_input = preprocess(image).unsqueeze(0).to(device)

        # Crear prompts textuales para cada tag, sesgados a la categoría
        text_prompts = [f"a {tag} style {category_context}" for tag in tag_options]
        text_tokens = clip.tokenize(text_prompts).to(device)

        # Generar embeddings
        with torch.no_grad():
            image_features = model.encode_image(image_input)
            text_features = model.encode_text(text_tokens)

            # Normalizar
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # Calcular similitudes
            similarities = (image_features @ text_features.T).cpu().numpy()[0]

        # Filtrar tags con confianza superior al umbral
        relevant_tags = []
        for i, tag in enumerate(tag_options):
            if similarities[i] > threshold:
                relevant_tags.append((tag, float(similarities[i])))

        # Ordenar por confianza descendente
        relevant_tags.sort(key=lambda x: x[1], reverse=True)

        return relevant_tags

    def image_text_similarity(pil_image, text: str) -> float:
        """Calcula similitud CLIP entre una imagen PIL y un texto."""
        with torch.no_grad():
            img = preprocess(pil_image).unsqueeze(0).to(device)
            txt = clip.tokenize([text]).to(device)
            img_f = model.encode_image(img)
            txt_f = model.encode_text(txt)
            img_f = img_f / img_f.norm(dim=-1, keepdim=True)
            txt_f = txt_f / txt_f.norm(dim=-1, keepdim=True)
            sim = (img_f @ txt_f.T).cpu().numpy()[0][0]
            return float(sim)

    def best_category_crop(image: Image.Image, category_context: str) -> Image.Image:
        """Explora crops candidatos y devuelve el que mayor similitud tiene con la categoría.
        Estrategia lightweight: distintas escalas (100%, 90%, 80%, 70%) y posiciones (centro y esquinas).
        """
        W, H = image.size
        min_side = min(W, H)
        scales = [1.0, 0.9, 0.8, 0.7]
        positions = [
            (0.5, 0.5),  # centro
            (0.2, 0.2),  # sup-izq
            (0.8, 0.2),  # sup-der
            (0.2, 0.8),  # inf-izq
            (0.8, 0.8),  # inf-der
            (0.5, 0.3),  # centro alto
            (0.5, 0.7),  # centro bajo
        ]
        prompt = f"a photo of a {category_context}"
        best_sim = -1.0
        best_crop = image
        for s in scales:
            crop_size = int(min_side * s)
            for (cx, cy) in positions:
                left = int(max(0, min(W - crop_size, cx * W - crop_size / 2)))
                top = int(max(0, min(H - crop_size, cy * H - crop_size / 2)))
                box = (left, top, left + crop_size, top + crop_size)
                crop = image.crop(box)
                sim = image_text_similarity(crop, prompt)
                if sim > best_sim:
                    best_sim = sim
                    best_crop = crop
        return best_crop

    def transform_cloudinary_url(url: str) -> str:
        """Inserta transformación de enfoque automático de Cloudinary para centrar el sujeto."""
        # Reemplaza /upload/ por /upload/c_fill,g_auto,w_800,h_800/
        try:
            if "/upload/" in url:
                return url.replace("/upload/", "/upload/c_fill,g_auto,w_800,h_800/")
        except Exception:
            pass
        return url

    def download_image(url):
        """Descarga una imagen desde URL y la convierte a PIL Image."""
        try:
            turl = transform_cloudinary_url(url)
            response = requests.get(turl, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert('RGB')
        except Exception as e:
            print(f"  Error descargando imagen {url}: {e}")
            return None

    # Conectar a la base de datos
    print("Conectando a la base de datos...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("Conexión exitosa")

    # Cargar atributos dinámicamente desde product_attribute_config
    print("\nCargando configuración de atributos por cliente...")
    cursor.execute("""
    SELECT c.id, c.name, pac.key, pac.label, pac.type, pac.options, pac.field_order
        FROM clients c
        JOIN product_attribute_config pac ON c.id = pac.client_id
        WHERE pac.type = 'list' AND pac.options IS NOT NULL
        ORDER BY c.id, pac.field_order
    """)

    # Organizar atributos por cliente
    client_attributes = {}
    for client_id, client_name, attr_key, attr_label, attr_type, attr_options, field_order in cursor.fetchall():
        if client_id not in client_attributes:
            client_attributes[client_id] = {
                'name': client_name,
                'attributes': {}
            }

        # Extraer valores del JSON options
        if attr_options and isinstance(attr_options, dict) and 'values' in attr_options:
            values = attr_options['values']
            if values:
                client_attributes[client_id]['attributes'][attr_key] = {
                    'label': attr_label,
                    'values': values
                }

    print(f"Configuración cargada para {len(client_attributes)} cliente(s)")
    for client_id, config in client_attributes.items():
        print(f"  - {config['name']}: {len(config['attributes'])} atributos configurados")
        for attr_key, attr_info in config['attributes'].items():
            print(f"    • {attr_info['label']} ({attr_key}): {len(attr_info['values'])} opciones")

    # Obtener productos sin atributos o con atributos vacíos
    # Incluimos la categoría (name_en, clip_prompt, name) y client_id del producto
    print("\nBuscando productos para procesar...")
    cursor.execute("""
        SELECT DISTINCT p.id, p.name, p.sku, p.attributes, p.client_id,
               c.name as category_name, c.name_en as category_name_en, c.clip_prompt as category_clip_prompt
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE EXISTS (SELECT 1 FROM images i WHERE i.product_id = p.id AND i.cloudinary_url IS NOT NULL)
        AND (p.attributes IS NULL OR p.attributes = '{}' OR p.attributes = '[]')
    """)

    products = cursor.fetchall()
    print(f"Encontrados {len(products)} productos para procesar (SIN LÍMITE - procesando todos)\n")

    if len(products) == 0:
        print("No hay productos para procesar. El script terminará.")
        cursor.close()
        conn.close()
        sys.exit(0)

    # Procesar cada producto
    processed = 0
    errors = 0

    for product_id, name, sku, current_attrs, client_id, category_name, category_name_en, category_clip_prompt in products:
        print(f"Procesando: {name} (SKU: {sku})")
        print(f"  Cliente ID: {client_id}")
        print(f"  Categoría: {category_name}")

        # Determinar contexto de categoría de forma dinámica
        # Prioridad: clip_prompt > name_en > name > "garment"
        category_ctx = category_clip_prompt or category_name_en or category_name or "garment"
        print(f"  Contexto CLIP: {category_ctx}")

        # Obtener atributos configurados para este cliente
        if client_id not in client_attributes:
            print(f"  ⚠️  Cliente sin atributos configurados, usando atributos por defecto")
            # Usar atributos por defecto si el cliente no tiene configuración
            ATTRIBUTE_OPTIONS = {
                "color": [
                    "rojo", "azul", "verde", "amarillo", "naranja", "morado", "rosa",
                    "marrón", "negro", "blanco", "gris", "beige", "celeste", "turquesa",
                    "café", "chocolate", "crema", "dorado", "plateado"
                ],
                "material": [
                    "algodón", "jean", "denim", "poliéster", "lino", "seda", "lana",
                    "cuero", "sintético", "tela", "metal", "plástico", "madera",
                    "nylon", "spandex", "lycra"
                ]
            }
        else:
            # Usar atributos configurados por el cliente
            print(f"  Usando {len(client_attributes[client_id]['attributes'])} atributos configurados")
            ATTRIBUTE_OPTIONS = {}
            for attr_key, attr_info in client_attributes[client_id]['attributes'].items():
                ATTRIBUTE_OPTIONS[attr_key] = attr_info['values']

        # Obtener TODAS las imágenes del producto (con flags para ponderación)
        cursor.execute("""
            SELECT cloudinary_url, COALESCE(is_primary, false) AS is_primary, COALESCE(display_order, 0) AS display_order
            FROM images
            WHERE product_id = %s AND cloudinary_url IS NOT NULL
            ORDER BY is_primary DESC, display_order ASC
        """, (product_id,))
        rows_images = cursor.fetchall()
        print(f"  Imágenes encontradas: {len(rows_images)}")

        if not rows_images:
            print(f"  ! No hay imágenes para procesar\n")
            errors += 1
            continue

        # Acumuladores para combinar resultados de todas las imágenes
        all_attributes = {attr_name: {} for attr_name in ATTRIBUTE_OPTIONS.keys()}
        all_tags = {}

        # Procesar cada imagen (category_ctx ya determinado arriba)
        for idx, (image_url, is_primary, display_order) in enumerate(rows_images, 1):
            print(f"  Analizando imagen {idx}/{len(rows_images)}: {image_url[:50]}... {'(PRINCIPAL)' if is_primary else ''}")

            # Descargar imagen
            image = download_image(image_url)
            if image is None:
                print(f"    ✗ Error descargando imagen")
                continue
            # Peso mayor para imagen principal
            weight = 1.6 if is_primary else 1.0

            # Encontrar el mejor recorte guiado por categoría para reducir sesgo por fondo
            try:
                cropped = best_category_crop(image, category_ctx)
                image = cropped
            except Exception as e:
                print(f"    ! No se pudo aplicar recorte guiado: {e}")

            # Clasificar atributos visuales con CLIP
            for attr_name, options in ATTRIBUTE_OPTIONS.items():
                best_option, confidence = classify_attribute(image, attr_name, options, category_ctx, name)

                # Acumular resultados (conteo de votos ponderado por confianza)
                if confidence > 0.2:
                    if best_option not in all_attributes[attr_name]:
                        all_attributes[attr_name][best_option] = 0
                    all_attributes[attr_name][best_option] += confidence * weight

            # Clasificar tags relevantes
            relevant_tags = classify_tags(image, TAG_OPTIONS, threshold=0.25, category_context=category_ctx)
            for tag, confidence in relevant_tags:
                if tag not in all_tags:
                    all_tags[tag] = 0
                all_tags[tag] += confidence * weight

        # Consolidar atributos finales (el más votado por imagen)
        new_attributes = {}

        # Agregar la categoría como atributo (ya definida por el usuario)
        if category_name:
            new_attributes["categoria"] = category_name

        print(f"\n  Consolidando resultados de {len(rows_images)} imagen(es):")

        for attr_name, votes in all_attributes.items():
            if votes:
                # Elegir el atributo con mayor peso acumulado
                best_option = max(votes.items(), key=lambda x: x[1])
                avg_confidence = best_option[1] / len(rows_images)
                new_attributes[attr_name] = best_option[0]
                print(f"    {attr_name}: {best_option[0]} (confianza promedio: {avg_confidence:.2f})")
            else:
                print(f"    {attr_name}: No detectado")

        # Consolidar tags finales (top 3 con mayor peso)
        if all_tags:
            sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:3]
            tag_names = [tag for tag, _ in sorted_tags]
            tags_str = ", ".join(tag_names)
            avg_confidences = [(tag, weight / len(rows_images)) for tag, weight in sorted_tags]
            print(f"    Tags: {tags_str}")
            print(f"    Confianzas promedio: {', '.join([f'{tag}={conf:.2f}' for tag, conf in avg_confidences])}")
        else:
            tags_str = ""
            print(f"    Tags: No detectados")

        # Actualizar en la base de datos (atributos y tags)
        if new_attributes or tags_str:
            try:
                if new_attributes and tags_str:
                    cursor.execute("""
                        UPDATE products
                        SET attributes = %s, tags = %s
                        WHERE id = %s
                    """, (json.dumps(new_attributes), tags_str, product_id))
                elif new_attributes:
                    cursor.execute("""
                        UPDATE products
                        SET attributes = %s
                        WHERE id = %s
                    """, (json.dumps(new_attributes), product_id))
                elif tags_str:
                    cursor.execute("""
                        UPDATE products
                        SET tags = %s
                        WHERE id = %s
                    """, (tags_str, product_id))

                conn.commit()
                print(f"  ✓ Guardado - Atributos: {new_attributes}, Tags: {tags_str}\n")
                processed += 1
            except Exception as e:
                print(f"  ✗ Error guardando: {e}\n")
                conn.rollback()
                errors += 1
        else:
            print(f"  ! No se detectaron atributos ni tags con confianza suficiente\n")

    # Resumen
    print("\n" + "="*60)
    print(f"RESUMEN:")
    print(f"  Productos procesados exitosamente: {processed}")
    print(f"  Errores: {errors}")
    print(f"  Total: {len(products)}")
    print("="*60)

    cursor.close()
    conn.close()
    print("\nScript finalizado correctamente")

except Exception as e:
    print(f"\nERROR FATAL: {e}")
    import traceback
    traceback.print_exc()
