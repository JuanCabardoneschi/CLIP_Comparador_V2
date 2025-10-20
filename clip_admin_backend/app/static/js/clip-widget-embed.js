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

    // Esperar a que el DOM esté listo
    function initWidget() {
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
            max-width: 1200px;
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
        .clip-widget-results-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }
        .clip-widget-result-item {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .clip-widget-result-item:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }
        .clip-widget-result-img {
            width: 100%;
            height: 200px;
            object-fit: cover;
        }
        .clip-widget-result-content {
            padding: 16px;
        }
        .clip-widget-result-name {
            font-weight: 700;
            color: #333;
            margin-bottom: 8px;
            font-size: 16px;
        }
        .clip-widget-result-sku {
            font-size: 13px;
            color: #888;
            margin-bottom: 12px;
        }
        .clip-widget-result-similarity {
            display: inline-block;
            padding: 4px 10px;
            background: #e3f2fd;
            color: #007bff;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 12px;
        }
        .clip-widget-result-attributes {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #eee;
        }
        .clip-widget-result-attribute {
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            font-size: 13px;
        }
        .clip-widget-result-attribute-key {
            color: #666;
            font-weight: 500;
        }
        .clip-widget-result-attribute-value {
            color: #333;
            text-align: right;
        }
        .clip-widget-result-link {
            display: inline-block;
            margin-top: 12px;
            padding: 8px 16px;
            background: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            transition: background 0.2s;
        }
        .clip-widget-result-link:hover {
            background: #0056b3;
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

        results.innerHTML = '<div class="clip-widget-results-grid">' + items.map(item => {
            // Atributos visibles
            let attributesHtml = '';
            if (item.attributes && typeof item.attributes === 'object') {
                const visibleAttrs = Object.entries(item.attributes)
                    .filter(([key, attr]) => {
                        // Mostrar solo atributos marcados como visible
                        if (typeof attr === 'object' && attr.visible === true) {
                            return true;
                        }
                        // O atributos simples que no son objetos de configuración
                        if (typeof attr !== 'object' && key !== 'visible') {
                            return true;
                        }
                        return false;
                    })
                    .map(([key, attr]) => {
                        const value = typeof attr === 'object' ? attr.value : attr;
                        const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                        // Si es url_producto, renderizar como link
                        if (key === 'url_producto' && value) {
                            return `
                                <div class="clip-widget-result-attribute">
                                    <a href="${value}" target="_blank" class="clip-widget-result-link">
                                        Ver Producto →
                                    </a>
                                </div>
                            `;
                        }

                        // Renderizar atributo normal
                        if (value && value !== '' && value !== null) {
                            const displayValue = Array.isArray(value) ? value.join(', ') : value;
                            return `
                                <div class="clip-widget-result-attribute">
                                    <span class="clip-widget-result-attribute-key">${label}:</span>
                                    <span class="clip-widget-result-attribute-value">${displayValue}</span>
                                </div>
                            `;
                        }
                        return '';
                    })
                    .filter(html => html !== '')
                    .join('');

                if (visibleAttrs.length > 0) {
                    attributesHtml = `<div class="clip-widget-result-attributes">${visibleAttrs}</div>`;
                }
            }

            return `
                <div class="clip-widget-result-item">
                    <img src="${item.image_url}" alt="${item.name}" class="clip-widget-result-img">
                    <div class="clip-widget-result-content">
                        <div class="clip-widget-result-name">${item.name}</div>
                        <div class="clip-widget-result-sku">SKU: ${item.sku}</div>
                        <div class="clip-widget-result-similarity">
                            ${Math.round(item.similarity * 100)}% similitud
                        </div>
                        ${attributesHtml}
                    </div>
                </div>
            `;
        }).join('') + '</div>';

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
    window.clipWidgetLoaded = true;
    }

    // Inicializar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWidget);
    } else {
        initWidget();
    }
})();
