content = open('clip_admin_backend/app/blueprints/api.py', encoding='utf-8').read()

content = content.replace(
    '"details": "No pudimos identificar categorías comercializadas en la imagen.",',
    '"details": "No se identificaron categorías aplicables en la imagen proporcionada.",'
)

content = content.replace(
    '"details": f"La imagen no pudo identificarse dentro de nuestras categorías disponibles (confianza máxima: {category_confidence:.1%}). Por favor, intenta con una imagen de un producto de nuestro catálogo.",',
    '"details": f"No se identificaron categorías aplicables (confianza máxima: {category_confidence:.1%}). Intenta con una imagen de productos del catálogo.",'
)

open('clip_admin_backend/app/blueprints/api.py', 'w', encoding='utf-8').write(content)
print('✅ Details actualizados')
