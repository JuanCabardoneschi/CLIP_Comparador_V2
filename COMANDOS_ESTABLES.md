# COMANDOS DE DESARROLLO ESTABLES - CLIP COMPARADOR V2
# =====================================================
# Usar estos comandos exactos que siempre funcionan

# 1. VERIFICAR BASE DE DATOS (siempre funciona)
python stable_config.py

# 2. EJECUTAR SERVIDOR (comando exacto)
cd C:\Personal\CLIP_Comparador_V2\clip_admin_backend; python app.py

# 3. TESTING API (configuración estable)
# URL: http://localhost:5000/api/search
# API Key: 2495555adf3943dbafa4cad1f28a9822
# Cliente: Demo Fashion Store

# 4. ABRIR WIDGET DE PRUEBA
# Abrir widget_test.html en navegador
# O usar: start widget_test.html

# 5. VERIFICAR TABLAS (comando SQL estable)
sqlite3 clip_admin_backend/instance/clip_comparador_v2.db "SELECT name FROM sqlite_master WHERE type='table';"

# 6. CONTAR REGISTROS (queries que siempre funcionan)
# python -c "import sqlite3; conn = sqlite3.connect('./clip_admin_backend/instance/clip_comparador_v2.db'); cur = conn.cursor(); print('Productos:', cur.execute('SELECT COUNT(*) FROM products').fetchone()[0]); print('Imágenes:', cur.execute('SELECT COUNT(*) FROM images').fetchone()[0]); print('Embeddings:', cur.execute('SELECT COUNT(*) FROM images WHERE clip_embedding IS NOT NULL').fetchone()[0]); conn.close()"

# 7. RESTART SERVIDOR (secuencia estable)
# Ctrl+C para detener
# cd C:\Personal\CLIP_Comparador_V2\clip_admin_backend; python app.py

# 8. VERIFICAR URLS DE IMÁGENES (helper estable)
# python stable_config.py

# 9. CREDENTIALS QUE SIEMPRE FUNCIONAN
# Super Admin: clipadmin@sistema.com / Laurana@01
# Store Admin: admin@demo.com / admin123

# 10. PUERTOS Y ENDPOINTS ESTABLES
# Backend Admin: http://localhost:5000
# API Search: http://localhost:5000/api/search
# Widget Test: file:///C:/Personal/CLIP_Comparador_V2/widget_test.html

# NOTAS IMPORTANTES:
# - Usar PowerShell con punto y coma (;) no &&
# - Siempre cd al directorio correcto antes de ejecutar
# - stable_config.py contiene todas las operaciones estables
# - Las URLs de placeholder aseguran que las imágenes se vean
