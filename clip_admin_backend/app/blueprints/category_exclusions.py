"""
Blueprint de gestión de exclusiones de pares de categorías (admin)
Ruta base: /categories/exclusions
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.category_pair_exclusion import CategoryPairExclusion
from app.models.category import Category
from app.models.client import Client
from sqlalchemy import desc
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('category_exclusions', __name__, url_prefix='/categories/exclusions')


@bp.route('/', methods=['GET'])
@login_required
def index():
    """Lista todas las reglas de exclusión de pares para el cliente actual."""
    client_id = current_user.client_id

    exclusions = CategoryPairExclusion.query.filter_by(
        client_id=client_id
    ).order_by(desc(CategoryPairExclusion.created_at)).all()

    return render_template(
        'category_exclusions/index.html',
        exclusions=exclusions
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Crea una nueva regla de exclusión de par."""
    if request.method == 'GET':
        # Obtener categorías del cliente
        categories = Category.query.filter_by(
            client_id=current_user.client_id,
            is_active=True
        ).order_by(Category.name).all()

        return render_template(
            'category_exclusions/create.html',
            categories=categories
        )

    # POST
    try:
        primary_cat_id = request.form.get('primary_category_id')
        secondary_cat_id = request.form.get('secondary_category_id')
        exclusion_rule = request.form.get('exclusion_rule', 'torso_evidence')

        # Parsear params JSON
        params = {}
        if exclusion_rule == 'torso_evidence':
            params = {
                'override_gap_max': float(request.form.get('override_gap_max', 0.10)),
                'torso_evidence_min': float(request.form.get('torso_evidence_min', 0.24)),
                'torso_advantage_min': float(request.form.get('torso_advantage_min', 0.06)),
                'suppression_evidence_threshold': float(request.form.get('suppression_evidence_threshold', 0.22)),
                'tie_margin': float(request.form.get('tie_margin', 0.02))
            }

        exclusion = CategoryPairExclusion(
            client_id=current_user.client_id,
            primary_category_id=primary_cat_id,
            secondary_category_id=secondary_cat_id,
            exclusion_rule=exclusion_rule,
            params=params,
            is_active=True
        )

        db.session.add(exclusion)
        db.session.commit()

        flash('Regla de exclusión creada exitosamente', 'success')
        return redirect(url_for('category_exclusions.index'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creando exclusión: {e}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('category_exclusions.create'))


@bp.route('/<exclusion_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(exclusion_id):
    """Edita una regla de exclusión existente."""
    exclusion = CategoryPairExclusion.query.filter_by(
        id=exclusion_id,
        client_id=current_user.client_id
    ).first_or_404()

    if request.method == 'GET':
        categories = Category.query.filter_by(
            client_id=current_user.client_id,
            is_active=True
        ).order_by(Category.name).all()

        return render_template(
            'category_exclusions/edit.html',
            exclusion=exclusion,
            categories=categories
        )

    # POST
    try:
        # Actualizar params
        if exclusion.exclusion_rule == 'torso_evidence':
            exclusion.params = {
                'override_gap_max': float(request.form.get('override_gap_max', 0.10)),
                'torso_evidence_min': float(request.form.get('torso_evidence_min', 0.24)),
                'torso_advantage_min': float(request.form.get('torso_advantage_min', 0.06)),
                'suppression_evidence_threshold': float(request.form.get('suppression_evidence_threshold', 0.22)),
                'tie_margin': float(request.form.get('tie_margin', 0.02))
            }

        exclusion.is_active = request.form.get('is_active') == 'on'

        db.session.commit()
        flash('Regla actualizada exitosamente', 'success')
        return redirect(url_for('category_exclusions.index'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error actualizando exclusión: {e}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('category_exclusions.edit', exclusion_id=exclusion_id))


@bp.route('/<exclusion_id>/toggle', methods=['POST'])
@login_required
def toggle(exclusion_id):
    """Activa/desactiva una regla de exclusión."""
    try:
        exclusion = CategoryPairExclusion.query.filter_by(
            id=exclusion_id,
            client_id=current_user.client_id
        ).first_or_404()

        exclusion.is_active = not exclusion.is_active
        db.session.commit()

        return jsonify({
            'success': True,
            'is_active': exclusion.is_active
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling exclusión: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/<exclusion_id>/delete', methods=['POST'])
@login_required
def delete(exclusion_id):
    """Elimina una regla de exclusión."""
    try:
        exclusion = CategoryPairExclusion.query.filter_by(
            id=exclusion_id,
            client_id=current_user.client_id
        ).first_or_404()

        db.session.delete(exclusion)
        db.session.commit()

        flash('Regla eliminada exitosamente', 'success')
        return redirect(url_for('category_exclusions.index'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error eliminando exclusión: {e}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('category_exclusions.index'))


@bp.route('/api/for-client/<client_id>', methods=['GET'])
def api_get_exclusions(client_id):
    """API: Obtiene reglas activas de exclusión para un cliente (uso interno)."""
    try:
        exclusions = CategoryPairExclusion.query.filter_by(
            client_id=client_id,
            is_active=True
        ).all()

        return jsonify({
            'success': True,
            'exclusions': [e.to_dict() for e in exclusions]
        })

    except Exception as e:
        logger.error(f"Error obteniendo exclusiones: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
