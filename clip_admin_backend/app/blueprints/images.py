"""
Blueprint de Imágenes
Gestión de imágenes de productos y embeddings
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app as app
from flask_login import login_required, current_user
from app import db
from app.models.image import Image
from app.models.product import Product
from app.models.category import Category
from app.services.image_manager import image_manager
import os

bp = Blueprint("images", __name__)


@bp.route("/")
@login_required
def index():
    """Lista de todas las imágenes"""
    page = request.args.get("page", 1, type=int)
    product_id = request.args.get("product_id")
    client_id = request.args.get("client_id")

    query = Image.query.join(Product).join(Category)

    if product_id:
        query = query.filter(Product.id == product_id)

    if client_id:
        query = query.filter(Category.client_id == client_id)

    images = query.paginate(
        page=page, per_page=24, error_out=False
    )

    return render_template("images/index.html", images=images)


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Subir nueva imagen"""
    if request.method == "POST":
        product_id = request.form.get("product_id")
        files = request.files.getlist("images")

        if not product_id:
            flash("Producto requerido", "error")
            return render_template("images/upload.html")

        product = Product.query.get_or_404(product_id)
        uploaded_count = 0
        errors = []

        for file in files:
            if file and file.filename:
                try:
                    # Usar el ImageManager para subir la imagen (client_slug auto-detectado)
                    image = image_manager.upload_image(
                        file=file,
                        product_id=product_id,
                        client_id=product.category.client_id
                    )

                    if image:
                        uploaded_count += 1
                    else:
                        errors.append(f"No se pudo procesar {file.filename}")

                except ValueError as ve:
                    errors.append(f"{file.filename}: {str(ve)}")
                except Exception as e:
                    errors.append(f"Error subiendo {file.filename}: {str(e)}")

        # Mostrar resultados
        if uploaded_count > 0:
            db.session.commit()

            # Generar embeddings y actualizar centroide
            try:
                from app.blueprints.products import _process_embeddings_and_centroid_for_product
                _process_embeddings_and_centroid_for_product(product)
            except Exception as e:
                flash(f"Imágenes subidas, pero error generando embeddings: {str(e)}", "warning")

            flash(f"{uploaded_count} imagen(es) subida(s) exitosamente", "success")

        for error in errors:
            flash(error, "error")

        if uploaded_count > 0:
            return redirect(url_for("products.view", product_id=product_id))

    products = Product.query.join(Category).all()
    return render_template("images/upload.html", products=products)


@bp.route("/<image_id>")
@login_required
def view(image_id):
    """Ver detalles de una imagen"""
    image = Image.query.get_or_404(image_id)

    # Usar propiedad del modelo (patrón unificado)
    image_url = image.display_url

    return render_template("images/view.html",
                           image=image,
                           image_url=image_url)


@bp.route("/<image_id>/edit", methods=["GET", "POST"])
@login_required
def edit(image_id):
    """Editar metadatos de imagen"""
    image = Image.query.get_or_404(image_id)

    if request.method == "POST":
        image.alt_text = request.form.get("alt_text", image.alt_text)
        image.is_primary = request.form.get("is_primary") == "on"

        # Si se marca como principal, desmarcar otras del mismo producto
        if image.is_primary:
            Image.query.filter_by(
                product_id=image.product_id,
                is_primary=True
            ).update({"is_primary": False})

        db.session.commit()
        flash("Imagen actualizada exitosamente", "success")
        return redirect(url_for("images.view", image_id=image.id))

    return render_template("images/edit.html", image=image)


@bp.route("/<image_id>/delete", methods=["POST"])
@login_required
def delete(image_id):
    """Eliminar imagen"""
    image = Image.query.get_or_404(image_id)
    product_id = image.product_id

    # Guardar referencias antes de eliminar
    product = image.product
    category = product.category if product else None
    was_processed = image.is_processed

    if request.form.get("confirm") == "DELETE":
        try:
            # Usar ImageManager para eliminar la imagen (auto-detecta client_slug)
            if image_manager.delete_image(image):
                db.session.commit()

                # Recalcular centroide si la imagen estaba procesada
                if category and was_processed:
                    try:
                        if category.needs_centroid_update():
                            category.update_centroid_embedding(force_recalculate=False)
                            db.session.commit()
                            print(f"📊 Centroide actualizado para categoría tras eliminar imagen: {category.name}")
                    except Exception as e:
                        # No bloquear la eliminación por error en centroide
                        print(f"⚠️ Error actualizando centroide tras eliminar imagen: {e}")
                        db.session.rollback()

                flash("Imagen eliminada exitosamente", "success")
            else:
                flash("Error eliminando imagen", "error")

        except Exception as e:
            flash(f"Error eliminando imagen: {str(e)}", "error")

        return redirect(url_for("products.view", product_id=product_id))

    flash("Confirmación requerida para eliminar imagen", "error")
    return redirect(url_for("images.view", image_id=image_id))


@bp.route("/<image_id>/generate-embedding", methods=["POST"])
@login_required
def generate_embedding(image_id):
    """Generar embedding CLIP para la imagen"""
    # Verificar que la imagen existe
    Image.query.get_or_404(image_id)

    try:
        # TODO: Implementar generación de embedding CLIP
        # Esta funcionalidad se manejará en el API de búsqueda
        flash("Funcionalidad de embedding movida al API de búsqueda", "info")

    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("images.view", image_id=image_id))


@bp.route("/api/by-product/<product_id>")
@login_required
def api_by_product(product_id):
    """API endpoint para obtener imágenes por producto"""
    images = image_manager.get_images_by_product(product_id)

    return jsonify([{
        "id": image.id,
        "image_url": image.display_url,  # Usar propiedad del modelo (patrón unificado)
        "alt_text": image.alt_text,
        "is_primary": image.is_primary,
        "filename": image.filename
    } for image in images])


# API de búsqueda eliminada - funcionalidad movida completamente a clip_search_api
