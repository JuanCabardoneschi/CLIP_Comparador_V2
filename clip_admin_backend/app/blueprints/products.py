"""
Blueprint de Productos
Gestión de productos del catálogo con subida de imágenes por lotes
"""

import os
import json
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app import db
from app.models.product import Product
from app.models.category import Category
from app.models.image import Image
from app.models.client import Client
from app.models.product_attribute_config import ProductAttributeConfig
from app.services.image_manager import image_manager
from datetime import datetime

bp = Blueprint("products", __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_size(file):
    """Valida el tamaño del archivo"""
    if hasattr(file, 'content_length') and file.content_length:
        return file.content_length <= MAX_FILE_SIZE

    # Si no podemos obtener el tamaño del content_length,
    # lo verificaremos después de guardarlo temporalmente
    return True


def _get_client_attribute_config(client_id):
    """Obtiene la configuración de atributos para un cliente"""
    return ProductAttributeConfig.query.filter_by(
        client_id=client_id
    ).order_by(ProductAttributeConfig.field_order).all()


def _process_dynamic_attributes(request_form, attribute_configs):
    """Procesa los atributos dinámicos desde el formulario y los convierte a dict"""
    attributes = {}

    for config in attribute_configs:
        field_base = f"attr_{config.key}"

        # Detectar si es selección múltiple (solo aplica a type 'list')
        is_multiple = False
        if config.type == 'list' and config.options:
            if isinstance(config.options, dict):
                is_multiple = bool(config.options.get('multiple', False))

        if config.type == 'list' and is_multiple:
            # Para múltiples, el name en el template es attr_<key>[]
            raw_list = request_form.getlist(f"{field_base}[]") or request_form.getlist(field_base)
            values = [v.strip() for v in raw_list if v and v.strip()]

            if config.required and not values:
                raise ValueError(f"El campo '{config.label}' es obligatorio")

            if values:
                attributes[config.key] = values
            # Si no hay valores y no es requerido, no guardamos la clave
            continue

        # Manejo single-value (text, number, date, url, list simple)
        value = (request_form.get(field_base, None) or request_form.get(f"{field_base}[]", "")).strip()

        # Validar requerido
        if config.required and not value:
            raise ValueError(f"El campo '{config.label}' es obligatorio")

        # Procesar según tipo
        if value:
            if config.type == 'number':
                try:
                    attributes[config.key] = float(value)
                except ValueError:
                    raise ValueError(f"El campo '{config.label}' debe ser un número válido")
            elif config.type == 'date':
                # Validar formato de fecha
                try:
                    from datetime import datetime
                    datetime.strptime(value, '%Y-%m-%d')
                    attributes[config.key] = value
                except ValueError:
                    raise ValueError(f"El campo '{config.label}' debe tener formato de fecha válido (YYYY-MM-DD)")
            else:
                # text, list simple, url - guardar como string
                attributes[config.key] = value

    return attributes


def _validate_attribute_options(attributes, attribute_configs):
    """
    Valida que los valores de tipo 'list' estén en las opciones configuradas.
    Formato esperado de options: {'multiple': bool, 'values': [...]}
    """
    for config in attribute_configs:
        if config.type == 'list' and config.key in attributes:
            value = attributes[config.key]

            # Obtener lista de opciones permitidas
            allowed = []
            if config.options and isinstance(config.options, dict):
                allowed = config.options.get('values', [])

            if not allowed:
                continue  # Sin opciones configuradas, no validar

            if isinstance(value, list):
                invalid = [v for v in value if v not in allowed]
                if invalid:
                    raise ValueError(f"Valor(es) no válidos para '{config.label}': {', '.join(invalid)}")
            else:
                if value not in allowed:
                    raise ValueError(f"El valor '{value}' no es válido para '{config.label}'")
    return True


@bp.route("/")
@login_required
def index():
    """Lista de todos los productos"""
    page = request.args.get("page", 1, type=int)
    category_id = request.args.get("category_id")
    search = request.args.get("search", "").strip()

    # Obtener todas las categorías del cliente actual
    categories = Category.query.filter_by(client_id=current_user.client_id).all()

    # Construir query base
    query = Product.query.filter_by(client_id=current_user.client_id)

    # Filtro por categoría
    if category_id:
        query = query.filter_by(category_id=category_id)

    # Filtro por búsqueda
    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f'%{search}%'),
                Product.description.ilike(f'%{search}%'),
                Product.sku.ilike(f'%{search}%'),
                Product.tags.ilike(f'%{search}%')
            )
        )

    # Ordenar y paginar
    products = query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    # Calcular estadísticas totales
    total_products = Product.query.filter_by(client_id=current_user.client_id).count()
    total_categories = Category.query.filter_by(client_id=current_user.client_id).count()

    # Calcular total de imágenes
    total_images = db.session.query(db.func.count(Image.id))\
        .join(Product, Image.product_id == Product.id)\
        .filter(Product.client_id == current_user.client_id).scalar()

    return render_template("products/index.html",
                           products=products,
                           categories=categories,
                           current_category=category_id,
                           search=search,
                           total_products=total_products,
                           total_categories=total_categories,
                           total_images=total_images)


def _validate_product_data(name, category_id, categories):
    """Valida los datos del producto"""
    if not name:
        flash("El nombre del producto es obligatorio", "error")
        return False, render_template("products/create.html", categories=categories)

    if not category_id:
        flash("Debe seleccionar una categoría", "error")
        return False, render_template("products/create.html", categories=categories)

    # Verificar que la categoría pertenece al cliente
    category = Category.query.filter_by(
        id=category_id,
        client_id=current_user.client_id
    ).first()

    if not category:
        flash("Categoría no válida", "error")
        return False, render_template("products/create.html", categories=categories)

    return True, category


def _create_product_instance(name, description, category_id, sku, price, stock, tags):
    """Crea una instancia del producto"""
    return Product(
        client_id=current_user.client_id,
        category_id=category_id,
        name=name,
        description=description,
        sku=sku if sku else None,
        price=float(price) if price else None,
        stock=stock,
        tags=tags if tags else None
    )


def _process_uploaded_images(product, uploaded_files, primary_image_index):
    """Procesa las imágenes subidas para el producto"""
    images_processed = 0
    errors = []

    if not uploaded_files or not uploaded_files[0].filename:
        return images_processed, errors, "No se subieron imágenes válidas"

    for index, file in enumerate(uploaded_files):
        if file and allowed_file(file.filename):
            # Validar tamaño del archivo
            if not validate_file_size(file):
                errors.append(f"Archivo {file.filename} es demasiado grande (máximo 50MB)")
                continue

            try:
                # ✅ USAR IMAGEMANAGER - Lógica centralizada
                client = Client.query.get(current_user.client_id)
                image = image_manager.upload_image(
                    file=file,
                    product_id=product.id,
                    client_id=current_user.client_id,
                    client_slug=client.slug,  # Dinámico desde BD
                    is_primary=(index == primary_image_index)
                )

                if image:
                    images_processed += 1
                else:
                    errors.append(f"No se pudo procesar {file.filename}")

            except ValueError as ve:
                errors.append(f"{file.filename}: {str(ve)}")
            except Exception as e:
                errors.append(f"Error procesando {file.filename}: {str(e)}")

    return images_processed, errors, None


def _generate_success_message(images_processed, errors):
    """Genera mensaje de éxito basado en resultados del procesamiento"""
    if images_processed == 0 and errors:
        flash("No se procesaron imágenes. Errores: " + "; ".join(errors), "error")
        return False
    elif images_processed == 0:
        flash("Producto creado sin imágenes", "warning")
        return True
    else:
        message = f"Producto creado con {images_processed} imagen(es)."
        if errors:
            message += f" Errores en {len(errors)} archivo(s): " + "; ".join(errors[:3])
            if len(errors) > 3:
                message += "..."
        flash(message, "success" if not errors else "warning")
        return True


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """Crear nuevo producto desde colección de imágenes"""
    categories = Category.query.filter_by(client_id=current_user.client_id).all()
    attribute_configs = _get_client_attribute_config(current_user.client_id)

    if request.method == "POST":
        try:
            # Obtener datos del formulario
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            category_id = request.form.get("category_id")
            sku = request.form.get("sku", "").strip()
            price = request.form.get("price")
            stock = request.form.get("stock", 0, type=int)
            tags = request.form.get("tags", "").strip()

            # Procesar atributos dinámicos
            dynamic_attributes = _process_dynamic_attributes(request.form, attribute_configs)
            _validate_attribute_options(dynamic_attributes, attribute_configs)

            # Validar datos del producto
            is_valid, result = _validate_product_data(name, category_id, categories)
            if not is_valid:
                return result

            # Crear producto
            product = _create_product_instance(name, description, category_id, sku, price, stock, tags)

            # Asignar atributos dinámicos
            product.attributes = dynamic_attributes if dynamic_attributes else None

            db.session.add(product)
            db.session.flush()  # Para obtener el ID del producto

            # Procesar imágenes
            uploaded_files = request.files.getlist("images")
            primary_image_index = request.form.get("primary_image", 0, type=int)

            images_processed, errors, error_msg = _process_uploaded_images(product, uploaded_files, primary_image_index)

            if error_msg:
                flash(error_msg, "warning")
            elif not _generate_success_message(images_processed, errors):
                # Si hay errores críticos, hacer rollback
                db.session.rollback()
                return render_template("products/create.html",
                                     categories=categories,
                                     attribute_configs=attribute_configs)

            db.session.commit()

            # Generar embeddings y actualizar centroide de la categoría del producto recién creado
            try:
                _process_embeddings_and_centroid_for_product(product)
            except Exception as e:
                # No bloquear la creación por un fallo en embeddings; mostrar aviso suave
                flash(f"El producto se creó, pero hubo un problema generando el embedding: {str(e)}", "warning")

            # 🤖 Auto-completar atributos usando CLIP (solo si hay imágenes y atributos configurados)
            try:
                from app.services.attribute_autofill_service import AttributeAutofillService

                # Solo ejecutar si el producto tiene imágenes y atributos vacíos/incompletos
                if images_processed > 0:
                    result = AttributeAutofillService.autofill_product_attributes(
                        product,
                        overwrite=False  # No sobrescribir valores que el usuario ya puso
                    )

                    if result['success']:
                        # Mergear atributos detectados con los existentes
                        current_attrs = product.attributes or {}
                        detected_attrs = result['attributes']

                        # Solo agregar atributos que no existan o estén vacíos
                        updated = False
                        for key, value in detected_attrs.items():
                            if key not in current_attrs or not current_attrs.get(key):
                                current_attrs[key] = value
                                updated = True

                        # Actualizar tags si no tiene
                        if result['tags'] and not product.tags:
                            product.tags = result['tags']
                            updated = True

                        if updated:
                            product.attributes = current_attrs
                            db.session.commit()
                            flash(f"✨ Auto-completado: {result['message']}", "info")

            except Exception as e:
                # No bloquear la creación si falla el autofill
                print(f"⚠️ No se pudo auto-completar atributos: {e}")

            return redirect(url_for("products.view", product_id=product.id))

        except ValueError as ve:
            flash(str(ve), "error")
            return render_template("products/create.html",
                                 categories=categories,
                                 attribute_configs=attribute_configs)
        except Exception as e:
            db.session.rollback()
            flash(f"Error al crear el producto: {str(e)}", "error")
            return render_template("products/create.html",
                                 categories=categories,
                                 attribute_configs=attribute_configs)

    return render_template("products/create.html",
                         categories=categories,
                         attribute_configs=attribute_configs)


def _process_embeddings_and_centroid_for_product(product):
    """Genera embeddings para las imágenes pendientes del producto y actualiza el centroide de su categoría.

    Nota: esta función es síncrona y se ejecuta al crear el producto para evitar que el
    usuario tenga que ir al menú de embeddings. Mantiene cambios mínimos y reutiliza
    la lógica existente de generación de embeddings.
    """
    from app.models.image import Image
    from app.blueprints.embeddings import generate_clip_embedding

    # Obtener imágenes pendientes del producto
    pending_images = Image.query.filter_by(
        product_id=product.id,
        is_processed=False,
        upload_status='pending'
    ).all()

    if not pending_images:
        return

    processed = 0
    for image in pending_images:
        # Requiere URL de Cloudinary
        if not image.cloudinary_url:
            image.upload_status = 'failed'
            image.error_message = 'No hay URL de Cloudinary disponible'
            continue

        # Generar embedding con la lógica real (optimizada si hay contexto)
        embedding, metadata = generate_clip_embedding(image.cloudinary_url, image)
        if not embedding:
            image.upload_status = 'failed'
            image.error_message = 'No se generó el embedding'
            continue

        image.clip_embedding = json.dumps(embedding)
        image.is_processed = True
        image.upload_status = 'completed'
        image.error_message = None

        # Guardar metadata si el modelo la soporta
        if hasattr(image, 'metadata') and metadata:
            try:
                image.metadata = json.dumps(metadata)
            except Exception:
                pass

        processed += 1

    # Persistir imágenes procesadas
    db.session.commit()

    # Actualizar centroide de la categoría del producto si corresponde
    category = product.category
    if category and processed > 0:
        try:
            if category.needs_centroid_update():
                category.update_centroid_embedding(force_recalculate=False)
                db.session.commit()
        except Exception:
            db.session.rollback()
            # No propagar excepción para no interrumpir el flujo de creación
            pass


@bp.route("/<product_id>")
@login_required
def view(product_id):
    """Ver detalles de un producto"""
    product = Product.query.filter_by(
        id=product_id,
        client_id=current_user.client_id
    ).first_or_404()

    # Obtener todas las imágenes del producto
    images = Image.query.filter_by(product_id=product_id).order_by(
        Image.is_primary.desc(),
        Image.created_at.asc()
    ).all()

    # Verificar si hay imágenes procesadas
    any_processed = any(img.is_processed for img in images) if images else False

    return render_template("products/view.html",
                           product=product,
                           images=images,
                           any_processed=any_processed)


@bp.route("/<product_id>/edit", methods=["GET", "POST"])
@login_required
def edit(product_id):
    """Editar producto"""
    product = Product.query.filter_by(
        id=product_id,
        client_id=current_user.client_id
    ).first_or_404()

    categories = Category.query.filter_by(client_id=current_user.client_id).all()
    attribute_configs = _get_client_attribute_config(current_user.client_id)

    if request.method == "POST":
        try:
            # Guardar categoría anterior para recalcular centroide si cambia
            old_category_id = product.category_id
            old_category = product.category if old_category_id else None

            # Actualizar datos del producto
            product.name = request.form.get("name", "").strip()
            product.description = request.form.get("description", "").strip()
            product.category_id = request.form.get("category_id")
            product.sku = request.form.get("sku", "").strip() or None
            price = request.form.get("price")
            product.price = float(price) if price else None
            product.stock = request.form.get("stock", 0, type=int)
            product.tags = request.form.get("tags", "").strip() or None
            product.updated_at = datetime.utcnow()

            # Procesar atributos dinámicos
            dynamic_attributes = _process_dynamic_attributes(request.form, attribute_configs)
            _validate_attribute_options(dynamic_attributes, attribute_configs)
            product.attributes = dynamic_attributes if dynamic_attributes else None

            # Validaciones
            if not product.name:
                flash("El nombre del producto es obligatorio", "error")
                return render_template("products/edit.html",
                                     product=product,
                                     categories=categories,
                                     attribute_configs=attribute_configs)

            # Verificar categoría
            new_category = None
            if product.category_id:
                new_category = Category.query.filter_by(
                    id=product.category_id,
                    client_id=current_user.client_id
                ).first()
                if not new_category:
                    flash("Categoría no válida", "error")
                    return render_template("products/edit.html",
                                         product=product,
                                         categories=categories,
                                         attribute_configs=attribute_configs)

            db.session.commit()

            # Recalcular centroides si cambió la categoría
            if old_category_id != product.category_id:
                # Verificar que el producto tiene imágenes procesadas
                has_processed_images = any(img.is_processed for img in product.images)

                if has_processed_images:
                    try:
                        # Recalcular centroide de la categoría ANTIGUA (ya no incluye este producto)
                        if old_category:
                            if old_category.needs_centroid_update():
                                old_category.update_centroid_embedding(force_recalculate=False)
                                print(f"📊 Centroide actualizado para categoría antigua: {old_category.name}")

                        # Recalcular centroide de la categoría NUEVA (ahora incluye este producto)
                        if new_category:
                            if new_category.needs_centroid_update():
                                new_category.update_centroid_embedding(force_recalculate=False)
                                print(f"📊 Centroide actualizado para categoría nueva: {new_category.name}")

                        db.session.commit()
                    except Exception as e:
                        # No bloquear la edición por error en centroides
                        print(f"⚠️ Error actualizando centroides tras cambio de categoría: {e}")
                        db.session.rollback()

            flash("Producto actualizado correctamente", "success")
            return redirect(url_for("products.view", product_id=product.id))

        except ValueError as ve:
            flash(str(ve), "error")
            return render_template("products/edit.html",
                                 product=product,
                                 categories=categories,
                                 attribute_configs=attribute_configs)
        except Exception as e:
            db.session.rollback()
            flash(f"Error al actualizar el producto: {str(e)}", "error")

    return render_template("products/edit.html",
                         product=product,
                         categories=categories,
                         attribute_configs=attribute_configs)


@bp.route("/<product_id>/delete", methods=["POST"])
@login_required
def delete(product_id):
    """Eliminar producto y sus archivos de imagen"""
    product = Product.query.filter_by(
        id=product_id,
        client_id=current_user.client_id
    ).first_or_404()

    try:
        # Guardar referencia a la categoría y verificar si tiene imágenes procesadas
        category = product.category
        has_processed_images = any(img.is_processed for img in product.images)

        # Obtener todas las imágenes antes de eliminar el producto
        images = product.images.all()

        # Eliminar archivos físicos de las imágenes
        for image in images:
            # Solo eliminar archivos físicos si no usan Cloudinary
            if not image.cloudinary_public_id and image.filename:
                client = Client.query.get(current_user.client_id)
                client_folder = client.name.replace(' ', '_').lower()
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'clients', client_folder)
                file_path = os.path.join(upload_folder, image.filename)

                # Eliminar archivo físico si existe
                if os.path.exists(file_path):
                    os.remove(file_path)

        # Eliminar producto (las imágenes se eliminan automáticamente por cascade)
        db.session.delete(product)
        db.session.commit()

        # Recalcular centroide de la categoría si el producto tenía imágenes procesadas
        if category and has_processed_images:
            try:
                if category.needs_centroid_update():
                    category.update_centroid_embedding(force_recalculate=False)
                    db.session.commit()
                    print(f"📊 Centroide actualizado para categoría tras eliminar producto: {category.name}")
            except Exception as e:
                # No bloquear la eliminación por error en centroide
                print(f"⚠️ Error actualizando centroide tras eliminar producto: {e}")
                db.session.rollback()

        flash("Producto e imágenes eliminados correctamente", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar el producto: {str(e)}", "error")

    return redirect(url_for("products.index"))


@bp.route("/<product_id>/autofill-attributes", methods=["POST"])
@login_required
def autofill_attributes(product_id):
    """Endpoint para auto-completar atributos de un producto usando CLIP"""
    product = Product.query.filter_by(
        id=product_id,
        client_id=current_user.client_id
    ).first_or_404()

    try:
        from app.services.attribute_autofill_service import AttributeAutofillService

        # Obtener parámetro overwrite del request (default=False)
        overwrite = request.json.get('overwrite', False) if request.is_json else False

        result = AttributeAutofillService.autofill_product_attributes(product, overwrite=overwrite)

        if result['success']:
            # Actualizar producto con atributos detectados
            current_attrs = product.attributes or {}
            detected_attrs = result['attributes']

            updated_fields = []
            for key, value in detected_attrs.items():
                if overwrite or key not in current_attrs or not current_attrs.get(key):
                    current_attrs[key] = value
                    updated_fields.append(f"{key}: {value}")

            # Actualizar tags si no tiene o si overwrite=True
            if result['tags'] and (overwrite or not product.tags):
                product.tags = result['tags']
                updated_fields.append(f"tags: {result['tags']}")

            if updated_fields:
                product.attributes = current_attrs
                db.session.commit()

                return jsonify({
                    'success': True,
                    'message': f'✨ Atributos auto-completados: {", ".join(updated_fields)}',
                    'attributes': current_attrs,
                    'tags': product.tags
                })
            else:
                return jsonify({
                    'success': True,
                    'message': 'No hay atributos nuevos para completar (todos ya tienen valor)',
                    'attributes': current_attrs,
                    'tags': product.tags
                })
        else:
            return jsonify({
                'success': False,
                'message': result['message']
            }), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@bp.route("/<product_id>/images/add", methods=["POST"])
@login_required
def add_images(product_id):
    """Agregar más imágenes a un producto existente usando ImageManager"""
    product = Product.query.filter_by(
        id=product_id,
        client_id=current_user.client_id
    ).first_or_404()

    try:
        uploaded_files = request.files.getlist("images")

        if not uploaded_files or not uploaded_files[0].filename:
            return jsonify({"success": False, "message": "No se recibieron archivos"})

        images_processed = 0
        errors = []

        for file in uploaded_files:
            if file and file.filename:
                try:
                    # ✅ USAR IMAGEMANAGER - Centralizado y limpio
                    client = Client.query.get(current_user.client_id)
                    image = image_manager.upload_image(
                        file=file,
                        product_id=product.id,
                        client_id=current_user.client_id,
                        client_slug=client.slug,  # Dinámico desde BD
                        is_primary=False  # Nuevas imágenes no son principales
                    )

                    if image:
                        images_processed += 1
                    else:
                        errors.append(f"No se pudo procesar {file.filename}")

                except ValueError as ve:
                    errors.append(f"{file.filename}: {str(ve)}")
                except Exception as e:
                    errors.append(f"Error con {file.filename}: {str(e)}")

        if images_processed > 0:
            db.session.commit()

        # Generar embeddings y actualizar centroide si se agregaron imágenes
        if images_processed > 0:
            try:
                _process_embeddings_and_centroid_for_product(product)
            except Exception as e:
                # Mantener respuesta exitosa aunque falle la generación; informar en mensaje
                errors.append(f"Embeddings: {str(e)}")

        # Preparar respuesta
        if images_processed > 0 and not errors:
            return jsonify({
                "success": True,
                "message": f"{images_processed} imagen(es) agregada(s) correctamente"
            })
        elif images_processed > 0 and errors:
            return jsonify({
                "success": True,
                "message": f"{images_processed} imagen(es) agregada(s). Errores: {'; '.join(errors)}"
            })
        else:
            return jsonify({
                "success": False,
                "message": f"No se procesaron imágenes. Errores: {'; '.join(errors)}"
            })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@bp.route("/<product_id>/images/<image_id>/set-primary", methods=["POST"])
@login_required
def set_primary_image(product_id, image_id):
    """Establecer imagen principal del producto usando ImageManager"""
    # Verificar que el producto pertenece al cliente del usuario
    Product.query.filter_by(
        id=product_id,
        client_id=current_user.client_id
    ).first_or_404()

    try:
        # ✅ USAR IMAGEMANAGER - Método centralizado
        if image_manager.set_primary_image(image_id, product_id):
            return jsonify({"success": True, "message": "Imagen principal actualizada"})
        else:
            return jsonify({"success": False, "message": "Imagen no encontrada"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@bp.route("/<product_id>/images/<image_id>/delete", methods=["POST"])
@login_required
def delete_image(product_id, image_id):
    """Eliminar una imagen del producto y su archivo físico"""
    # Verificar que el producto pertenece al cliente del usuario actual
    product = Product.query.filter_by(
        id=product_id,
        client_id=current_user.client_id
    ).first_or_404()

    try:
        image = Image.query.filter_by(
            id=image_id,
            product_id=product_id
        ).first()

        if image:
            # Guardar referencia a la categoría antes de eliminar
            category = product.category
            was_processed = image.is_processed

            # Eliminar archivo físico
            client = Client.query.get(current_user.client_id)
            if client:
                client_folder = client.name.replace(' ', '_').lower()
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'clients', client_folder)
                file_path = os.path.join(upload_folder, image.filename)

                # Eliminar archivo físico si existe
                if os.path.exists(file_path):
                    os.remove(file_path)

            # Eliminar registro de base de datos
            db.session.delete(image)
            db.session.commit()

            # Recalcular centroide de la categoría si la imagen estaba procesada
            if category and was_processed:
                try:
                    if category.needs_centroid_update():
                        category.update_centroid_embedding(force_recalculate=False)
                        db.session.commit()
                except Exception as e:
                    # No bloquear la eliminación por error en centroide
                    print(f"⚠️ Error actualizando centroide tras eliminar imagen: {e}")
                    db.session.rollback()

            return jsonify({"success": True, "message": "Imagen eliminada correctamente"})
        else:
            return jsonify({"success": False, "message": "Imagen no encontrada"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@bp.route("/api/generate-embeddings", methods=["POST"])
@login_required
def generate_embeddings():
    """Generar embeddings para imágenes pendientes y actualizar tags del producto"""
    try:
        # Obtener imágenes pendientes del cliente
        pending_images = Image.query.filter_by(
            client_id=current_user.client_id,
            is_processed=False,
            upload_status='pending'
        ).limit(10).all()  # Procesar máximo 10 por vez

        if not pending_images:
            return jsonify({"success": True, "message": "No hay imágenes pendientes"})

        # Usar la lógica REAL de generación de embeddings del blueprint de embeddings
        processed = 0
        tags_updated = 0
        from app.blueprints.embeddings import generate_clip_embedding  # import local para evitar ciclos
        from app.services.attribute_autofill_service import AttributeAutofillService

        for image in pending_images:
            try:
                if not image.cloudinary_url:
                    image.upload_status = 'failed'
                    image.error_message = 'No hay URL de Cloudinary disponible'
                    continue

                embedding, metadata = generate_clip_embedding(image.cloudinary_url, image)
                if not embedding:
                    raise Exception('No se generó el embedding')

                image.clip_embedding = json.dumps(embedding)
                image.is_processed = True
                image.upload_status = 'completed'
                image.error_message = None
                processed += 1

                # ✨ Actualizar tags contextuales del producto
                product = Product.query.get(image.product_id)
                if product:
                    result = AttributeAutofillService.autofill_product_attributes(
                        product,
                        overwrite=False
                    )
                    if result['success'] and result['tags']:
                        product.tags = result['tags']
                        tags_updated += 1
                        print(f"  ✓ Tags actualizados para {product.name}: {result['tags']}")

            except Exception as e:
                image.upload_status = 'failed'
                image.error_message = str(e)

        db.session.commit()

        message = f"{processed} embeddings generados"
        if tags_updated > 0:
            message += f" y {tags_updated} productos con tags actualizados"

        return jsonify({
            "success": True,
            "message": message
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@bp.route("/api/regenerate-all-tags", methods=["POST"])
@login_required
def regenerate_all_tags():
    """Regenerar tags contextuales para todos los productos con imágenes"""
    try:
        from app.services.attribute_autofill_service import AttributeAutofillService

        # Obtener solo productos del cliente actual que tengan imágenes
        products = Product.query.filter_by(
            client_id=current_user.client_id
        ).all()

        products_with_images = [p for p in products if p.images.count() > 0]

        if not products_with_images:
            return jsonify({
                "success": False,
                "message": "No hay productos con imágenes para procesar"
            })

        updated = 0
        failed = 0

        for product in products_with_images:
            try:
                # Solo regenerar tags, no sobrescribir atributos existentes
                result = AttributeAutofillService.autofill_product_attributes(
                    product,
                    overwrite=False
                )

                if result['success'] and result['tags']:
                    # Actualizar tags (siempre sobrescribimos tags para obtener los nuevos contextuales)
                    product.tags = result['tags']
                    updated += 1
                    print(f"✓ {product.name}: {result['tags']}")
                else:
                    failed += 1

            except Exception as e:
                failed += 1
                print(f"❌ Error en {product.name}: {e}")
                continue

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"✨ Tags actualizados: {updated} productos exitosos, {failed} fallidos",
            "updated": updated,
            "failed": failed,
            "total": len(products_with_images)
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        })
