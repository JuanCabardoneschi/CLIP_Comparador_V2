#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para generar datos de prueba en analytics
Ejecuta varias búsquedas para poblar search_logs
"""

import requests
import time

API_KEY = "test-api-key-demo-fashion-store-2024"
BASE_URL = "http://localhost:5000"

# Búsquedas de prueba con diferentes escenarios
test_searches = [
    # Búsquedas exitosas (categorías que existen)
    {"query": "remera negra", "expected": "success"},
    {"query": "pantalon azul", "expected": "success"},
    {"query": "campera roja", "expected": "success"},
    {"query": "zapatillas blancas", "expected": "success"},
    {"query": "buzo verde", "expected": "success"},

    # Búsquedas con categorías que NO existen (gap detection)
    {"query": "vestido floreado", "expected": "missing_category"},
    {"query": "bikini roja", "expected": "missing_category"},
    {"query": "sombrero de paja", "expected": "missing_category"},
    {"query": "cartera de cuero", "expected": "missing_category"},

    # Búsquedas con atributos específicos
    {"query": "remera con bolsillo", "expected": "attribute_search"},
    {"query": "pantalon de jean", "expected": "attribute_search"},
    {"query": "campera impermeable", "expected": "attribute_search"},
    {"query": "zapatillas deportivas", "expected": "attribute_search"},

    # Búsquedas ambiguas o sin resultados
    {"query": "algo azul", "expected": "ambiguous"},
    {"query": "ropa casual", "expected": "ambiguous"},
    {"query": "producto barato", "expected": "ambiguous"},
]

def test_text_search(query):
    """Ejecutar búsqueda por texto"""
    url = f"{BASE_URL}/api/search/text"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "query": query,
        "limit": 5
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        print(f"  [{response.status_code}] '{query}' → {response.json().get('total_results', 0)} resultados")
        return response.status_code == 200
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    print("="*70)
    print("🔍 GENERANDO DATOS DE PRUEBA PARA ANALYTICS")
    print("="*70)
    print(f"API Key: {API_KEY}")
    print(f"Base URL: {BASE_URL}")
    print(f"Total búsquedas: {len(test_searches)}")
    print("="*70)

    success_count = 0

    for i, search in enumerate(test_searches, 1):
        query = search['query']
        print(f"\n{i}/{len(test_searches)} - Tipo: {search['expected']}")

        if test_text_search(query):
            success_count += 1

        # Pequeña pausa entre búsquedas
        time.sleep(0.5)

    print("\n" + "="*70)
    print(f"✅ Completado: {success_count}/{len(test_searches)} búsquedas exitosas")
    print("="*70)
    print("\n💡 Ahora puedes ver los datos en:")
    print(f"   - Dashboard: {BASE_URL}/analytics/")
    print(f"   - Gap Detection: {BASE_URL}/analytics/gaps")
    print(f"   - Búsquedas: {BASE_URL}/analytics/searches")
    print("="*70)

if __name__ == "__main__":
    main()
