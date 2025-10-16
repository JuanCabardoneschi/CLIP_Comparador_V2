#!/usr/bin/env python3
"""
Script para aplicar migración de centroides a Railway PostgreSQL
Sistema: CLIP Comparador V2
Fecha: 2025-10-16
"""

import os
import sys
import psycopg2
from datetime import datetime

def get_railway_db_connection():
    """Obtener conexión a PostgreSQL de Railway"""
    try:
        # Railway PostgreSQL connection
        DATABASE_URL = os.environ.get('DATABASE_URL')
        if not DATABASE_URL:
            print("❌ ERROR: DATABASE_URL no encontrada en variables de entorno")
            print("   Configurar en Railway: postgres://user:pass@host:port/db")
            return None
        
        print(f"🔗 Conectando a Railway PostgreSQL...")
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Conexión establecida exitosamente")
        return conn
        
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        return None

def apply_migration(conn):
    """Aplicar migración SQL de centroides"""
    try:
        cursor = conn.cursor()
        
        # Leer archivo de migración
        migration_file = os.path.join(os.path.dirname(__file__), 'migration_add_centroids.sql')
        
        if not os.path.exists(migration_file):
            print(f"❌ Error: Archivo de migración no encontrado: {migration_file}")
            return False
        
        print(f"📄 Leyendo migración: {migration_file}")
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        print("🔄 Aplicando migración...")
        
        # Ejecutar migración por bloques (split por comentarios principales)
        sql_blocks = migration_sql.split('-- ')
        
        for i, block in enumerate(sql_blocks):
            if block.strip():
                try:
                    block_sql = block.strip()
                    if block_sql and not block_sql.startswith('Migración:') and not block_sql.startswith('Fecha:') and not block_sql.startswith('Sistema:'):
                        print(f"   Ejecutando bloque {i+1}...")
                        cursor.execute(block_sql)
                        conn.commit()
                except Exception as e:
                    print(f"⚠️  Advertencia en bloque {i+1}: {e}")
                    conn.rollback()
                    continue
        
        # Verificar que las columnas se crearon
        print("🔍 Verificando migración...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'categories' 
            AND column_name IN ('centroid_embedding', 'centroid_updated_at', 'centroid_image_count')
            ORDER BY column_name;
        """)
        
        columns = cursor.fetchall()
        if len(columns) >= 3:
            print("✅ Migración aplicada exitosamente:")
            for col_name, data_type, is_nullable in columns:
                print(f"   - {col_name}: {data_type} ({'NULL' if is_nullable == 'YES' else 'NOT NULL'})")
        else:
            print(f"⚠️  Solo se crearon {len(columns)} de 3 columnas esperadas")
            
        # Verificar vista de estadísticas
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.views 
            WHERE table_name = 'category_centroid_stats';
        """)
        view_count = cursor.fetchone()[0]
        if view_count > 0:
            print("✅ Vista category_centroid_stats creada")
        else:
            print("⚠️  Vista category_centroid_stats no se creó")
            
        cursor.close()
        return True
        
    except Exception as e:
        print(f"❌ Error aplicando migración: {e}")
        conn.rollback()
        return False

def verify_migration(conn):
    """Verificar estado post-migración"""
    try:
        cursor = conn.cursor()
        
        print("\n📊 Verificando estado de categorías...")
        cursor.execute("""
            SELECT 
                c.name,
                c.centroid_embedding IS NOT NULL as has_centroid,
                COUNT(i.id) as total_images,
                COUNT(CASE WHEN i.clip_embedding IS NOT NULL THEN 1 END) as with_embeddings
            FROM categories c
            LEFT JOIN products p ON c.id = p.category_id
            LEFT JOIN images i ON p.id = i.product_id
            WHERE c.is_active = true
            GROUP BY c.id, c.name, c.centroid_embedding
            ORDER BY c.name;
        """)
        
        categories = cursor.fetchall()
        print(f"\n📋 Estado de {len(categories)} categorías activas:")
        for name, has_centroid, total_imgs, with_embeddings in categories:
            status = "✅ CON CENTROIDE" if has_centroid else "⭕ SIN CENTROIDE"
            print(f"   {name}: {status} | {with_embeddings}/{total_imgs} imágenes con embeddings")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"❌ Error verificando migración: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 CLIP Comparador V2 - Migración de Centroides")
    print("=" * 50)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Conectar a BD
    conn = get_railway_db_connection()
    if not conn:
        sys.exit(1)
    
    try:
        # 2. Aplicar migración
        if apply_migration(conn):
            print("\n✅ Migración aplicada exitosamente")
            
            # 3. Verificar estado
            verify_migration(conn)
            
            print("\n🎉 MIGRACIÓN COMPLETADA")
            print("📝 Próximos pasos:")
            print("   1. Actualizar código Python para usar BD")
            print("   2. Recalcular centroides existentes")
            print("   3. Deployment a Railway")
            
        else:
            print("\n❌ Error aplicando migración")
            sys.exit(1)
            
    finally:
        conn.close()
        print("\n🔐 Conexión a BD cerrada")

if __name__ == "__main__":
    main()