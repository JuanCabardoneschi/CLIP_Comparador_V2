import sqlite3

conn = sqlite3.connect('clip_admin_backend/instance/clip_comparador_v2.db')
cursor = conn.cursor()

# Verificar imágenes pendientes
cursor.execute('SELECT COUNT(*) FROM images WHERE is_processed = 0 AND upload_status = "pending"')
pendientes = cursor.fetchone()[0]
print(f'✅ Imágenes marcadas como pendientes para CLIP: {pendientes}')

# Verificar imágenes con embeddings
cursor.execute('SELECT COUNT(*) FROM images WHERE clip_embedding IS NOT NULL')
con_embeddings = cursor.fetchone()[0]
print(f'📊 Imágenes con embeddings CLIP: {con_embeddings}')

# Total de imágenes
cursor.execute('SELECT COUNT(*) FROM images')
total = cursor.fetchone()[0]
print(f'📸 Total de imágenes: {total}')

# Estado actual
print(f'\n🔄 Pendientes de procesar: {pendientes}')
print(f'✅ Ya procesadas: {con_embeddings}')
print(f'🔍 Porcentaje completado: {(con_embeddings/total)*100:.1f}%')

conn.close()
