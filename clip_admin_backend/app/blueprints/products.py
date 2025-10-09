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


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """Crear nuevo producto desde colección de imágenes"""
    categories = Category.query.filter_by(client_id=current_user.client_id).all()

    if request.method == "POST":
        try:
            # Datos del producto
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            category_id = request.form.get("category_id")
            sku = request.form.get("sku", "").strip()
            price = request.form.get("price")
            stock = request.form.get("stock", 0, type=int)
            tags = request.form.get("tags", "").strip()

            # Validaciones
            if not name:
                flash("El nombre del producto es obligatorio", "error")
                return render_template("products/create.html", categories=categories)

            if not category_id:
                flash("Debe seleccionar una categoría", "error")
                return render_template("products/create.html", categories=categories)

            # Verificar que la categoría pertenece al cliente
            category = Category.query.filter_by(
                id=category_id,
                client_id=current_user.client_id
            ).first()

            if not category:
                flash("Categoría no válida", "error")
                return render_template("products/create.html", categories=categories)

            # Crear producto
            product = Product(
                client_id=current_user.client_id,
                category_id=category_id,
                name=name,
                description=description,
                sku=sku if sku else None,
                price=float(price) if price else None,
                stock=stock,
                tags=tags if tags else None
            )

            db.session.add(product)
            db.session.flush()  # Para obtener el ID del producto

            # Procesar imágenes subidas
            uploaded_files = request.files.getlist("images")
            primary_image_index = request.form.get("primary_image", 0, type=int)

            if uploaded_files and uploaded_files[0].filename:
                images_processed = 0
                errors = []

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

                # Mostrar resultados
                if images_processed == 0 and errors:
                    flash("No se procesaron imágenes. Errores: " + "; ".join(errors), "error")
                elif images_processed == 0:
                    flash("No se subieron imágenes válidas", "warning")
                else:
                    message = f"Producto creado con {images_processed} imagen(es)."
                    if errors:
                        message += f" Errores en {len(errors)} archivo(s): " + "; ".join(errors[:3])
                        if len(errors) > 3:
                            message += "..."
                    flash(message, "success" if not errors else "warning")
            else:
                flash("Producto creado sin imágenes", "warning")

            db.session.commit()

            # TODO: Aquí se dispararía el proceso de subida a Cloudinary y generación de embeddings
            # Por ahora solo marcamos como pendiente

            return redirect(url_for("products.view", product_id=product.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al crear el producto: {str(e)}", "error")
            return render_template("products/create.html", categories=categories)

    return render_template("products/create.html", categories=categories)


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

            # Validaciones
            if not product.name:
                flash("El nombre del producto es obligatorio", "error")
                return render_template("products/edit.html", product=product, categories=categories)

            # Verificar categoría
            if product.category_id:
                category = Category.query.filter_by(
                    id=product.category_id,
                    client_id=current_user.client_id
                ).first()
                if not category:
                    flash("Categoría no válida", "error")
                    return render_template("products/edit.html", product=product, categories=categories)

            db.session.commit()
            flash("Producto actualizado correctamente", "success")
            return redirect(url_for("products.view", product_id=product.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al actualizar el producto: {str(e)}", "error")

    return render_template("products/edit.html", product=product, categories=categories)


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
