#!/usr/bin/env python3
"""
Script para recalcular centroides existentes y migrar a BD
Sistema: CLIP Comparador V2 - Post Migración
"""

import os
import sys
import time
from datetime import datetime

# Configurar path para importar desde el backend
backend_path = os.path.join(os.path.dirname(__file__), '..', '..', 'clip_admin_backend')
sys.path.insert(0, backend_path)

def setup_flask_app():
    """Configurar app Flask para acceso a modelos"""
    try:
        import os
        os.chdir(backend_path)
        
        from app import app, db
        from app.models.category import Category
        from app.models.client import Client
        from app.models.product import Product
        from app.models.image import Image
        
        return app, db, Category, Client, Product, Image
        
    except Exception as e:
        print(f"❌ Error configurando Flask app: {e}")
        return None, None, None, None, None, None

def recalculate_client_centroids(app, db, Category, client_id=None):
    """Recalcular centroides para un cliente específico o todos"""
    
    with app.app_context():
        try:
            if client_id:
                print(f"🎯 Recalculando centroides para cliente: {client_id}")
                stats = Category.recalculate_all_centroids(client_id=client_id, force=True)
            else:
                print("🎯 Recalculando centroides para TODOS los clientes")
                stats = Category.recalculate_all_centroids(force=True)
            
            return stats
            
        except Exception as e:
            print(f"❌ Error recalculando centroides: {e}")
            import traceback
            traceback.print_exc()
            return None

def verify_centroids_status(app, db, Category, Client):
    """Verificar estado de centroides después de migración"""
    
    with app.app_context():
        try:
            print("\n📊 ESTADO DE CENTROIDES POST-MIGRACIÓN")
            print("=" * 50)
            
            # Estadísticas generales
            total_categories = Category.query.filter_by(is_active=True).count()
            with_centroids = Category.query.filter(
                Category.is_active == True,
                Category.centroid_embedding.isnot(None)
            ).count()
            
            print(f"📋 Total categorías activas: {total_categories}")
            print(f"✅ Con centroides: {with_centroids}")
            print(f"❌ Sin centroides: {total_categories - with_centroids}")
            print(f"📈 Cobertura: {(with_centroids/total_categories*100):.1f}%")
            
            # Por cliente
            print(f"\n📊 DETALLE POR CLIENTE:")
            clients = Client.query.all()
            
            for client in clients:
                client_categories = Category.query.filter_by(
                    client_id=client.id, 
                    is_active=True
                ).all()
                
                if not client_categories:
                    continue
                
                with_centroids = sum(1 for cat in client_categories if cat.centroid_embedding)
                total = len(client_categories)
                
                print(f"\n🏢 {client.name} ({client.id[:8]}...):")
                print(f"   📋 Categorías: {total}")
                print(f"   ✅ Con centroides: {with_centroids}")
                print(f"   📈 Cobertura: {(with_centroids/total*100):.1f}%")
                
                # Detalle por categoría
                for category in client_categories:
                    status = "✅" if category.centroid_embedding else "❌"
                    count = f"({category.centroid_image_count} imgs)" if category.centroid_image_count else "(0 imgs)"
                    updated = category.centroid_updated_at.strftime('%Y-%m-%d %H:%M') if category.centroid_updated_at else "Nunca"
                    print(f"      {status} {category.name}: {count} - {updated}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error verificando estado: {e}")
            return False

def test_detection_performance(app, db, Category, client_id):
    """Probar performance de detección con centroides BD"""
    
    with app.app_context():
        try:
            print(f"\n🚀 PRUEBA DE PERFORMANCE - Cliente: {client_id}")
            print("=" * 50)
            
            # Simular detección con centroides BD
            categories = Category.query.filter_by(
                client_id=client_id,
                is_active=True
            ).all()
            
            if not categories:
                print(f"❌ No hay categorías para cliente {client_id}")
                return False
            
            total_start = time.time()
            centroids_loaded = 0
            centroids_calculated = 0
            
            print(f"📋 Probando {len(categories)} categorías...")
            
            for category in categories:
                start_time = time.time()
                
                # Probar get_centroid_embedding
                centroid = category.get_centroid_embedding(auto_calculate=True)
                
                load_time = time.time() - start_time
                
                if centroid is not None:
                    if category.centroid_embedding:
                        centroids_loaded += 1
                        print(f"⚡ {category.name}: {load_time:.3f}s (BD)")
                    else:
                        centroids_calculated += 1
                        print(f"🔄 {category.name}: {load_time:.3f}s (CALC)")
                else:
                    print(f"❌ {category.name}: Sin centroide")
            
            total_time = time.time() - total_start
            
            print(f"\n📊 RESULTADO PERFORMANCE:")
            print(f"   ⏱️  Tiempo total: {total_time:.2f}s")
            print(f"   ⚡ Desde BD: {centroids_loaded} categorías")
            print(f"   🔄 Calculados: {centroids_calculated} categorías")
            print(f"   📈 Promedio por categoría: {(total_time/len(categories)):.3f}s")
            
            # Performance esperado
            if centroids_loaded > 0:
                bd_time = total_time / max(1, centroids_loaded + centroids_calculated) * centroids_loaded
                print(f"   🎯 Performance esperado con BD: ~{bd_time:.2f}s")
            
            return True
            
        except Exception as e:
            print(f"❌ Error probando performance: {e}")
            return False

def main():
    """Función principal del script"""
    print("🚀 CLIP Comparador V2 - Recálculo de Centroides Post-Migración")
    print("=" * 60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Configurar Flask app
    print("\n🔧 Configurando Flask app...")
    app, db, Category, Client, Product, Image = setup_flask_app()
    
    if not app:
        print("❌ No se pudo configurar Flask app")
        sys.exit(1)
    
    print("✅ Flask app configurada")
    
    # 2. Verificar estado actual
    print("\n🔍 Verificando estado actual...")
    verify_centroids_status(app, db, Category, Client)
    
    # 3. Recalcular centroides
    print("\n🔄 Iniciando recálculo de centroides...")
    start_time = time.time()
    
    stats = recalculate_client_centroids(app, db, Category)
    
    if stats:
        recalc_time = time.time() - start_time
        print(f"\n✅ Recálculo completado en {recalc_time:.2f}s")
        print(f"📊 Estadísticas:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
    else:
        print("\n❌ Error en recálculo")
        sys.exit(1)
    
    # 4. Verificar estado final
    print("\n🔍 Verificando estado final...")
    verify_centroids_status(app, db, Category, Client)
    
    # 5. Probar performance (cliente ejemplo)
    with app.app_context():
        client = Client.query.first()
        if client:
            test_detection_performance(app, db, Category, client.id)
    
    print("\n🎉 PROCESO COMPLETADO")
    print("📝 Próximos pasos:")
    print("   1. Deployment del código actualizado a Railway")
    print("   2. Probar detección con widget")
    print("   3. Verificar performance de 1-2 segundos")

if __name__ == "__main__":
    main()