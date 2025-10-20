/**
 * CLIP Widget - Versión Embebible Ultra-Minimalista
 * El cliente solo necesita 3 líneas de código
 */

(function() {
    'use strict';

    // Verificar configuración mínima
    if (!window.CLIPWidget || !window.CLIPWidget.apiKey) {
        console.error('CLIP Widget: Se requiere window.CLIPWidget = { apiKey: "TU_KEY" }');
        return;
    }

    const config = {
        apiKey: window.CLIPWidget.apiKey,
        serverUrl: window.CLIPWidget.serverUrl || 'https://clipcomparadorv2-production.up.railway.app',
        containerId: window.CLIPWidget.containerId || 'clip-widget',
        maxResults: window.CLIPWidget.maxResults || 3,
        buttonText: window.CLIPWidget.buttonText || '🔍 Buscar con IA'
    };

    // CSS completo inyectado
    const style = document.createElement('style');
    style.textContent = `
        .clip-widget-container {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 400px;
            margin: 20px auto;
            padding: 20px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.1);
        }
        .clip-widget-upload {
            border: 2px dashed #007bff;
            border-radius: 8px;
            padding: 40px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            background: #f8f9fa;
        }
        .clip-widget-upload:hover {
            background: #e3f2fd;
            border-color: #0056b3;
        }
        .clip-widget-upload.drag-over {
            background: #bbdefb;
            transform: scale(1.02);
        }
        .clip-widget-icon {
            font-size: 48px;
            margin-bottom: 10px;
        }
        .clip-widget-text {
            color: #666;
            font-size: 14px;
            margin: 10px 0;
        }
        .clip-widget-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            font-weight: 500;
            transition: background 0.3s;
            display: none;
        }
        .clip-widget-btn:hover {
            background: #0056b3;
        }
        .clip-widget-btn:disabled {
            background: #6c757d;
            cursor: not-allowed;
        }
        .clip-widget-preview {
            margin: 15px 0;
            display: none;
        }
        .clip-widget-preview img {
            max-width: 100%;
            max-height: 200px;
            border-radius: 8px;
        }
        .clip-widget-loading {
            text-align: center;
            padding: 20px;
            color: #007bff;
            display: none;
        }
        .clip-widget-spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #007bff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: clip-spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes clip-spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .clip-widget-results {
            margin-top: 20px;
            display: none;
        }
        .clip-widget-result-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 10px;
            transition: transform 0.2s;
        }
        .clip-widget-result-item:hover {
            transform: translateX(5px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .clip-widget-result-img {
            width: 60px;
            height: 60px;
            object-fit: cover;
            border-radius: 6px;
            flex-shrink: 0;
        }
        .clip-widget-result-info {
            flex: 1;
        }
        .clip-widget-result-name {
            font-weight: 600;
            color: #333;
            margin-bottom: 4px;
        }
        .clip-widget-result-sku {
            font-size: 12px;
            color: #888;
        }
        .clip-widget-result-similarity {
            font-size: 12px;
            color: #007bff;
            font-weight: 500;
        }
        .clip-widget-error {
            background: #f8d7da;
            color: #721c24;
            padding: 12px;
            border-radius: 6px;
            margin-top: 10px;
            display: none;
            font-size: 14px;
        }
        .clip-widget-reset {
            background: #6c757d;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            cursor: pointer;
            margin-top: 10px;
            display: none;
        }
        .clip-widget-reset:hover {
            background: #5a6268;
        }
    `;
    document.head.appendChild(style);

    // HTML del widget
    const container = document.getElementById(config.containerId);
    if (!container) {
        console.error(`CLIP Widget: No se encuentra el contenedor #${config.containerId}`);
        return;
    }

    container.innerHTML = `
        <div class="clip-widget-container">
            <div class="clip-widget-upload" id="clip-upload-area">
                <div class="clip-widget-icon">📸</div>
                <div class="clip-widget-text">Arrastra una imagen aquí<br>o haz clic para seleccionar</div>
                <input type="file" id="clip-file-input" accept="image/*" style="display:none">
            </div>
            <div class="clip-widget-preview" id="clip-preview">
                <img id="clip-preview-img" alt="Preview">
            </div>
            <button class="clip-widget-btn" id="clip-search-btn">${config.buttonText}</button>
            <div class="clip-widget-loading" id="clip-loading">
                <div class="clip-widget-spinner"></div>
                <div>Buscando productos similares...</div>
            </div>
            <div class="clip-widget-results" id="clip-results"></div>
            <div class="clip-widget-error" id="clip-error"></div>
            <button class="clip-widget-reset" id="clip-reset-btn">Nueva búsqueda</button>
        </div>
    `;

    // Referencias a elementos
    const uploadArea = document.getElementById('clip-upload-area');
    const fileInput = document.getElementById('clip-file-input');
    const preview = document.getElementById('clip-preview');
    const previewImg = document.getElementById('clip-preview-img');
    const searchBtn = document.getElementById('clip-search-btn');
    const loading = document.getElementById('clip-loading');
    const results = document.getElementById('clip-results');
    const error = document.getElementById('clip-error');
    const resetBtn = document.getElementById('clip-reset-btn');

    let selectedFile = null;

    // Click en área de upload
    uploadArea.addEventListener('click', () => fileInput.click());

    // Drag & Drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) {
            handleFile(file);
        }
    });

    // Selección de archivo
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFile(file);
        }
    });

    // Manejar archivo seleccionado
    function handleFile(file) {
        selectedFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImg.src = e.target.result;
            preview.style.display = 'block';
            searchBtn.style.display = 'inline-block';
            uploadArea.style.display = 'none';
        };
        reader.readAsDataURL(file);
    }

    // Botón de búsqueda
    searchBtn.addEventListener('click', async () => {
        if (!selectedFile) return;

        // Ocultar elementos
        searchBtn.style.display = 'none';
        results.style.display = 'none';
        error.style.display = 'none';
        resetBtn.style.display = 'none';
        loading.style.display = 'block';

        try {
            const formData = new FormData();
            formData.append('image', selectedFile);
            formData.append('max_results', config.maxResults);

            const response = await fetch(`${config.serverUrl}/api/search`, {
                method: 'POST',
                headers: {
                    'X-API-Key': config.apiKey
                },
                body: formData
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.message || data.error || 'Error en la búsqueda');
            }

            displayResults(data.results);
        } catch (err) {
            showError(err.message);
        } finally {
            loading.style.display = 'none';
            resetBtn.style.display = 'inline-block';
        }
    });

    // Mostrar resultados
    function displayResults(items) {
        if (!items || items.length === 0) {
            showError('No se encontraron productos similares');
            return;
        }

        results.innerHTML = items.map(item => `
            <div class="clip-widget-result-item">
                <img src="${item.image_url}" alt="${item.name}" class="clip-widget-result-img">
                <div class="clip-widget-result-info">
                    <div class="clip-widget-result-name">${item.name}</div>
                    <div class="clip-widget-result-sku">SKU: ${item.sku}</div>
                    <div class="clip-widget-result-similarity">
                        Similitud: ${Math.round(item.similarity * 100)}%
                    </div>
                </div>
            </div>
        `).join('');
        
        results.style.display = 'block';
    }

    // Mostrar error
    function showError(message) {
        error.textContent = message;
        error.style.display = 'block';
    }

    // Reset
    resetBtn.addEventListener('click', () => {
        selectedFile = null;
        fileInput.value = '';
        preview.style.display = 'none';
        results.style.display = 'none';
        error.style.display = 'none';
        searchBtn.style.display = 'none';
        resetBtn.style.display = 'none';
        uploadArea.style.display = 'block';
    });

    console.log('✅ CLIP Widget cargado correctamente');
})();
