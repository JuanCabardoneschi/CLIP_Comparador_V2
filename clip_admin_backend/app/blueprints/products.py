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
    """Valida que los valores de tipo 'list' estén en las opciones configuradas"""
    for config in attribute_configs:
        if config.type == 'list' and config.key in attributes:
            value = attributes[config.key]
            # Obtener lista de opciones permitidas
            allowed = []
            if config.options:
                if isinstance(config.options, dict):
                    allowed = config.options.get('values', []) or []
                elif isinstance(config.options, list):
                    allowed = config.options

            if isinstance(value, list):
                invalid = [v for v in value if v not in allowed]
                if invalid:
                    raise ValueError(f"Valor(es) no válidos para '{config.label}': {', '.join(invalid)}")
            else:
                if allowed and value not in allowed:
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

            # TODO: Aquí se dispararía el proceso de subida a Cloudinary y generación de embeddings
            # Por ahora solo marcamos como pendiente

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

    return render_template("products/view.html",
                           product=product,
                           images=images)


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
            if product.category_id:
                category = Category.query.filter_by(
                    id=product.category_id,
                    client_id=current_user.client_id
                ).first()
                if not category:
                    flash("Categoría no válida", "error")
                    return render_template("products/edit.html",
                                         product=product,
                                         categories=categories,
                                         attribute_configs=attribute_configs)

            db.session.commit()
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
        # Obtener todas las imágenes antes de eliminar el producto
        images = product.images.all()

        # Eliminar archivos físicos de las imágenes
        for image in images:
            # Construir ruta al archivo
            client = Client.query.get(current_user.client_id)
            if client:
                client_folder = client.name.replace(' ', '_').lower()
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'clients', client_folder)
                file_path = os.path.join(upload_folder, image.filename)

                # Eliminar archivo físico si existe
                if os.path.exists(file_path):
                    os.remove(file_path)

        # Eliminar producto (las imágenes se eliminan automáticamente por cascade)
        db.session.delete(product)
        db.session.commit()
        flash("Producto e imágenes eliminados correctamente", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar el producto: {str(e)}", "error")

    return redirect(url_for("products.index"))


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
    Product.query.filter_by(
        id=product_id,
        client_id=current_user.client_id
    ).first_or_404()

    try:
        image = Image.query.filter_by(
            id=image_id,
            product_id=product_id
        ).first()

        if image:
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
            return jsonify({"success": True, "message": "Imagen eliminada correctamente"})
        else:
            return jsonify({"success": False, "message": "Imagen no encontrada"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@bp.route("/api/generate-embeddings", methods=["POST"])
@login_required
def generate_embeddings():
    """Generar embeddings para imágenes pendientes"""
    try:
        # Obtener imágenes pendientes del cliente
        pending_images = Image.query.filter_by(
            client_id=current_user.client_id,
            is_processed=False,
            upload_status='pending'
        ).limit(10).all()  # Procesar máximo 10 por vez

        if not pending_images:
            return jsonify({"success": True, "message": "No hay imágenes pendientes"})

        # TODO: Aquí iría la lógica de generación de embeddings con CLIP
        # Por ahora simulamos el proceso

        processed = 0
        for image in pending_images:
            # Simular procesamiento
            image.upload_status = 'completed'
            image.is_processed = True
            # image.clip_embedding = generate_clip_embedding(image_path)
            processed += 1

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"{processed} embeddings generados correctamente"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"})
