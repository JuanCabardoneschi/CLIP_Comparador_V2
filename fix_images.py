import sqlite3

conn = sqlite3.connect('clip_admin_backend/instance/clip_comparador_v2.db')
cursor = conn.cursor()

print("🔍 Verificando el estado actual de las imágenes...")

# Ver las primeras imágenes y su estado
cursor.execute('SELECT id, filename, is_processed, upload_status, (clip_embedding IS NOT NULL) as has_embedding FROM images LIMIT 5')
rows = cursor.fetchall()
print("\n📋 Primeras 5 imágenes:")
for row in rows:
    print(f"ID: {row[0]}, Archivo: {row[1][:30]}..., Procesada: {row[2]}, Estado: {row[3]}, Embedding: {row[4]}")

# Actualizar todas las imágenes sin embedding para que estén pendientes
print("\n🔄 Marcando imágenes sin embedding como pendientes...")
cursor.execute('UPDATE images SET is_processed = 0, upload_status = "pending" WHERE clip_embedding IS NULL')
affected = cursor.rowcount
print(f"✅ Actualizadas {affected} imágenes")

conn.commit()

# Verificar el resultado
cursor.execute('SELECT COUNT(*) FROM images WHERE is_processed = 0 AND upload_status = "pending"')
pendientes = cursor.fetchone()[0]
print(f'\n✅ Imágenes marcadas como pendientes para CLIP: {pendientes}')

cursor.execute('SELECT COUNT(*) FROM images WHERE clip_embedding IS NOT NULL')
con_embeddings = cursor.fetchone()[0]
print(f'📊 Imágenes con embeddings CLIP: {con_embeddings}')

conn.close()
print("\n🎯 Ahora puedes ir al panel admin y hacer clic en 'Procesar Imágenes Pendientes'")
