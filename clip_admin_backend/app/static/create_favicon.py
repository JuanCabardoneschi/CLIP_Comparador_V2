import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Crear imagen de 32x32
img = Image.new('RGB', (32, 32), color='#1e40af')
d = ImageDraw.Draw(img)

# Dibujar círculo
d.ellipse([4, 4, 28, 28], fill='#3b82f6', outline='white', width=2)

# Intentar agregar texto (sin fuente específica)
try:
    d.text((10, 8), 'C', fill='white')
except:
    pass

# Guardar como ICO
img.save('favicon.ico', format='ICO', sizes=[(32, 32), (16, 16)])
print("Favicon created successfully!")
