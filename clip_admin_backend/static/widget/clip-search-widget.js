/**
 * CLIP Search Widget - JavaScript Embebible
 * Version: 1.0.0
 *
 * Widget de búsqueda visual que se puede embeber en cualquier sitio web
 * Solo requiere un div con data-api-key y este script
 */

(function() {
    'use strict';

    // Configuración del widget
    const CONFIG = {
        API_BASE_URL: 'http://localhost:5000',
        WIDGET_VERSION: '1.0.0',
        MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
        ALLOWED_TYPES: ['image/jpeg', 'image/png', 'image/webp'],
        DEFAULT_LIMIT: 3,
        DEFAULT_THRESHOLD: 0.5
    };

    // Estilos CSS para el widget
    const WIDGET_STYLES = `
        .clip-search-widget {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 600px;
            margin: 20px auto;
            padding: 20px;
            border: 2px dashed #e0e0e0;
            border-radius: 12px;
            background: #fafafa;
            text-align: center;
            transition: all 0.3s ease;
        }

        .clip-search-widget.dragover {
            border-color: #007bff;
            background: #f0f8ff;
        }

        .clip-search-widget h3 {
            margin: 0 0 15px 0;
            color: #333;
            font-size: 18px;
        }

        .clip-upload-area {
            margin: 20px 0;
        }

        .clip-file-input {
            display: none;
        }

        .clip-upload-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            transition: transform 0.2s ease;
        }

        .clip-upload-btn:hover {
            transform: translateY(-2px);
        }

        .clip-upload-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }

        .clip-query-image {
            max-width: 300px;
            max-height: 200px;
            border-radius: 8px;
            margin: 15px 0;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }

        .clip-loading {
            display: none;
            margin: 20px 0;
        }

        .clip-spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .clip-results {
            margin-top: 30px;
        }

        .clip-results h4 {
            color: #333;
            margin: 0 0 20px 0;
            font-size: 16px;
        }

        .clip-results-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }

        .clip-result-item {
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s ease;
            text-align: center;
            min-height: 350px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .clip-result-item:hover {
            transform: translateY(-4px);
        }

        .clip-result-image {
            width: 100%;
            height: 150px;
            object-fit: contain;
            border-radius: 6px;
            margin-bottom: 10px;
            background: #f8f9fa;
            border: 1px solid #e9ecef;
        }

        .clip-result-name {
            font-weight: 600;
            color: #333;
            margin: 0 0 5px 0;
            font-size: 14px;
        }

        .clip-result-sku {
            color: #666;
            font-size: 12px;
            margin: 0 0 8px 0;
        }

        .clip-result-content {
            display: flex;
            flex-direction: column;
            gap: 5px;
            flex-grow: 1;
        }

        .clip-result-description {
            color: #666;
            font-size: 12px;
            line-height: 1.3;
            margin: 0 0 5px 0;
            text-align: left;
            background: #f8f9fa;
            padding: 5px 8px;
            border-radius: 4px;
        }

        .clip-result-category {
            background: #e3f2fd;
            color: #1976d2;
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 10px;
            margin: 0 0 5px 0;
            display: inline-block;
        }

        .clip-result-stock {
            font-size: 12px;
            font-weight: 500;
            margin: 5px 0;
            padding: 3px 6px;
            border-radius: 4px;
        }

        .clip-result-stock.in-stock {
            background: #e8f5e8;
            color: #2e7d32;
        }

        .clip-result-stock.out-of-stock {
            background: #ffebee;
            color: #c62828;
        }

        .clip-result-price {
            color: #007bff;
            font-weight: 600;
            font-size: 14px;
            margin: 0 0 5px 0;
        }

        .clip-similarity {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }

        .clip-error {
            background: #ffe6e6;
            color: #d63031;
            padding: 10px;
            border-radius: 6px;
            margin: 10px 0;
            font-size: 14px;
        }

        .clip-info {
            color: #666;
            font-size: 12px;
            margin-top: 15px;
        }
    `;

    // Clase principal del widget
    class ClipSearchWidget {
        constructor(container, apiKey) {
            this.container = container;
            this.apiKey = apiKey;
            this.isLoading = false;

            this.init();
        }

        init() {
            this.injectStyles();
            this.render();
            this.bindEvents();

            console.log('🎯 CLIP Search Widget inicializado');
        }

        injectStyles() {
            if (!document.getElementById('clip-widget-styles')) {
                const style = document.createElement('style');
                style.id = 'clip-widget-styles';
                style.textContent = WIDGET_STYLES;
                document.head.appendChild(style);
            }
        }

        render() {
            this.container.innerHTML = `
                <div class="clip-search-widget">
                    <h3>🔍 Búsqueda Visual</h3>
                    <p>Sube una imagen para encontrar productos similares</p>

                    <div class="clip-upload-area">
                        <input type="file" class="clip-file-input" accept="image/*" />
                        <button class="clip-upload-btn">
                            📷 Seleccionar Imagen
                        </button>
                        <p style="margin: 10px 0 0 0; font-size: 12px; color: #666;">
                            O arrastra una imagen aquí
                        </p>
                    </div>

                    <div class="clip-query-preview"></div>

                    <div class="clip-loading">
                        <div class="clip-spinner"></div>
                        <p>Analizando imagen...</p>
                    </div>

                    <div class="clip-results"></div>

                    <div class="clip-info">
                        Powered by CLIP Comparador V2
                    </div>
                </div>
            `;
        }

        bindEvents() {
            const fileInput = this.container.querySelector('.clip-file-input');
            const uploadBtn = this.container.querySelector('.clip-upload-btn');
            const widget = this.container.querySelector('.clip-search-widget');

            // Click en botón de upload
            uploadBtn.addEventListener('click', () => {
                if (!this.isLoading) {
                    fileInput.click();
                }
            });

            // Cambio de archivo
            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.handleFileSelection(e.target.files[0]);
                }
            });

            // Drag & Drop
            widget.addEventListener('dragover', (e) => {
                e.preventDefault();
                widget.classList.add('dragover');
            });

            widget.addEventListener('dragleave', (e) => {
                e.preventDefault();
                widget.classList.remove('dragover');
            });

            widget.addEventListener('drop', (e) => {
                e.preventDefault();
                widget.classList.remove('dragover');

                if (e.dataTransfer.files.length > 0) {
                    this.handleFileSelection(e.dataTransfer.files[0]);
                }
            });
        }

        async handleFileSelection(file) {
            // Validar archivo
            const validation = this.validateFile(file);
            if (!validation.valid) {
                this.showError(validation.message);
                return;
            }

            // Mostrar preview
            this.showImagePreview(file);

            // Realizar búsqueda
            await this.performSearch(file);
        }

        validateFile(file) {
            if (!CONFIG.ALLOWED_TYPES.includes(file.type)) {
                return {
                    valid: false,
                    message: 'Tipo de archivo no válido. Solo se permiten imágenes JPG, PNG o WebP.'
                };
            }

            if (file.size > CONFIG.MAX_FILE_SIZE) {
                return {
                    valid: false,
                    message: 'El archivo es demasiado grande. Máximo 10MB.'
                };
            }

            return { valid: true };
        }

        showImagePreview(file) {
            const preview = this.container.querySelector('.clip-query-preview');
            const reader = new FileReader();

            reader.onload = (e) => {
                preview.innerHTML = `
                    <h4>📷 Imagen de consulta</h4>
                    <img src="${e.target.result}" class="clip-query-image" alt="Imagen de consulta">
                `;
            };

            reader.readAsDataURL(file);
        }

        async performSearch(file) {
            this.setLoading(true);
            this.clearResults();
            this.clearError();

            try {
                const formData = new FormData();
                formData.append('image', file);
                formData.append('limit', CONFIG.DEFAULT_LIMIT);
                formData.append('threshold', CONFIG.DEFAULT_THRESHOLD);

                console.log('🚀 Enviando búsqueda visual...');

                const response = await fetch(`${CONFIG.API_BASE_URL}/api/search`, {
                    method: 'POST',
                    headers: {
                        'X-API-Key': this.apiKey
                    },
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(`Error ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();
                console.log('📦 Resultados recibidos:', data);

                this.displayResults(data);

            } catch (error) {
                console.error('❌ Error en búsqueda:', error);

                // Mensajes de error más amigables
                let errorMessage;
                if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
                    errorMessage = '🔌 No se puede conectar con el servicio de búsqueda. Por favor, inténtalo más tarde.';
                } else if (error.message.includes('404')) {
                    errorMessage = '🔍 Servicio de búsqueda no disponible temporalmente.';
                } else if (error.message.includes('500')) {
                    errorMessage = '⚠️ Error interno del servidor. Por favor, inténtalo más tarde.';
                } else if (error.message.includes('403') || error.message.includes('401')) {
                    errorMessage = '🔐 Acceso no autorizado. Verifica tu configuración.';
                } else {
                    errorMessage = '❌ Ups, algo salió mal. Por favor, inténtalo nuevamente.';
                }

                this.showError(errorMessage);
            } finally {
                this.setLoading(false);
            }
        }

        displayResults(data) {
            const resultsContainer = this.container.querySelector('.clip-results');

            if (!data.results || data.results.length === 0) {
                resultsContainer.innerHTML = `
                    <div class="clip-error">
                        No se encontraron productos similares.
                        Intenta con otra imagen.
                    </div>
                `;
                return;
            }

            const resultsHtml = `
                <h4>🎯 ${data.results.length} productos similares encontrados</h4>
                <div class="clip-results-grid">
                    ${data.results.map(product => `
                        <div class="clip-result-item">
                            ${product.image_url ? `
                                <img src="${product.image_url}"
                                     class="clip-result-image"
                                     alt="${product.name}"
                                     onerror="this.style.display='none'">
                            ` : ''}
                            <div class="clip-result-content">
                                <div class="clip-result-name">${product.name}</div>
                                ${product.description && product.description !== 'Sin descripción disponible' ? `
                                    <div class="clip-result-description">${product.description.length > 60 ? product.description.substring(0, 60) + '...' : product.description}</div>
                                ` : ''}
                                <div class="clip-result-sku">SKU: ${product.sku}</div>
                                ${product.category ? `
                                    <div class="clip-result-category">${product.category}</div>
                                ` : ''}
                                ${product.price ? `
                                    <div class="clip-result-price">$${product.price}</div>
                                ` : ''}
                                <div class="clip-result-stock ${product.stock > 0 ? 'in-stock' : 'out-of-stock'}">
                                    ${product.stock > 0 ? `✅ ${product.stock} disponibles` : '❌ Sin stock'}
                                </div>
                                <div class="clip-similarity">
                                    ${Math.round(product.similarity * 100)}% similar
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
                <div class="clip-info">
                    Búsqueda completada en ${data.processing_time}s
                </div>
            `;

            resultsContainer.innerHTML = resultsHtml;
        }

        setLoading(loading) {
            this.isLoading = loading;
            const loadingEl = this.container.querySelector('.clip-loading');
            const uploadBtn = this.container.querySelector('.clip-upload-btn');

            if (loading) {
                loadingEl.style.display = 'block';
                uploadBtn.disabled = true;
                uploadBtn.textContent = 'Analizando...';
            } else {
                loadingEl.style.display = 'none';
                uploadBtn.disabled = false;
                uploadBtn.textContent = '📷 Seleccionar Imagen';
            }
        }

        showError(message) {
            const resultsContainer = this.container.querySelector('.clip-results');
            resultsContainer.innerHTML = `<div class="clip-error">${message}</div>`;
        }

        clearError() {
            const errorEl = this.container.querySelector('.clip-error');
            if (errorEl) {
                errorEl.remove();
            }
        }

        clearResults() {
            const resultsContainer = this.container.querySelector('.clip-results');
            resultsContainer.innerHTML = '';
        }
    }

    // Auto-inicialización cuando se carga el DOM
    function initializeWidgets() {
        const widgets = document.querySelectorAll('[id="clip-search-widget"]');

        widgets.forEach(container => {
            const apiKey = container.getAttribute('data-api-key');

            if (!apiKey) {
                console.error('❌ CLIP Widget: data-api-key requerido');
                container.innerHTML = `
                    <div style="color: red; padding: 20px; border: 1px solid red; border-radius: 8px;">
                        ❌ Error: Se requiere data-api-key para el widget de búsqueda visual
                    </div>
                `;
                return;
            }

            new ClipSearchWidget(container, apiKey);
        });
    }

    // Inicializar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeWidgets);
    } else {
        initializeWidgets();
    }

})();
