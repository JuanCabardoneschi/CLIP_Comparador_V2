import psycopg2
import re
from pathlib import Path

def normalize_data_url(b64: str) -> str:
    """Normaliza cualquier valor base64 a un data URL válido.

    - Quita espacios y saltos de línea.
    - Si ya viene con prefijo data:image/...;base64, lo estandariza y evita duplicarlo.
    - Si viene solo el payload base64, agrega 'data:image/jpeg;base64,' por defecto.
    """
    if not b64:
        return ""
    cleaned = re.sub(r"\s+", "", b64)
    m = re.match(r"^data:(image/[^;]+);base64,", cleaned, flags=re.IGNORECASE)
    if m:
        mime = m.group(1).lower()
        payload = re.sub(r"^data:(image/[^;]+);base64,", "", cleaned, flags=re.IGNORECASE)
        return f"data:{mime};base64,{payload}"
    return f"data:image/jpeg;base64,{cleaned}"

# 1) Obtener 6 productos de Eve's Store con base64 primario
conn = psycopg2.connect(
    host="ballast.proxy.rlwy.net",
    port=54363,
    database="railway",
    user="postgres",
    password="xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum",
)
cur = conn.cursor()
cur.execute(
    """
    SELECT p.name, p.price, i.base64_data
    FROM products p
    JOIN clients c ON c.id = p.client_id
    JOIN images i ON i.product_id = p.id AND i.is_primary = true
    WHERE c.name LIKE 'Eve%'
    ORDER BY p.created_at
    LIMIT 6
    """
)
rows = cur.fetchall()
cur.close()
conn.close()

if len(rows) < 6:
    raise RuntimeError(f"Se encontraron solo {len(rows)} productos de Eve's Store con imagen primaria.")

cards = []
for name, price, b64 in rows:
    # sanitizar
    name_html = (name or '').strip()
    price_val = float(price or 0)
    src_val = normalize_data_url(b64 or "")
    cards.append(f"""
            <div class=\"product-card\">\r
                <div class=\"product-image\">\r
                    <img src=\"{src_val}\" alt=\"{name_html}\" style=\"width: 100%; height: 100%; object-fit: cover;\">\r
                </div>\r
                <div class=\"product-info\">\r
                    <h3 class=\"product-name\">{name_html}</h3>\r
                    <p class=\"product-price\">${price_val:.2f}</p>\r
                </div>\r
            </div>\r
    """)

new_grid_inner = "\n".join(cards)

html_path = Path("clip_admin_backend/app/static/eve-store.html")
h = html_path.read_text(encoding="utf-8")

# 2) Reemplazar el contenido interno del contenedor .product-grid conservando el contenedor
pattern = re.compile(r"(<div class=\"product-grid\">)([\s\S]*?)(</div>\s*</section>)")
match = pattern.search(h)
if not match:
    raise RuntimeError("No se encontró el bloque .product-grid en eve-store.html")

before = match.group(1)
after = match.group(3)
new_html = h[:match.start()] + before + "\n" + new_grid_inner + "\n" + after + h[match.end():]

html_path.write_text(new_html, encoding="utf-8")
print("✅ Actualizado eve-store.html con 6 imágenes base64 de Eve's Store")
