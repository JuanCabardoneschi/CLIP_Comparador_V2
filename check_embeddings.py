import sqlite3

# Conectar a la base de datos
conn = sqlite3.connect('clip_admin_backend/instance/clip_comparador_v2.db')
cursor = conn.cursor()

print("=== ESTADO ACTUAL DE EMBEDDINGS ===")

# Verificar si realmente se procesaron embeddings
cursor.execute("SELECT COUNT(*) FROM images WHERE is_processed = 1")
processed_count = cursor.fetchone()[0]
print(f"Imágenes con is_processed=1: {processed_count}")

cursor.execute("SELECT COUNT(*) FROM images WHERE is_processed = 0")
pending_count = cursor.fetchone()[0]
print(f"Imágenes con is_processed=0: {pending_count}")

cursor.execute("SELECT COUNT(*) FROM images WHERE clip_embedding IS NOT NULL AND clip_embedding != ''")
with_embeddings = cursor.fetchone()[0]
print(f"Imágenes con clip_embedding: {with_embeddings}")

if with_embeddings > 0:
    print("\n=== MUESTRA DE EMBEDDINGS ===")
    cursor.execute("SELECT filename, length(clip_embedding), clip_embedding FROM images WHERE clip_embedding IS NOT NULL AND clip_embedding != '' LIMIT 5")
    embeddings_sample = cursor.fetchall()

    for filename, embed_length, embedding in embeddings_sample:
        # Mostrar solo primeros caracteres del embedding
        embed_preview = embedding[:50] + "..." if len(embedding) > 50 else embedding
        print(f"- {filename}")
        print(f"  Longitud embedding: {embed_length} caracteres")
        print(f"  Contenido: {embed_preview}")
        print()

print(f"\n=== RESUMEN ===")
print(f"Total imágenes: {processed_count + pending_count}")
print(f"Procesadas: {processed_count}")
print(f"Pendientes: {pending_count}")
print(f"Con embeddings: {with_embeddings}")

if processed_count > 0 and with_embeddings == 0:
    print("⚠️  ADVERTENCIA: Hay imágenes marcadas como procesadas pero sin embeddings!")
elif processed_count == 0:
    print("✅ CORRECTO: No se han procesado embeddings aún")
elif processed_count == with_embeddings:
    print("✅ CORRECTO: Todas las imágenes procesadas tienen embeddings")

conn.close()
