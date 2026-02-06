<?php
/**
 * Plugin Name: CLIP Visual Search
 * Plugin URI: https://clipcomparadorv2-production.up.railway.app
 * Description: Búsqueda visual de productos con IA - Sube una foto y encuentra productos similares
 * Version: 1.0.0
 * Author: CLIP Comparador
 * Requires at least: 5.8
 * Requires PHP: 7.4
 * WC requires at least: 5.0
 * WC tested up to: 8.5
 * License: GPL v2 or later
 * Text Domain: clip-visual-search
 */

define('CLIP_VS_PLUGIN_VERSION', '1.0.1');

if (!defined('ABSPATH')) {
    exit; // Exit if accessed directly
}

// Verificar que WooCommerce esté activo
function clip_vs_check_woocommerce() {
    if (!class_exists('WooCommerce')) {
        add_action('admin_notices', function() {
            echo '<div class="error"><p><strong>CLIP Visual Search</strong> requiere WooCommerce activo.</p></div>';
        });
        return false;
    }
    return true;
}
add_action('plugins_loaded', 'clip_vs_check_woocommerce');

// ==================== CONFIGURACIÓN ====================

class CLIP_Visual_Search_Settings {

    private static $instance = null;

    public static function get_instance() {
        if (self::$instance === null) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    public function __construct() {
        add_action('admin_menu', array($this, 'add_settings_page'));
        add_action('admin_init', array($this, 'register_settings'));
        add_filter('plugin_action_links_' . plugin_basename(__FILE__), array($this, 'add_settings_link'));
    }

    public function add_settings_page() {
        add_options_page(
            'CLIP Visual Search - Configuración',
            'CLIP Search',
            'manage_options',
            'clip-visual-search',
            array($this, 'render_settings_page')
        );
    }

    public function add_settings_link($links) {
        $settings_link = '<a href="' . admin_url('options-general.php?page=clip-visual-search') . '">Ajustes</a>';
        array_unshift($links, $settings_link);
        return $links;
    }

    public function register_settings() {
        register_setting('clip_vs_settings', 'clip_vs_api_key');
        register_setting('clip_vs_settings', 'clip_vs_server_url');
        register_setting('clip_vs_settings', 'clip_vs_button_text');
        register_setting('clip_vs_settings', 'clip_vs_button_position');
        register_setting('clip_vs_settings', 'clip_vs_widget_version');
    }

    public function render_settings_page() {
        ?>
        <div class="wrap">
            <h1>⚙️ CLIP Visual Search - Configuración</h1>
            <form method="post" action="options.php">
                <?php settings_fields('clip_vs_settings'); ?>
                <table class="form-table">
                    <tr>
                        <th scope="row"><label for="clip_vs_api_key">API Key *</label></th>
                        <td>
                            <input type="text" id="clip_vs_api_key" name="clip_vs_api_key"
                                   value="<?php echo esc_attr(get_option('clip_vs_api_key')); ?>"
                                   class="regular-text" required>
                            <p class="description">Tu API Key del sistema CLIP (obtenida del panel admin)</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row"><label for="clip_vs_server_url">URL del Servidor</label></th>
                        <td>
                            <input type="url" id="clip_vs_server_url" name="clip_vs_server_url"
                                   value="<?php echo esc_attr(get_option('clip_vs_server_url', 'https://clipcomparadorv2-production.up.railway.app')); ?>"
                                   class="regular-text">
                            <p class="description">URL de tu servidor Railway (dejar por defecto si no cambiaste)</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row"><label for="clip_vs_button_text">Texto del Botón</label></th>
                        <td>
                            <input type="text" id="clip_vs_button_text" name="clip_vs_button_text"
                                   value="<?php echo esc_attr(get_option('clip_vs_button_text', '🔍 Buscar por Imagen')); ?>"
                                   class="regular-text">
                        </td>
                    </tr>
                    <tr>
                        <th scope="row"><label for="clip_vs_button_position">Posición del Botón</label></th>
                        <td>
                            <select id="clip_vs_button_position" name="clip_vs_button_position">
                                <option value="woocommerce_before_shop_loop" <?php selected(get_option('clip_vs_button_position', 'woocommerce_before_shop_loop'), 'woocommerce_before_shop_loop'); ?>>
                                    Antes del catálogo
                                </option>
                                <option value="woocommerce_after_shop_loop" <?php selected(get_option('clip_vs_button_position'), 'woocommerce_after_shop_loop'); ?>>
                                    Después del catálogo
                                </option>
                                <option value="wp_footer" <?php selected(get_option('clip_vs_button_position'), 'wp_footer'); ?>>
                                    Botón flotante (footer)
                                </option>
                            </select>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row"><label for="clip_vs_widget_version">Versión del Widget</label></th>
                        <td>
                            <input type="text" id="clip_vs_widget_version" name="clip_vs_widget_version"
                                   value="<?php echo esc_attr(get_option('clip_vs_widget_version', CLIP_VS_PLUGIN_VERSION)); ?>"
                                   class="regular-text">
                            <p class="description">Usar para forzar recarga del JS (ej: 1.0.1)</p>
                        </td>
                    </tr>
                </table>
                <?php submit_button('Guardar Configuración'); ?>
            </form>

            <hr>
            <h2>📖 Instrucciones</h2>
            <ol>
                <li>Obtén tu API Key desde el panel admin de CLIP Comparador</li>
                <li>Pégala en el campo "API Key" arriba</li>
                <li>Guarda los cambios</li>
                <li>El widget aparecerá automáticamente en tu tienda</li>
            </ol>

            <h3>🎨 Shortcode (opcional)</h3>
            <p>Usa <code>[clip_search_button]</code> para agregar el botón manualmente en cualquier página.</p>
        </div>
        <?php
    }
}

// Inicializar el plugin
if (is_admin()) {
    CLIP_Visual_Search_Settings::get_instance();
}

// ==================== FRONTEND ====================

function clip_vs_enqueue_widget() {
    if (!is_admin() && get_option('clip_vs_api_key')) {
        // Configuración del widget
        $api_key = get_option('clip_vs_api_key');
        $server_url = get_option('clip_vs_server_url', 'https://clipcomparadorv2-production.up.railway.app');
        $widget_version = get_option('clip_vs_widget_version', CLIP_VS_PLUGIN_VERSION);

        // Inyectar configuración
        wp_add_inline_script('jquery', "
            window.CLIPWidget = {
                apiKey: '" . esc_js($api_key) . "',
                serverUrl: '" . esc_js($server_url) . "'
            };
        ", 'before');

        // Cargar widget desde tu servidor
        wp_enqueue_script(
            'clip-widget-v4',
            $server_url . '/static/js/clip-widget-embed-v4.js',
            array('jquery'),
            $widget_version,
            true
        );

        // CSS personalizado para WooCommerce
        wp_add_inline_style('wp-block-library', "
            .clip-search-trigger-btn {
                display: inline-block;
                padding: 12px 24px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
                transition: all 0.3s ease;
                margin: 20px 0;
            }
            .clip-search-trigger-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
            }
            .clip-search-floating {
                position: fixed;
                bottom: 30px;
                right: 30px;
                z-index: 9999;
            }
        ");

    }
}
add_action('wp_enqueue_scripts', 'clip_vs_enqueue_widget');

// Renderizar botón flotante directamente en el footer (funciona en TODAS las páginas)
function clip_vs_render_floating_button() {
    $position = get_option('clip_vs_button_position', 'woocommerce_before_shop_loop');
    if ($position === 'wp_footer' && get_option('clip_vs_api_key')) {
        $button_text = get_option('clip_vs_button_text', '🔍 Buscar por Imagen');
        echo '<button class="clip-search-trigger-btn clip-search-floating" onclick="if(window.CLIPV2) window.CLIPV2.overlay.open(); return false;">';
        echo esc_html($button_text);
        echo '</button>';
    }
}
add_action('wp_footer', 'clip_vs_render_floating_button', 999);

// Botón de activación
function clip_vs_render_button($floating = false) {
    if (!get_option('clip_vs_api_key')) {
        return;
    }

    $button_text = get_option('clip_vs_button_text', '🔍 Buscar por Imagen');
    $class = $floating ? 'clip-search-trigger-btn clip-search-floating' : 'clip-search-trigger-btn';

    echo '<button class="' . esc_attr($class) . '" onclick="if(window.CLIPV2) window.CLIPV2.overlay.open(); return false;">';
    echo esc_html($button_text);
    echo '</button>';
}

// Hook según configuración
function clip_vs_add_button() {
    $position = get_option('clip_vs_button_position', 'woocommerce_before_shop_loop');

    if ($position === 'wp_footer') {
        clip_vs_render_button(true); // Floating button
    } else {
        clip_vs_render_button(false); // Inline button
    }
}

// Registrar en la posición elegida
$position = get_option('clip_vs_button_position', 'woocommerce_before_shop_loop');
add_action($position, 'clip_vs_add_button');

// Shortcode
function clip_vs_shortcode($atts) {
    ob_start();
    clip_vs_render_button(false);
    return ob_get_clean();
}
add_shortcode('clip_search_button', 'clip_vs_shortcode');

// ==================== ACTIVACIÓN ====================

register_activation_hook(__FILE__, function() {
    // Valores por defecto
    add_option('clip_vs_server_url', 'https://clipcomparadorv2-production.up.railway.app');
    add_option('clip_vs_button_text', '🔍 Buscar por Imagen');
    add_option('clip_vs_button_position', 'woocommerce_before_shop_loop');
    add_option('clip_vs_widget_version', CLIP_VS_PLUGIN_VERSION);
});

register_deactivation_hook(__FILE__, function() {
    // No borrar configuración, por si reactivan
});
