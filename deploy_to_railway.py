#!/usr/bin/env python3
"""
Script de deployment automático a Railway
CLIP Comparador V2 - Deployment completo
"""

import os
import subprocess
import json
import sys
from pathlib import Path

def check_railway_cli():
    """Verificar si Railway CLI está instalado"""
    try:
        result = subprocess.run(['railway', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Railway CLI instalado: {result.stdout.strip()}")
            return True
        else:
            print("❌ Railway CLI no encontrado")
            return False
    except FileNotFoundError:
        print("❌ Railway CLI no instalado")
        return False

def install_railway_cli():
    """Instalar Railway CLI"""
    print("📦 Instalando Railway CLI...")
    
    try:
        # Para Windows con npm
        result = subprocess.run(['npm', 'install', '-g', '@railway/cli'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Railway CLI instalado exitosamente")
            return True
        else:
            print(f"❌ Error instalando Railway CLI: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ npm no encontrado. Instala Node.js primero")
        return False

def railway_login():
    """Login a Railway"""
    print("🔐 Iniciando sesión en Railway...")
    
    try:
        result = subprocess.run(['railway', 'login'], check=True)
        print("✅ Login exitoso en Railway")
        return True
    except subprocess.CalledProcessError:
        print("❌ Error en login de Railway")
        return False

def create_railway_project():
    """Crear proyecto en Railway"""
    print("🚀 Creando proyecto en Railway...")
    
    project_name = "clip-comparador-v2"
    
    try:
        # Crear proyecto
        result = subprocess.run(['railway', 'new', project_name], 
                              capture_output=True, text=True, input='y\n')
        
        if result.returncode == 0:
            print(f"✅ Proyecto '{project_name}' creado")
            return True
        else:
            print(f"⚠️ Proyecto puede ya existir: {result.stderr}")
            # Intentar conectar a proyecto existente
            return link_existing_project()
            
    except Exception as e:
        print(f"❌ Error creando proyecto: {e}")
        return False

def link_existing_project():
    """Conectar a proyecto existente"""
    print("🔗 Conectando a proyecto existente...")
    
    try:
        result = subprocess.run(['railway', 'link'], check=True)
        print("✅ Conectado a proyecto Railway")
        return True
    except subprocess.CalledProcessError:
        print("❌ Error conectando a proyecto")
        return False

def add_postgresql():
    """Agregar PostgreSQL al proyecto"""
    print("🐘 Agregando PostgreSQL...")
    
    try:
        result = subprocess.run(['railway', 'add', 'postgresql'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ PostgreSQL agregado al proyecto")
            return True
        else:
            print("⚠️ PostgreSQL puede ya estar agregado")
            return True
    except Exception as e:
        print(f"❌ Error agregando PostgreSQL: {e}")
        return False

def add_redis():
    """Agregar Redis al proyecto (opcional)"""
    print("📦 Agregando Redis...")
    
    try:
        result = subprocess.run(['railway', 'add', 'redis'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Redis agregado al proyecto")
            return True
        else:
            print("⚠️ Redis puede ya estar agregado")
            return True
    except Exception as e:
        print(f"❌ Error agregando Redis: {e}")
        return False

def set_environment_variables(config):
    """Configurar variables de entorno"""
    print("⚙️ Configurando variables de entorno...")
    
    variables = {
        'FLASK_ENV': 'production',
        'FLASK_DEBUG': 'False',
        'SECRET_KEY': config['secret_key'],
        'CLOUDINARY_CLOUD_NAME': config['cloudinary_cloud_name'],
        'CLOUDINARY_API_KEY': config['cloudinary_api_key'],
        'CLOUDINARY_API_SECRET': config['cloudinary_api_secret'],
        'APP_URL': 'https://clip-comparador-v2.railway.app',
        'CLIP_MODEL_NAME': 'ViT-B/16',
        'LOG_LEVEL': 'INFO'
    }
    
    for key, value in variables.items():
        try:
            result = subprocess.run(['railway', 'variables', 'set', f'{key}={value}'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"   ✅ {key} configurada")
            else:
                print(f"   ❌ Error configurando {key}: {result.stderr}")
        except Exception as e:
            print(f"   ❌ Error con {key}: {e}")

def create_railway_toml():
    """Crear archivo railway.toml para configuración"""
    
    toml_content = """[build]
builder = "NIXPACKS"

[deploy]
healthcheckPath = "/"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10

[[services]]
name = "clip-admin-backend"
source = "clip_admin_backend"

[services.variables]
FLASK_ENV = "production"
FLASK_DEBUG = "False"

[[services.domains]]
"""

    with open('railway.toml', 'w') as f:
        f.write(toml_content)
    
    print("✅ railway.toml creado")

def create_dockerfiles():
    """Crear Dockerfiles optimizados para Railway"""
    
    # Dockerfile para backend admin
    admin_dockerfile = """FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicación
COPY clip_admin_backend/ ./clip_admin_backend/
COPY shared/ ./shared/

WORKDIR /app/clip_admin_backend

# Variables de entorno
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Puerto
EXPOSE 5000

# Comando de inicio
CMD ["python", "app.py"]
"""

    os.makedirs('clip_admin_backend', exist_ok=True)
    with open('clip_admin_backend/Dockerfile', 'w') as f:
        f.write(admin_dockerfile)
    
    print("✅ Dockerfile para admin backend creado")

def create_procfile():
    """Crear Procfile para Railway"""
    
    procfile_content = """web: cd clip_admin_backend && python app.py
"""

    with open('Procfile', 'w') as f:
        f.write(procfile_content)
    
    print("✅ Procfile creado")

def run_database_migration():
    """Ejecutar migración de base de datos"""
    print("🗄️ Ejecutando migración de base de datos...")
    
    try:
        # Obtener URL de PostgreSQL de Railway
        result = subprocess.run(['railway', 'variables'], 
                              capture_output=True, text=True)
        
        if 'DATABASE_URL' in result.stdout:
            print("✅ PostgreSQL disponible")
            
            # Ejecutar script de estructura
            structure_file = None
            import_file = None
            
            for file in os.listdir('.'):
                if file.endswith('_postgresql_structure.sql'):
                    structure_file = file
                if file.endswith('_import_to_postgresql.py'):
                    import_file = file
            
            if structure_file and import_file:
                print(f"📊 Ejecutando migración con {structure_file}")
                
                # Ejecutar importación de datos
                result = subprocess.run(['python', import_file], 
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("✅ Migración de datos completada")
                    return True
                else:
                    print(f"❌ Error en migración: {result.stderr}")
                    return False
            else:
                print("⚠️ Archivos de migración no encontrados")
                return False
        else:
            print("❌ DATABASE_URL no disponible")
            return False
            
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        return False

def deploy_to_railway():
    """Deploy a Railway"""
    print("🚀 Iniciando deployment a Railway...")
    
    try:
        result = subprocess.run(['railway', 'deploy'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Deployment exitoso!")
            
            # Obtener URL del deployment
            url_result = subprocess.run(['railway', 'domain'], 
                                      capture_output=True, text=True)
            
            if url_result.returncode == 0:
                print(f"🌐 URL de la aplicación: {url_result.stdout.strip()}")
            
            return True
        else:
            print(f"❌ Error en deployment: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error en deployment: {e}")
        return False

def main():
    """Función principal de deployment"""
    print("🚂 DEPLOYMENT AUTOMÁTICO A RAILWAY")
    print("CLIP Comparador V2 - Sistema Completo")
    print("=" * 50)
    
    # Verificar Railway CLI
    if not check_railway_cli():
        if not install_railway_cli():
            print("❌ No se pudo instalar Railway CLI")
            return False
    
    # Solicitar configuración
    print("\n📋 CONFIGURACIÓN NECESARIA:")
    config = {}
    
    config['secret_key'] = input("Secret Key para Flask (deja vacío para generar): ").strip()
    if not config['secret_key']:
        import secrets
        config['secret_key'] = secrets.token_urlsafe(32)
        print(f"🔑 Secret Key generada: {config['secret_key']}")
    
    config['cloudinary_cloud_name'] = input("Cloudinary Cloud Name: ").strip()
    config['cloudinary_api_key'] = input("Cloudinary API Key: ").strip()
    config['cloudinary_api_secret'] = input("Cloudinary API Secret: ").strip()
    
    if not all(config.values()):
        print("❌ Faltan datos de configuración")
        return False
    
    # Proceso de deployment
    steps = [
        ("🔐 Login a Railway", railway_login),
        ("🚀 Crear/conectar proyecto", create_railway_project),
        ("🐘 Agregar PostgreSQL", add_postgresql),
        ("📦 Agregar Redis", add_redis),
        ("⚙️ Configurar variables", lambda: set_environment_variables(config)),
        ("📄 Crear archivos de deployment", create_railway_toml),
        ("🐳 Crear Dockerfiles", create_dockerfiles),
        ("📝 Crear Procfile", create_procfile),
        ("🗄️ Migrar base de datos", run_database_migration),
        ("🚀 Deploy aplicación", deploy_to_railway)
    ]
    
    for description, step_func in steps:
        print(f"\n{description}...")
        try:
            if not step_func():
                print(f"❌ Falló: {description}")
                return False
        except Exception as e:
            print(f"❌ Error en {description}: {e}")
            return False
    
    print("\n🎉 ¡DEPLOYMENT COMPLETADO EXITOSAMENTE!")
    print("🌐 Tu aplicación está ahora disponible en Railway")
    print("📊 Verifica el deployment en: https://railway.app/dashboard")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n💥 Deployment falló. Revisar errores arriba.")
        sys.exit(1)
    else:
        print("\n🎊 ¡Sistema CLIP Comparador V2 desplegado en Railway!")