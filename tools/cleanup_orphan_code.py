"""
Elimina el código basura entre /* showError removed */ y </script>
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'demo-store.html'
BAK = ROOT / 'demo-store.cleanup_orphan.bak.html'

if not HTML.exists():
    raise SystemExit(f"No se encuentra {HTML}")

content = HTML.read_text(encoding='utf-8', errors='ignore')
BAK.write_text(content, encoding='utf-8')

print("Eliminando código huérfano...")

# Buscar el patrón: /* showError removed */ hasta el siguiente </script>
# y reemplazarlo con solo un salto de línea y el </script>

import re

# Patrón: desde /* showError removed */ hasta </script>
pattern = r'/\*\s*showError removed\s*\*/.*?(?=</script>)'

def clean_orphan(match):
    return '\n        '

content = re.sub(pattern, clean_orphan, content, flags=re.DOTALL)

HTML.write_text(content, encoding='utf-8')
print(f"✅ Código huérfano eliminado. Backup: {BAK}")
print("   Recarga con Ctrl+F5")
