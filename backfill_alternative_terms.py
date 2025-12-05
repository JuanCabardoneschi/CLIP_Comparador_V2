#!/usr/bin/env python3
"""
Script para backfill de alternative_terms en categorías existentes.
Aplica auto-generación a todas las categorías con alternative_terms=NULL.
"""

import sys
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('.env.local')

# Agregar path del backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from app import create_app, db
from app.models.category import Category
from app.services.alternative_terms_generator import generate_alternative_terms
from sqlalchemy import text

print("=" * 80)
print("🔄 BACKFILL: Generando alternative_terms para categorías existentes")
print("=" * 80)

app = create_app()

with app.app_context():
    print("\n📊 Consultando categorías sin alternative_terms...")
    
    # Buscar categorías con alternative_terms NULL o vacío
    categories = Category.query.filter(
        db.or_(
            Category.alternative_terms.is_(None),
            Category.alternative_terms == ''
        )
    ).all()
    
    print(f"✅ Encontradas {len(categories)} categorías sin alternative_terms\n")
    
    if not categories:
        print("✅ Todas las categorías ya tienen alternative_terms configurados")
        sys.exit(0)
    
    # Mostrar preview
    print("📋 Vista previa de categorías a procesar:")
    for i, cat in enumerate(categories[:10], 1):
        print(f"  {i:2d}. [{cat.client.name}] {cat.name}")
    
    if len(categories) > 10:
        print(f"  ... y {len(categories) - 10} más")
    
    print("\n" + "=" * 80)
    response = input("¿Continuar con la generación? (s/n): ").strip().lower()
    
    if response != 's':
        print("❌ Operación cancelada")
        sys.exit(0)
    
    print("\n" + "=" * 80)
    print("🚀 Iniciando generación...")
    print("=" * 80 + "\n")
    
    success_count = 0
    error_count = 0
    empty_count = 0
    
    for i, category in enumerate(categories, 1):
        try:
            print(f"[{i}/{len(categories)}] Procesando: {category.name} (ID: {category.id})")
            
            # Generar alternative_terms
            alternative_terms = generate_alternative_terms(category.name)
            
            if alternative_terms:
                category.alternative_terms = alternative_terms
                db.session.commit()
                print(f"  ✅ Generado: {alternative_terms}")
                success_count += 1
            else:
                print(f"  ⚠️  Sin términos generados (similitud baja)")
                empty_count += 1
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            error_count += 1
            db.session.rollback()
    
    print("\n" + "=" * 80)
    print("📊 RESUMEN DE BACKFILL")
    print("=" * 80)
    print(f"✅ Éxitos:     {success_count}")
    print(f"⚠️  Vacíos:     {empty_count}")
    print(f"❌ Errores:    {error_count}")
    print(f"📊 Total:      {len(categories)}")
    print("=" * 80)
    
    if success_count > 0:
        print("\n🎉 Backfill completado exitosamente")
        
        # Mostrar algunos ejemplos
        print("\n📋 Ejemplos de alternative_terms generados:")
        updated_cats = Category.query.filter(
            Category.alternative_terms.isnot(None),
            Category.alternative_terms != ''
        ).limit(5).all()
        
        for cat in updated_cats:
            print(f"\n  📂 {cat.name}")
            print(f"     → {cat.alternative_terms}")
    
    print("\n✅ Script completado")
