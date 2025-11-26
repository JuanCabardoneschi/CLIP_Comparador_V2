"""
Script para arreglar todos los f-strings mal formados en search_text.py
"""

import re

FILE_PATH = r"c:\Personal\CLIP_Comparador_V2\clip_admin_backend\app\blueprints\search_text.py"

with open(FILE_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazar todos los f-strings que contienen {"="*60}
# con strings normales concatenados
content = re.sub(
    r'log_verbose\(LogCategory\.NLP, f\"\{\"=\"\*60\}\"\)',
    'log_verbose(LogCategory.NLP, "="*60)',
    content
)

# También buscar variantes con \n
content = re.sub(
    r'log_verbose\(LogCategory\.NLP, f\"\{\"=\"\*60\}\\n\"\)',
    'log_verbose(LogCategory.NLP, "="*60 + "\\n")',
    content
)

with open(FILE_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Arreglados f-strings en search_text.py")
