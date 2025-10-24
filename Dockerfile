FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY clip_admin_backend/ ./clip_admin_backend/
COPY shared/ ./shared/

# Configurar directorio de trabajo
WORKDIR /app/clip_admin_backend

# Variables de entorno por defecto
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app
ENV PORT=5000

# Crear directorio instance si no existe
RUN mkdir -p instance

# Exponer puerto
EXPOSE $PORT

# Comando de inicio - Flask app (NO FastAPI)
CMD ["python", "app.py"]
