"""
Script temporal para migrar todos los print() en search_text.py a log_verbose
Ejecutar una vez y luego eliminar
"""
import re

file_path = "c:\\Personal\\CLIP_Comparador_V2\\clip_admin_backend\\app\\blueprints\\search_text.py"

# Leer el archivo
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazar todos los print() que son de debugging por log_verbose
# Patrón: print(f"..." o print("..."
replacements = [
    # Prints que son claramente verbose/debug
    (r'print\(f"🔗 ', r'log_verbose(LogCategory.NLP, f"🔗 '),
    (r'print\(f"     ', r'log_verbose(LogCategory.NLP, f"     '),
    (r'print\(f"  ✅ ', r'log_verbose(LogCategory.NLP, f"  ✅ '),
    (r'print\(f"    ⛔ ', r'log_verbose(LogCategory.NLP, f"    ⛔ '),
    (r'print\(f"\\n⚠️ \[FALLBACK\]', r'log_verbose(LogCategory.NLP, f"[FALLBACK]'),
    (r'print\(f"\\n❌ \[EXTRACTOR\]', r'log_verbose(LogCategory.NLP, f"[EXTRACTOR]'),
    (r'print\(f"\{\'=\'\*60\}', r'log_verbose(LogCategory.NLP, f"{"="*60}'),
    (r'print\(f"\\n✅ \[RESULTADO\]', r'log_verbose(LogCategory.NLP, f"[RESULTADO]'),
    (r'print\(f"📦 \[CATEGORÍA\]', r'log_verbose(LogCategory.NLP, f"📦 [CATEGORÍA]'),
    (r'print\(f"🏷️  \[MODIFICADORES\]', r'log_verbose(LogCategory.NLP, f"🏷️  [MODIFICADORES]'),
    (r'print\(f"✅ \[SALIDA\]', r'log_verbose(LogCategory.NLP, f"✅ [SALIDA]'),
    (r'print\(f"⚠️ Error construyendo', r'log_error(f"Error construyendo'),
    (r'print\(f"⚠️ \[Módulo Custom\] Error', r'log_error(f"[Módulo Custom] Error'),
    (r'print\(f"✅ \[Módulo Custom\]', r'log_verbose(LogCategory.SEARCH, f"[Módulo Custom]'),
    (r'print\(f"⚠️ \[Genérico\] Error', r'log_error(f"[Genérico] Error'),
    (r'print\(f"🔍 Token', r'log_verbose(LogCategory.NLP, f"🔍 Token'),
    (r'print\(f"📝 \[Genérico\]', r'log_verbose(LogCategory.NLP, f"[Genérico]'),
    (r'print\(f"✅ \[Módulo Custom\] Filtro', r'log_verbose(LogCategory.SEARCH, f"[Módulo Custom] Filtro'),
    (r'print\(f"📝 \[Módulo Custom\]', r'log_verbose(LogCategory.SEARCH, f"[Módulo Custom]'),
    (r'print\(f"🔒 \[Genérico\]', r'log_verbose(LogCategory.SEARCH, f"[Genérico]'),
    (r'print\(f"⚡ STAGE 1:', r'log_search(f"STAGE 1:'),
    (r'print\(f"🎯 STAGE 2:', r'log_search(f"STAGE 2:'),
    (r'print\(f"   \{i\}\.', r'log_verbose(LogCategory.SEARCH, f"   {i}.'),
    (r'print\(f"\\n🎯 \[TEXT_SEARCH\]', r'log_search(f"[TEXT_SEARCH]'),
    (r'print\(f"📝 \[TEXT_SEARCH\]', r'log_verbose(LogCategory.SEARCH, f"[TEXT_SEARCH]'),
    (r'print\(f"🧹 \[TEXT_SEARCH\]', r'log_verbose(LogCategory.NLP, f"[TEXT_SEARCH]'),
    (r'print\(f"   📦 Categoría', r'log_verbose(LogCategory.NLP, f"   📦 Categoría'),
    (r'print\(f"   🏷️  Modificadores', r'log_verbose(LogCategory.NLP, f"   🏷️  Modificadores'),
    (r'print\(f"\\n\{\'=\'\*60\}"\)', r'log_verbose(LogCategory.SEARCH, "="*60)'),
    (r'print\(f"🔍 DETECCIÓN', r'log_verbose(LogCategory.CATEGORY_DETECTION, f"🔍 DETECCIÓN'),
    (r'print\(f"Total categorías', r'log_verbose(LogCategory.CATEGORY_DETECTION, f"Total categorías'),
    (r'print\(f"✅ Match encontrado', r'log_verbose(LogCategory.CATEGORY_DETECTION, f"✅ Match encontrado'),
    (r'print\(f"📊 RESUMEN', r'log_verbose(LogCategory.CATEGORY_DETECTION, f"📊 RESUMEN'),
    (r'print\(f"   Categoría en query', r'log_verbose(LogCategory.CATEGORY_DETECTION, f"   Categoría en query'),
    (r'print\(f"   Categorías coincidentes', r'log_verbose(LogCategory.CATEGORY_DETECTION, f"   Categorías coincidentes'),
    (r'print\(f"      - \{mc', r'log_verbose(LogCategory.CATEGORY_DETECTION, f"      - {mc'),
    (r'print\(f"      ⚠️ No se encontraron', r'log_verbose(LogCategory.CATEGORY_DETECTION, f"      ⚠️ No se encontraron'),
    (r'print\(f"🏷️  ANÁLISIS', r'log_verbose(LogCategory.NLP, f"🏷️  ANÁLISIS'),
]

for old_pattern, new_pattern in replacements:
    content = re.sub(old_pattern, new_pattern, content)

# Guardar
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Migración completada")
