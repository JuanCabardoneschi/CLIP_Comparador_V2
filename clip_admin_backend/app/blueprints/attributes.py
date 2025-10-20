"""
Blueprint para administración de atributos de productos
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from .. import db
from ..models.product_attribute_config import ProductAttributeConfig
from ..utils.permissions import admin_required
import json

bp = Blueprint('attributes', __name__, url_prefix='/attributes')

@bp.route('/')
@login_required
@admin_required
def index():
    """Lista de atributos configurados"""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    query = ProductAttributeConfig.query.filter_by(client_id=current_user.client_id)
    query = query.order_by(ProductAttributeConfig.field_order, ProductAttributeConfig.label)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    attributes = pagination.items

    return render_template('attributes/index.html',
                         attributes=attributes,
                         pagination=pagination)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    """Crear nuevo atributo"""
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            key = request.form.get('key', '').strip().lower().replace(' ', '_')
            label = request.form.get('label', '').strip()
            attr_type = request.form.get('type', 'text')
            required = request.form.get('required') == 'on'
            field_order = request.form.get('field_order', 0, type=int)
            expose_in_search = request.form.get('expose_in_search') == 'on'

            # Validaciones básicas
            if not key or not label:
                flash('El nombre interno y la etiqueta son obligatorios', 'danger')
                return render_template('attributes/create.html')

            # Verificar que no exista ya ese key para este cliente
            existing = ProductAttributeConfig.query.filter_by(
                client_id=current_user.client_id,
                key=key
            ).first()

            if existing:
                flash(f'Ya existe un atributo con el nombre interno "{key}"', 'danger')
                return render_template('attributes/create.html')

            # Procesar opciones si el tipo es list
            options = None
            if attr_type == 'list':
                options_raw = request.form.get('options', '').strip()
                is_multiple = request.form.get('is_multiple') == 'on'

                if options_raw:
                    try:
                        # Intentar parsear como JSON
                        options_list = json.loads(options_raw)
                        if not isinstance(options_list, list):
                            raise ValueError("Las opciones deben ser una lista")
                    except json.JSONDecodeError:
                        # Si falla, dividir por líneas o comas
                        options_list = [opt.strip() for opt in options_raw.replace(',', '\n').split('\n') if opt.strip()]

                    options = {
                        'multiple': is_multiple,
                        'values': options_list
                    }
                else:
                    flash('Para atributos de tipo lista, debes especificar al menos una opción', 'warning')
                    return render_template('attributes/create.html')

            # Crear atributo
            attribute = ProductAttributeConfig(
                client_id=current_user.client_id,
                key=key,
                label=label,
                type=attr_type,
                required=required,
                options=options,
                field_order=field_order,
                expose_in_search=expose_in_search
            )

            db.session.add(attribute)
            db.session.commit()

            flash(f'Atributo "{label}" creado correctamente', 'success')
            return redirect(url_for('attributes.index'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error al crear atributo: {str(e)}')
            flash(f'Error al crear atributo: {str(e)}', 'danger')

    return render_template('attributes/create.html')

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    """Editar atributo existente"""
    attribute = ProductAttributeConfig.query.filter_by(
        id=id,
        client_id=current_user.client_id
    ).first_or_404()

    if request.method == 'POST':
        try:
            # Actualizar datos
            attribute.label = request.form.get('label', '').strip()
            attribute.type = request.form.get('type', 'text')
            attribute.required = request.form.get('required') == 'on'
            attribute.field_order = request.form.get('field_order', 0, type=int)
            attribute.expose_in_search = request.form.get('expose_in_search') == 'on'

            # El key no se puede editar para evitar problemas con datos existentes

            # Procesar opciones si el tipo es list
            if attribute.type == 'list':
                options_raw = request.form.get('options', '').strip()
                is_multiple = request.form.get('is_multiple') == 'on'

                if options_raw:
                    try:
                        options_list = json.loads(options_raw)
                        if not isinstance(options_list, list):
                            raise ValueError("Las opciones deben ser una lista")
                    except json.JSONDecodeError:
                        options_list = [opt.strip() for opt in options_raw.replace(',', '\n').split('\n') if opt.strip()]

                    attribute.options = {
                        'multiple': is_multiple,
                        'values': options_list
                    }
                else:
                    flash('Para atributos de tipo lista, debes especificar al menos una opción', 'warning')
                    return render_template('attributes/edit.html', attribute=attribute)
            else:
                attribute.options = None

            db.session.commit()
            flash(f'Atributo "{attribute.label}" actualizado correctamente', 'success')
            return redirect(url_for('attributes.index'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error al actualizar atributo: {str(e)}')
            flash(f'Error al actualizar atributo: {str(e)}', 'danger')

    # Para el formulario, convertir options a string si es lista
    if attribute.options and isinstance(attribute.options, dict):
        if 'values' in attribute.options:
            attribute.options_str = json.dumps(attribute.options['values'], ensure_ascii=False, indent=2)
        else:
            attribute.options_str = json.dumps(attribute.options, ensure_ascii=False, indent=2)
    else:
        attribute.options_str = ''

    return render_template('attributes/edit.html', attribute=attribute)

@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    """Eliminar atributo"""
    attribute = ProductAttributeConfig.query.filter_by(
        id=id,
        client_id=current_user.client_id
    ).first_or_404()

    try:
        label = attribute.label
        db.session.delete(attribute)
        db.session.commit()
        flash(f'Atributo "{label}" eliminado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error al eliminar atributo: {str(e)}')
        flash(f'Error al eliminar atributo: {str(e)}', 'danger')

    return redirect(url_for('attributes.index'))
