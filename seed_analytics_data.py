#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para insertar datos de prueba directamente en search_logs
"""

import sys
import os
from pathlib import Path

# Cargar variables de entorno
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env.local'
load_dotenv(env_path)

sys.path.insert(0, 'clip_admin_backend')

from app import create_app, db
from app.models.search_log import SearchLog
from app.models.client import Client
from datetime import datetime, timedelta
import random

app = create_app()

with app.app_context():
    # Obtener cliente activo
    client = Client.query.filter_by(is_active=True).first()

    if not client:
        print("❌ No hay clientes activos")
        sys.exit(1)

    print(f"✅ Cliente encontrado: {client.name} ({client.id})")

    # Datos de prueba
    search_scenarios = [
        # Búsquedas exitosas
        {
            'search_type': 'text_nlp',
            'query_text': 'remera negra',
            'categories_detected': ['Remera', 'Camiseta'],
            'categories_matched': ['Remera'],
            'categories_missing': [],
            'terms_extracted': ['negra', 'remera'],
            'terms_matched': ['negra'],
            'terms_unmatched': [],
            'results_count': 5,
            'had_results': True,
            'response_time_ms': 250
        },
        {
            'search_type': 'text_nlp',
            'query_text': 'pantalon azul',
            'categories_detected': ['Pantalon'],
            'categories_matched': ['Pantalon'],
            'categories_missing': [],
            'terms_extracted': ['azul', 'pantalon'],
            'terms_matched': ['azul'],
            'terms_unmatched': [],
            'results_count': 3,
            'had_results': True,
            'response_time_ms': 180
        },
        # Búsqueda con categoría faltante
        {
            'search_type': 'text_nlp',
            'query_text': 'vestido floreado',
            'categories_detected': ['Vestido'],
            'categories_matched': [],
            'categories_missing': ['Vestido'],
            'terms_extracted': ['floreado', 'vestido'],
            'terms_matched': [],
            'terms_unmatched': ['floreado'],
            'results_count': 0,
            'had_results': False,
            'response_time_ms': 120
        },
        {
            'search_type': 'text_nlp',
            'query_text': 'bikini roja',
            'categories_detected': ['Bikini'],
            'categories_matched': [],
            'categories_missing': ['Bikini'],
            'terms_extracted': ['roja', 'bikini'],
            'terms_matched': [],
            'terms_unmatched': ['roja'],
            'results_count': 0,
            'had_results': False,
            'response_time_ms': 95
        },
        {
            'search_type': 'gpt4v_visual',
            'query_text': None,
            'image_url': None,
            'categories_detected': ['Campera', 'Jacket'],
            'categories_matched': ['Campera'],
            'categories_missing': [],
            'results_count': 8,
            'had_results': True,
            'response_time_ms': 1200,
            'threshold_used': 0.7
        },
        # Términos no matcheados
        {
            'search_type': 'text_nlp',
            'query_text': 'remera con bolsillo',
            'categories_detected': ['Remera'],
            'categories_matched': ['Remera'],
            'categories_missing': [],
            'terms_extracted': ['bolsillo', 'remera'],
            'terms_matched': [],
            'terms_unmatched': ['bolsillo'],
            'results_count': 2,
            'had_results': True,
            'response_time_ms': 200
        },
        {
            'search_type': 'text_nlp',
            'query_text': 'pantalon impermeable',
            'categories_detected': ['Pantalon'],
            'categories_matched': ['Pantalon'],
            'categories_missing': [],
            'terms_extracted': ['impermeable', 'pantalon'],
            'terms_matched': [],
            'terms_unmatched': ['impermeable'],
            'results_count': 1,
            'had_results': True,
            'response_time_ms': 175
        },
    ]

    print(f"\n📝 Insertando {len(search_scenarios)} registros de prueba...")

    inserted = 0
    base_time = datetime.utcnow() - timedelta(days=7)

    for i, scenario in enumerate(search_scenarios):
        try:
            # Variar el timestamp
            created_at = base_time + timedelta(days=random.randint(0, 7), hours=random.randint(0, 23))

            log = SearchLog(
                client_id=client.id,
                created_at=created_at,
                **scenario
            )
            db.session.add(log)
            inserted += 1
            print(f"  ✅ {i+1}. {scenario.get('query_text', 'Visual search')}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    try:
        db.session.commit()
        print(f"\n✅ {inserted} registros insertados correctamente")
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Error al hacer commit: {e}")
        sys.exit(1)

    # Verificar
    total = SearchLog.query.count()
    print(f"\n📊 Total registros en search_logs: {total}")

    print("\n💡 Ahora puedes ver los datos en:")
    print("   - Dashboard: http://localhost:5000/analytics/")
    print("   - Gap Detection: http://localhost:5000/analytics/gaps")
