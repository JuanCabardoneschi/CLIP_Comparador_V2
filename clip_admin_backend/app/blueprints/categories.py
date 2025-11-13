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
    category = Category.query.get_or_404(category_id)

    # Verificar que la categoría pertenece al cliente del usuario actual
    if category.client_id != current_user.client_id:
        flash("No tienes permisos para editar esta categoría", "error")
        return redirect(url_for("categories.index"))

    # Debug: Ver vision_hint al cargar
    if request.method == "GET":
        print(f"🏷️ CATEGORIES EDIT GET: Category: {category.name}")
        print(f"🏷️ CATEGORIES EDIT GET: vision_hint value: {repr(category.vision_hint)}")

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

        # Validaciones
        if not name:
            flash("El nombre de la categoría es obligatorio", "error")
            return render_template("categories/edit.html", category=category)

        if not name_en:
            flash("El nombre en inglés es obligatorio", "error")
            return render_template("categories/edit.html", category=category)

        # Actualizar slug si cambió el nombre
        if name != category.name:
            new_slug = slugify(name)
            existing = Category.query.filter_by(
                slug=new_slug,
                client_id=category.client_id
            ).first()

            if existing and existing.id != category.id:
                flash("Ya existe una categoría con ese nombre", "error")
                return render_template("categories/edit.html", category=category)

            category.slug = new_slug

        # Actualizar todos los campos
        category.name = name
        category.name_en = name_en
        category.description = description if description else None
        category.alternative_terms = alternative_terms if alternative_terms else None
        category.vision_hint = vision_hint if vision_hint else None
        category.color = color
        category.is_active = is_active

        db.session.commit()
        flash(f"Categoría '{name}' actualizada exitosamente", "success")
        return redirect(url_for("categories.view", category_id=category.id))

    return render_template("categories/edit.html", category=category)


@bp.route("/<category_id>/delete", methods=["POST"])
@login_required
def delete(category_id):
    """Eliminar categoría"""
    category = Category.query.get_or_404(category_id)

    # Verificar que no tenga productos
    product_count = Product.query.filter_by(category_id=category_id).count()
    if product_count > 0:
        flash(f"No se puede eliminar la categoría: tiene {product_count} productos asociados", "error")
        return redirect(url_for("categories.view", category_id=category_id))

    if request.form.get("confirm") == "DELETE":
        db.session.delete(category)
        db.session.commit()
        flash(f"Categoría '{category.name}' eliminada exitosamente", "success")
        return redirect(url_for("categories.index"))

    flash("Confirmación requerida para eliminar categoría", "error")
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
