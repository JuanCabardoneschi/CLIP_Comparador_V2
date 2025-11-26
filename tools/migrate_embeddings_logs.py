"""
Script de migración para convertir logs de embeddings.py al nuevo sistema
Convierte print() y clip_logger.* al sistema centralizado de logs
"""

import re

FILE_PATH = r"c:\Personal\CLIP_Comparador_V2\clip_admin_backend\app\blueprints\embeddings.py"

def migrate_embeddings_logs():
    print("📝 Iniciando migración de embeddings.py...")

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 1. Actualizar imports (eliminar logger local y agregar logging_config)
    # Eliminar el logger local de clip_model
    content = re.sub(
        r'import logging\n# Configuración explícita del logger.*?clip_logger\.addHandler\(handler\)\n',
        '',
        content,
        flags=re.DOTALL
    )

    # Agregar import del nuevo sistema DESPUÉS de las importaciones de Flask
    if 'from app.utils.logging_config import' not in content:
        # Buscar después de los imports de app.*
        content = re.sub(
            r'(from app\.models\.category import Category)',
            r'\1\nfrom app.utils.logging_config import (\n    log_error, log_embedding, log_verbose, log_system,\n    LogCategory\n)',
            content
        )

    # 2. Migrar prints de emojis del sistema de carga/descarga de modelo
    # Estos son logs del sistema CLIP, categoría EMBEDDING
    emoji_patterns = {
        r'print\(f"🧹 CLIP descargado por inactividad tras arranque \(sin uso, timeout \{idle_timeout\}s\)"\)':
            'log_system(f"CLIP descargado por inactividad tras arranque (sin uso, timeout {idle_timeout}s)")',

        r'print\(f"🧹 CLIP descargado por inactividad \(idle \{int\(idle_for\)\}s ≥ \{idle_timeout\}s\) \+ GC ejecutado"\)':
            'log_system(f"CLIP descargado por inactividad (idle {int(idle_for)}s >= {idle_timeout}s) + GC ejecutado")',

        r'print\(f"\[CLIP\] Model NOT unloaded: inactivity \{int\(idle_for\)\}s < \{idle_timeout\}s threshold\."\)':
            'log_verbose(LogCategory.EMBEDDING, f"[CLIP] Model NOT unloaded: inactivity {int(idle_for)}s < {idle_timeout}s threshold.")',

        r'print\(f"⚠️ Modelo cambió de \{_clip_current_model_name\} a \{model_name\}\. Recargando\.\.\."\)':
            'log_system(f"Modelo cambio de {_clip_current_model_name} a {model_name}. Recargando...")',

        r'print\(f"🔄 Cargando modelo CLIP \{model_name\} \(\{model_id\}\)\.\.\."\)':
            'log_embedding(f"Cargando modelo CLIP {model_name} ({model_id})...")',

        r'print\("🔥 GPU disponible, usando CUDA"\)':
            'log_system("GPU disponible, usando CUDA")',

        r'print\("💻 Usando CPU para CLIP"\)':
            'log_system("Usando CPU para CLIP")',

        r'print\(f"✅ Modelo CLIP \{model_name\} cargado exitosamente"\)':
            'log_embedding(f"Modelo CLIP {model_name} cargado exitosamente")',

        r'print\(f"❌ Error cargando CLIP: \{e\}"\)':
            'log_error(f"Error cargando CLIP: {e}")',
    }

    for pattern, replacement in emoji_patterns.items():
        content = re.sub(pattern, replacement, content)

    # 3. Migrar prints de embeddings con emojis
    embedding_patterns = {
        r'print\(f"⚠️ Error aplicando recorte manual: \{ce\}"\)':
            'log_error(f"Error aplicando recorte manual: {ce}")',

        r'print\(f"✅ Embedding optimizado generado: \{len\(embedding\)\} dimensiones"\)':
            'log_embedding(f"Embedding optimizado generado: {len(embedding)} dimensiones")',

        r'print\(f"📊 Métodos usados: \{metadata\.get\(\'optimization_method\'\)\}"\)':
            'log_verbose(LogCategory.EMBEDDING, f"Metodos usados: {metadata.get(\'optimization_method\')}")',

        r'print\(f"✅ Embedding simple generado: \{len\(embedding\)\} dimensiones"\)':
            'log_embedding(f"Embedding simple generado: {len(embedding)} dimensiones")',

        r'print\(f"❌ Error generando embedding: \{e\}"\)':
            'log_error(f"Error generando embedding: {e}")',
    }

    for pattern, replacement in embedding_patterns.items():
        content = re.sub(pattern, replacement, content)

    # 4. Migrar prints de errores/warnings sin emoji
    error_patterns = {
        r'print\(f"⚠️ Error obteniendo contexto: \{e\}"\)':
            'log_error(f"Error obteniendo contexto: {e}")',

        r'print\(f"🔧 DEBUG: Error en procesador embeddings \(línea 173\): \{e\}"\)':
            'log_error(f"Error en procesador embeddings (linea 173): {e}")',

        r'print\(f"🔧 DEBUG: Error en procesador embeddings \(línea 194\): \{e\}"\)':
            'log_error(f"Error en procesador embeddings (linea 194): {e}")',
    }

    for pattern, replacement in error_patterns.items():
        content = re.sub(pattern, replacement, content)

    # 5. Buscar otros print() que puedan haber quedado
    remaining_prints = re.findall(r'print\([^)]+\)', content)
    if remaining_prints:
        print(f"⚠️ Encontrados {len(remaining_prints)} print() adicionales que necesitan revisión manual:")
        for p in remaining_prints[:10]:  # Mostrar solo los primeros 10
            print(f"  - {p}")

    # Guardar archivo modificado
    if content != original_content:
        with open(FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ Migración completada")
        print(f"📊 Cambios realizados:")
        print(f"  - Eliminado logger local clip_logger")
        print(f"  - Agregado import de logging_config")
        print(f"  - Migrados prints de sistema CLIP")
        print(f"  - Migrados prints de generación de embeddings")
        print(f"  - Migrados prints de errores")
        return True
    else:
        print("⚠️ No se detectaron cambios")
        return False

if __name__ == "__main__":
    migrate_embeddings_logs()
