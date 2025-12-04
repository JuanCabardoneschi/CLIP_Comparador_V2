"""
Blueprint de Categorías
Gestión de categorías de productos
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.category import Category
from app.models.product import Product
from slugify import slugify

bp = Blueprint("categories", __name__)


@bp.route("/")
@login_required
def index():
    """Lista de categorías del cliente actual"""
    # Filtrar solo las categorías del cliente del usuario actual
    if not current_user.client_id:
        flash("Usuario no asignado a ningún cliente", "error")
        return redirect(url_for('dashboard.index'))

    categories = Category.query.filter_by(client_id=current_user.client_id).all()

    # Calcular estadísticas
    total_categories = len(categories)
    active_categories = len([c for c in categories if c.is_active])
    inactive_categories = len([c for c in categories if not c.is_active])

    # Calcular categorías con productos y agregar conteo a cada categoría
    categories_with_products = 0
    for category in categories:
        product_count = Product.query.filter_by(category_id=category.id).count()
        category.product_count = product_count  # Agregar como atributo temporal
        if product_count > 0:
            categories_with_products += 1

    return render_template("categories/index.html",
                           categories=categories,
                           total_categories=total_categories,
                           active_categories=active_categories,
                           inactive_categories=inactive_categories,
                           categories_with_products=categories_with_products)


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """Crear nueva categoría para el cliente actual"""
    # ⛔ STORE_ADMIN de Tiendanube NO puede crear categorías
    if current_user.is_store_admin and current_user.client:
        if current_user.client.integration_type == 'tiendanube' or current_user.client.is_read_only:
            flash("No puedes crear categorías. Las categorías se sincronizan automáticamente desde Tiendanube.", "error")
            return redirect(url_for("categories.index"))

    print(f"🏷️ CATEGORIES CREATE: Método {request.method}")
    print(f"🏷️ CATEGORIES CREATE: Usuario autenticado: {current_user.is_authenticated}")
    print(f"🏷️ CATEGORIES CREATE: Usuario email: {current_user.email if current_user.is_authenticated else 'N/A'}")
    print(f"🏷️ CATEGORIES CREATE: Client ID: {current_user.client_id if current_user.is_authenticated else 'N/A'}")

    # Verificar que el usuario tenga cliente asignado
    if not current_user.client_id:
        flash("Usuario no asignado a ningún cliente", "error")
        return redirect(url_for('dashboard.index'))

    if request.method == "POST":
        name = request.form.get("name")
        name_en = request.form.get("name_en", "")  # Permitir sobrescribir traducción
        alternative_terms = request.form.get("alternative_terms", "")
        description = request.form.get("description", "")
        color = request.form.get("color", "#007bff")
        vision_hint = request.form.get("vision_hint", "").strip()
        is_active = request.form.get("is_active") == "on"

        if not name:
            flash("El nombre de la categoría es requerido", "error")
            return render_template("categories/create.html")

        # Verificar que no exista una categoría con el mismo nombre para este cliente
        existing = Category.query.filter_by(name=name, client_id=current_user.client_id).first()
        if existing:
            flash("Ya existe una categoría con ese nombre para este cliente", "error")
            return render_template("categories/create.html")

        # Si no se proporcionó traducción manual, usar traducción automática
        if not name_en.strip():
            client_industry = current_user.client.industry if current_user.client else 'general'
            name_en = Category.auto_translate_to_english(name, client_industry)

        # Obtener características visuales del formulario (opcional)
        visual_features = request.form.get("visual_features", "")

        # Generar prompt CLIP optimizado con términos alternativos
        clip_prompt = Category.generate_clip_prompt(name_en, visual_features, alternative_terms)
        if visual_features:
            clip_prompt = Category.generate_clip_prompt(name_en, visual_features)

        # Crear categoría con campos bilingües
        category = Category(
            name=name,
            name_en=name_en,
            alternative_terms=alternative_terms,
            description=description,
            vision_hint=vision_hint if vision_hint else None,
            clip_prompt=clip_prompt,
            visual_features=visual_features,
            confidence_threshold=float(request.form.get("confidence_threshold", "0.75")),
            color=color,
            is_active=is_active,
            client_id=current_user.client_id  # Usar automáticamente el cliente del usuario
        )
        db.session.add(category)
        db.session.commit()

        flash(f"Categoría '{name}' creada exitosamente", "success")
        return redirect(url_for("categories.view", category_id=category.id))

    return render_template("categories/create.html")


@bp.route("/<category_id>")
@login_required
def view(category_id):
    """Ver detalles de una categoría"""
    category = Category.query.get_or_404(category_id)
    # TODO: Implementar cuando el modelo Product esté listo
    # products = Product.query.filter_by(category_id=category_id).all()
    products = []  # Lista vacía por ahora

    return render_template("categories/view.html",
                           category=category,
                           products=products)


@bp.route("/<category_id>/edit", methods=["GET", "POST"])
@login_required
def edit(category_id):
    """Editar categoría"""
    from app.models.tiendanube_integration import TiendanubeIntegration

    category = Category.query.get_or_404(category_id)

    # Verificar que la categoría pertenece al cliente del usuario actual
    if category.client_id != current_user.client_id:
        flash("No tienes permisos para editar esta categoría", "error")
        return redirect(url_for("categories.index"))

    # Determinar si la categoría viene de TiendaNube
    is_tiendanube = TiendanubeIntegration.query.filter_by(
        client_id=category.client_id,
        is_active=True
    ).first() is not None

    if request.method == "GET":
        print(f"🏷️ CATEGORIES EDIT GET: Category: {category.name}")

    if request.method == "POST":
        print("🏷️ CATEGORIES EDIT: Método POST")
        print(f"🏷️ CATEGORIES EDIT: Usuario autenticado: {current_user.is_authenticated}")
        print(f"🏷️ CATEGORIES EDIT: Usuario email: {current_user.email}")
        print(f"🏷️ CATEGORIES EDIT: Category ID: {category_id}")

        # Obtener datos del formulario
        name = request.form.get("name", "").strip()
        name_en = request.form.get("name_en", "").strip()
        description = request.form.get("description", "").strip()
        alternative_terms = request.form.get("alternative_terms", "").strip()
        vision_hint = request.form.get("vision_hint", "").strip()
        color = request.form.get("color", "#007bff")
        is_active = request.form.get("is_active") == "on"

        # ✅ Si es Tiendanube: SOLO editar campos permitidos
        if is_tiendanube:
            # Solo actualizar: name_en, alternative_terms, description, vision_hint
            if not name_en:
                flash("El nombre en inglés es obligatorio", "error")
                return render_template("categories/edit.html",
                                     category=category,
                                     is_tiendanube=is_tiendanube)

            category.name_en = name_en
            category.alternative_terms = alternative_terms if alternative_terms else None
            category.description = description if description else None
            category.vision_hint = vision_hint if vision_hint else None

            db.session.commit()
            flash(f"Campos editables actualizados exitosamente", "success")
            return redirect(url_for("categories.view", category_id=category.id))

        # ⚙️ Si NO es Tiendanube: edición completa (comportamiento original)
        # Validaciones
        if not name:
            flash("El nombre de la categoría es obligatorio", "error")
            return render_template("categories/edit.html",
                                 category=category,
                                 is_tiendanube=is_tiendanube)

        if not name_en:
            flash("El nombre en inglés es obligatorio", "error")
            return render_template("categories/edit.html",
                                 category=category,
                                 is_tiendanube=is_tiendanube)

        # Actualizar slug si cambió el nombre
        if name != category.name:
            new_slug = slugify(name)
            existing = Category.query.filter_by(
                slug=new_slug,
                client_id=category.client_id
            ).first()

            if existing and existing.id != category.id:
                flash("Ya existe una categoría con ese nombre", "error")
                return render_template("categories/edit.html",
                                     category=category,
                                     is_tiendanube=is_tiendanube)

            category.slug = new_slug

        # Actualizar todos los campos
        category.name = name
        category.name_en = name_en
        category.description = description if description else None
        category.alternative_terms = alternative_terms if alternative_terms else None
        category.color = color
        category.vision_hint = vision_hint if vision_hint else None
        category.is_active = is_active

        db.session.commit()
        flash(f"Categoría '{name}' actualizada exitosamente", "success")
        return redirect(url_for("categories.view", category_id=category.id))

    return render_template("categories/edit.html",
                         category=category,
                         is_tiendanube=is_tiendanube)


@bp.route("/<category_id>/delete", methods=["POST"])
@login_required
def delete(category_id):
    """Eliminar categoría y todos sus productos asociados.

    Al eliminar una categoría:
    1. Elimina imágenes de Cloudinary usando cloudinary.uploader.destroy()
    2. Elimina todos los embeddings de imágenes de los productos
    3. Elimina registros de imágenes de la BD
    4. Elimina todos los productos asociados
    5. Elimina la categoría
    6. Recalcula centroides de las categorías restantes
    """
    category = Category.query.get_or_404(category_id)

    # Verificar permisos del cliente
    if category.client_id != current_user.client_id:
        flash("No tienes permisos para eliminar esta categoría", "error")
        return redirect(url_for("categories.index"))

    try:
        category_name = category.name

        # 1. Obtener productos asociados
        products = Product.query.filter_by(category_id=category_id).all()
        product_count = len(products)

        # 2. Eliminar imágenes de Cloudinary y BD
        from app.models.image import Image
        import cloudinary.uploader
        images_count = 0
        embeddings_count = 0
        cloudinary_deleted = 0
        cloudinary_errors = 0

        for product in products:
            # Obtener imágenes del producto
            images = Image.query.filter_by(product_id=product.id).all()
            images_count += len(images)

            for image in images:
                if image.clip_embedding:
                    embeddings_count += 1

                # Eliminar de Cloudinary
                if image.cloudinary_public_id:
                    try:
                        result = cloudinary.uploader.destroy(image.cloudinary_public_id)
                        if result.get('result') == 'ok':
                            cloudinary_deleted += 1
                            print(f"🗑️ Cloudinary: {image.cloudinary_public_id} eliminado")
                        else:
                            cloudinary_errors += 1
                            print(f"⚠️ Cloudinary: {image.cloudinary_public_id} - {result.get('result', 'error')}")
                    except Exception as e:
                        cloudinary_errors += 1
                        print(f"❌ Error eliminando de Cloudinary {image.cloudinary_public_id}: {e}")

                # Eliminar registro de BD
                db.session.delete(image)

        # 3. Eliminar productos
        for product in products:
            db.session.delete(product)

        # 4. Eliminar la categoría
        db.session.delete(category)
        db.session.commit()

        # 5. Recalcular centroides de categorías restantes del cliente
        remaining_categories = Category.query.filter_by(
            client_id=current_user.client_id,
            is_active=True
        ).all()

        recalculated_count = 0
        for cat in remaining_categories:
            try:
                if cat.needs_centroid_update():
                    cat.update_centroid_embedding(force_recalculate=True)
                    recalculated_count += 1
            except Exception as e:
                print(f"⚠️ Error recalculando centroide de {cat.name}: {e}")

        db.session.commit()

        # Mensaje de confirmación con detalles de Cloudinary
        flash(
            f"✅ Categoría '{category_name}' eliminada. "
            f"{product_count} productos eliminados, "
            f"{images_count} imágenes eliminadas, "
            f"{embeddings_count} embeddings eliminados, "
            f"{recalculated_count} centroides recalculados. "
            f"Cloudinary: {cloudinary_deleted} eliminadas" +
            (f", {cloudinary_errors} errores" if cloudinary_errors > 0 else ""),
            "success" if cloudinary_errors == 0 else "warning"
        )

        print(f"🗑️ Categoría '{category_name}' eliminada:")
        print(f"   - Productos eliminados: {product_count}")
        print(f"   - Imágenes eliminadas: {images_count}")
        print(f"   - Embeddings eliminados: {embeddings_count}")
        print(f"   - Centroides recalculados: {recalculated_count}")
        print(f"   - Cloudinary eliminadas: {cloudinary_deleted}")
        if cloudinary_errors > 0:
            print(f"   - ⚠️ Cloudinary errores: {cloudinary_errors}")

        return redirect(url_for("categories.index"))

    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar categoría: {str(e)}", "error")
        print(f"❌ Error eliminando categoría {category_name}: {e}")
        return redirect(url_for("categories.view", category_id=category_id))


@bp.route("/api/by-client/<client_id>")
@login_required
def api_by_client(client_id):
    """API endpoint para obtener categorías por cliente"""
    categories = Category.query.filter_by(client_id=client_id).all()

    return jsonify([{
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "product_count": Product.query.filter_by(category_id=category.id).count()
    } for category in categories])


@bp.route("/api/search")
@login_required
def api_search():
    """API endpoint para buscar categorías"""
    query = request.args.get("q", "")
    client_id = request.args.get("client_id")

    if not query:
        return jsonify([])

    categories_query = Category.query.filter(
        Category.name.contains(query) | Category.description.contains(query)
    )

    if client_id:
        categories_query = categories_query.filter_by(client_id=client_id)

    categories = categories_query.limit(10).all()

    return jsonify([{
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "client_name": category.client.name
    } for category in categories])
