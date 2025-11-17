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

# Instalar dependencias Python (incluyendo spaCy)
RUN pip install --no-cache-dir -r requirements.txt && \
    # Instalar modelo español de spaCy explícitamente
    python -m spacy download es_core_news_sm && \
    # Verificar instalación de spaCy
    python -c "import spacy; nlp = spacy.load('es_core_news_sm'); print('✅ spaCy instalado correctamente')"

# Copiar código fuente
COPY clip_admin_backend/ ./clip_admin_backend/
COPY shared/ ./shared/
COPY system_config.json ./system_config.json

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
