FROM python:3.10-slim

WORKDIR /app

# Configurar caché de HuggingFace para que los modelos descargados en build se usen en runtime
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface

# Crear directorio de caché (persistirá en la imagen)
RUN mkdir -p /app/.cache/huggingface

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias Python (incluyendo spaCy y el modelo vía pip) y verificar instalación
RUN pip install --no-cache-dir -r requirements.txt && \
    python -c "import spacy; spacy.load('es_core_news_md'); print('✅ spaCy instalado correctamente')" && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); print('✅ MiniLM precargado en imagen Docker')" && \
    python -c "from transformers import CLIPModel, CLIPProcessor; CLIPModel.from_pretrained('openai/clip-vit-base-patch16'); CLIPProcessor.from_pretrained('openai/clip-vit-base-patch16'); print('✅ CLIP precargado en imagen Docker')"

# Copiar solo runtime del backend (evitar logs, tools y tests)
COPY clip_admin_backend/app/ ./clip_admin_backend/app/
COPY clip_admin_backend/app.py ./clip_admin_backend/app.py
COPY clip_admin_backend/wsgi.py ./clip_admin_backend/wsgi.py
COPY shared/ ./shared/
COPY system_config.json ./system_config.json

# Configurar directorio de trabajo
WORKDIR /app/clip_admin_backend

# Variables de entorno por defecto
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV SPACY_MODEL=es_core_news_md
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_OFFLINE=1
ENV HF_HUB_OFFLINE=1
ENV PYTHONPATH=/app
ENV PORT=5000

# Crear directorio instance si no existe
RUN mkdir -p instance

# Exponer puerto
EXPOSE $PORT

# Comando de inicio - Flask app (NO FastAPI)
CMD ["python", "app.py"]
