<?php
/**
 * Plugin Name: WP Updater Connector
 * Description: Secure REST connector that reports WordPress core/plugin/theme update status to a self-hosted WP Updater dashboard, and (optionally) applies updates or toggles auto-updates on request.
 * Version: 1.3.1
 * Author: WP Updater
 * License: GPL-2.0-or-later
 *
 * Install: drop this single file into wp-content/mu-plugins/ (create the folder
 * if it does not exist). It is then always-active. After installing, go to
 * Settings -> WP Updater to copy the auto-generated API key into the dashboard.
 *
 * Backwards compatible: also answers on the legacy `wpmonitor/v1` REST
 * namespace and accepts the legacy `X-WPMonitor-Key` header / `wpmonitor_api_key`
 * option, so dashboards from before the WP Updater rename keep working.
 */

if (!defined('ABSPATH')) {
    exit;
}

if (!defined('WPUPDATER_VERSION')) {
    define('WPUPDATER_VERSION', '1.3.1');
}

/**
 * Return the connector API key.
 *
 * Priority:
 *   1) WPUPDATER_API_KEY (or legacy WPMONITOR_API_KEY) constant in wp-config.php.
 *   2) The auto-generated, stored option (created on first load). The legacy
 *      `wpmonitor_api_key` option is migrated to `wpupdater_api_key` if present.
 */
function wpupdater_get_api_key() {
    if (defined('WPUPDATER_API_KEY') && WPUPDATER_API_KEY) {
        return (string) WPUPDATER_API_KEY;
    }
    if (defined('WPMONITOR_API_KEY') && WPMONITOR_API_KEY) {
        return (string) WPMONITOR_API_KEY;
    }
    $key = get_option('wpupdater_api_key');
    if (!$key) {
        // Migrate a key stored by the pre-rename connector, if any.
        $legacy = get_option('wpmonitor_api_key');
        if ($legacy) {
            $key = $legacy;
            update_option('wpupdater_api_key', $key, false);
        }
    }
    if (!$key) {
        // 64 hex chars. avoids special chars that complicate headers.
        $key = bin2hex(random_bytes(32));
        update_option('wpupdater_api_key', $key, false);
    }
    return (string) $key;
}

/**
 * Constant-time check of the incoming key against the stored key.
 */
function wpupdater_check_auth(WP_REST_Request $request) {
    $provided = $request->get_header('x_wpupdater_key');
    if (!$provided) {
        $provided = $request->get_header('x_wpmonitor_key');
    }
    if (!$provided) {
        $provided = $request->get_param('key');
    }
    if (!is_string($provided) || $provided === '') {
        return new WP_Error('wpupdater_no_key', 'Missing API key.', array('status' => 401));
    }
    $expected = wpupdater_get_api_key();
    if (!hash_equals($expected, $provided)) {
        return new WP_Error('wpupdater_bad_key', 'Invalid API key.', array('status' => 403));
    }
    return true;
}

/**
 * Make sure the update/plugin/theme APIs are loaded outside of wp-admin.
 */
function wpupdater_load_update_apis() {
    if (!function_exists('get_plugins')) {
        require_once ABSPATH . 'wp-admin/includes/plugin.php';
    }
    require_once ABSPATH . 'wp-admin/includes/update.php';
    require_once ABSPATH . 'wp-admin/includes/misc.php';
    // file.php defines WP_Filesystem() and request_filesystem_credentials(),
    // which the upgraders call; without it updates fatal outside wp-admin.
    if (!function_exists('request_filesystem_credentials')) {
        require_once ABSPATH . 'wp-admin/includes/file.php';
    }
    if (!function_exists('get_core_updates')) {
        require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
    }
}

/**
 * Build the full status payload: versions + available updates + auto-update state.
 */
function wpupdater_collect_status() {
    wpupdater_load_update_apis();

    // Force-refresh update transients so the dashboard sees current data.
    wp_version_check(array(), true);
    wp_update_plugins();
    wp_update_themes();

    global $wp_version;

    // ---- Core ----
    $core_update = null;
    $core_updates = function_exists('get_core_updates') ? get_core_updates() : array();
    if (!empty($core_updates) && isset($core_updates[0]) && isset($core_updates[0]->response)
        && $core_updates[0]->response === 'upgrade') {
        $core_update = array(
            'current'   => $wp_version,
            'available' => isset($core_updates[0]->version) ? $core_updates[0]->version : null,
        );
    }

    // ---- Auto-update enabled lists ----
    $auto_plugins = (array) get_site_option('auto_update_plugins', array());
    $auto_themes  = (array) get_site_option('auto_update_themes', array());

    // ---- Plugins ----
    $all_plugins = get_plugins();
    $plugin_updates = get_plugin_updates(); // keyed by plugin file
    $plugins = array();
    foreach ($all_plugins as $file => $data) {
        $has_update = isset($plugin_updates[$file]);
        $plugins[] = array(
            'file'           => $file,
            'name'           => isset($data['Name']) ? $data['Name'] : $file,
            'current'        => isset($data['Version']) ? $data['Version'] : '',
            'available'      => $has_update && isset($plugin_updates[$file]->update->new_version)
                                  ? $plugin_updates[$file]->update->new_version : null,
            'update'         => $has_update,
            'active'         => is_plugin_active($file),
            'auto_update'    => in_array($file, $auto_plugins, true),
        );
    }

    // ---- Themes ----
    $theme_updates = get_theme_updates(); // keyed by stylesheet
    $themes = array();
    foreach (wp_get_themes() as $stylesheet => $theme) {
        $has_update = isset($theme_updates[$stylesheet]);
        $themes[] = array(
            'stylesheet'  => $stylesheet,
            'name'        => $theme->get('Name'),
            'current'     => $theme->get('Version'),
            'available'   => $has_update && isset($theme_updates[$stylesheet]->update['new_version'])
                               ? $theme_updates[$stylesheet]->update['new_version'] : null,
            'update'      => $has_update,
            'auto_update' => in_array($stylesheet, $auto_themes, true),
        );
    }

    $plugin_update_count = count(array_filter($plugins, function ($p) { return $p['update']; }));
    $theme_update_count  = count(array_filter($themes, function ($t) { return $t['update']; }));

    return array(
        'connector_version' => WPUPDATER_VERSION,
        'site_url'          => home_url(),
        'name'              => get_bloginfo('name'),
        'wp_version'        => $wp_version,
        'php_version'       => PHP_VERSION,
        'is_multisite'      => is_multisite(),
        'core_auto_update'  => wpupdater_core_auto_update_state(),
        'core_update'       => $core_update,
        'counts'            => array(
            'core'    => $core_update ? 1 : 0,
            'plugins' => $plugin_update_count,
            'themes'  => $theme_update_count,
            'total'   => ($core_update ? 1 : 0) + $plugin_update_count + $theme_update_count,
        ),
        'plugins'           => $plugins,
        'themes'            => $themes,
        'admin_email'       => get_bloginfo('admin_email'),
        'checked_at'        => gmdate('c'),
    );
}

/**
 * Best-effort read of the core auto-update policy.
 */
function wpupdater_core_auto_update_state() {
    // 'minor' updates are on by default. Major auto-updates are controlled by a filter/constant.
    $major = apply_filters('allow_major_auto_core_updates', false);
    if (defined('WP_AUTO_UPDATE_CORE')) {
        return WP_AUTO_UPDATE_CORE === true ? 'all' : (string) WP_AUTO_UPDATE_CORE;
    }
    return $major ? 'all' : 'minor';
}

/**
 * Enable/disable auto-updates for all plugins and themes (and optionally core major).
 *
 * @param bool $enable
 */
function wpupdater_set_auto_updates($enable) {
    wpupdater_load_update_apis();

    if ($enable) {
        $plugin_files = array_keys(get_plugins());
        $theme_slugs  = array_keys(wp_get_themes());
        update_site_option('auto_update_plugins', array_values($plugin_files));
        update_site_option('auto_update_themes', array_values($theme_slugs));
    } else {
        update_site_option('auto_update_plugins', array());
        update_site_option('auto_update_themes', array());
    }
    return array(
        'auto_update' => (bool) $enable,
        'plugins'     => count((array) get_site_option('auto_update_plugins', array())),
        'themes'      => count((array) get_site_option('auto_update_themes', array())),
    );
}

/**
 * Apply updates on request. $targets controls scope.
 * Returns a per-item result list. Runs synchronously.
 *
 * Hardened so a single failing item (or a core package that is incompatible
 * with the running PHP) cannot bring down the whole request as an opaque
 * "critical error" 500. Each step is isolated and any PHP error/exception is
 * captured and reported back as a normal JSON result.
 */
function wpupdater_apply_updates($targets, $only_plugins = array(), $only_themes = array()) {
    wpupdater_load_update_apis();
    if (!class_exists('Plugin_Upgrader')) {
        require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
    }
    if (!class_exists('Automatic_Upgrader_Skin')) {
        require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader-skin.php';
    }
    if (!function_exists('request_filesystem_credentials')) {
        require_once ABSPATH . 'wp-admin/includes/file.php';
    }

    // Give long upgrades room to breathe.
    @set_time_limit(0);
    if (function_exists('wp_raise_memory_limit')) {
        wp_raise_memory_limit('admin');
    }

    // Force the direct filesystem method; without credentials a non-direct
    // host would otherwise make every upgrade silently return false.
    if (!defined('FS_METHOD')) {
        define('FS_METHOD', 'direct');
    }
    if (function_exists('WP_Filesystem')) {
        WP_Filesystem();
    }

    $results = array('plugins' => array(), 'themes' => array(), 'core' => null, 'errors' => array());
    $skin = new Automatic_Upgrader_Skin();

    // Refresh data first.
    wp_update_plugins();
    wp_update_themes();
    wp_version_check(array(), true);

    $do_plugins = empty($targets) || in_array('plugins', $targets, true);
    $do_themes  = empty($targets) || in_array('themes', $targets, true);
    $do_core    = empty($targets) || in_array('core', $targets, true);

    // When the dashboard requests specific plugin/theme items, restrict the run
    // to exactly those items and skip the other groups (and core).
    $only_plugins = array_filter((array) $only_plugins);
    $only_themes  = array_filter((array) $only_themes);
    $has_specific = !empty($only_plugins) || !empty($only_themes);
    if ($has_specific) {
        $do_plugins = !empty($only_plugins);
        $do_themes  = !empty($only_themes);
        $do_core    = false;
    }

    if ($do_plugins) {
        try {
            $plugin_updates = get_plugin_updates();
            if (!empty($only_plugins)) {
                $files = array_values(array_intersect(array_keys($plugin_updates), $only_plugins));
            } else {
                $files = array_keys($plugin_updates);
            }
            if (!empty($files)) {
                $upgrader = new Plugin_Upgrader($skin);
                $res = $upgrader->bulk_upgrade($files);
                foreach ((array) $res as $file => $ok) {
                    $results['plugins'][] = array(
                        'file'    => $file,
                        'success' => !is_wp_error($ok) && $ok !== false && $ok !== null,
                        'message' => is_wp_error($ok) ? $ok->get_error_message() : null,
                    );
                }
            }
        } catch (\Throwable $e) {
            $results['errors'][] = 'plugins: ' . $e->getMessage();
        }
    }

    if ($do_themes) {
        try {
            $theme_updates = get_theme_updates();
            if (!empty($only_themes)) {
                $slugs = array_values(array_intersect(array_keys($theme_updates), $only_themes));
            } else {
                $slugs = array_keys($theme_updates);
            }
            if (!empty($slugs)) {
                $upgrader = new Theme_Upgrader($skin);
                $res = $upgrader->bulk_upgrade($slugs);
                foreach ((array) $res as $slug => $ok) {
                    $results['themes'][] = array(
                        'stylesheet' => $slug,
                        'success'    => !is_wp_error($ok) && $ok !== false && $ok !== null,
                        'message'    => is_wp_error($ok) ? $ok->get_error_message() : null,
                    );
                }
            }
        } catch (\Throwable $e) {
            $results['errors'][] = 'themes: ' . $e->getMessage();
        }
    }

    if ($do_core) {
        try {
            $core_updates = get_core_updates();
            if (!empty($core_updates) && isset($core_updates[0]->response) && $core_updates[0]->response === 'upgrade') {
                $offer = $core_updates[0];
                // Refuse a core upgrade whose package requires a newer PHP than
                // this server runs, which would otherwise brick the site.
                $required_php = isset($offer->php_version) ? $offer->php_version : null;
                if ($required_php && version_compare(PHP_VERSION, $required_php, '<')) {
                    $results['core'] = array(
                        'success' => false,
                        'message' => sprintf(
                            'Skipped: WordPress %s requires PHP %s but this server runs PHP %s.',
                            isset($offer->version) ? $offer->version : '?',
                            $required_php,
                            PHP_VERSION
                        ),
                    );
                } else {
                    $upgrader = new Core_Upgrader($skin);
                    $ok = $upgrader->upgrade($offer);
                    $results['core'] = array(
                        'success' => !is_wp_error($ok) && $ok !== false,
                        'message' => is_wp_error($ok) ? $ok->get_error_message() : null,
                    );
                }
            }
        } catch (\Throwable $e) {
            $results['errors'][] = 'core: ' . $e->getMessage();
        }
    }

    // Never leave the site stuck behind a leftover maintenance flag.
    $maintenance = ABSPATH . '.maintenance';
    if (file_exists($maintenance)) {
        @unlink($maintenance);
    }

    return $results;
}

/**
 * Register the four REST routes on a given namespace.
 */
function wpupdater_register_routes($namespace) {
    register_rest_route($namespace, '/ping', array(
        'methods'             => 'GET',
        'permission_callback' => 'wpupdater_check_auth',
        'callback'            => function () {
            return new WP_REST_Response(array(
                'ok'                => true,
                'connector_version' => WPUPDATER_VERSION,
                'site_url'          => home_url(),
            ), 200);
        },
    ));

    register_rest_route($namespace, '/status', array(
        'methods'             => 'GET',
        'permission_callback' => 'wpupdater_check_auth',
        'callback'            => function () {
            return new WP_REST_Response(wpupdater_collect_status(), 200);
        },
    ));

    register_rest_route($namespace, '/auto-updates', array(
        'methods'             => 'POST',
        'permission_callback' => 'wpupdater_check_auth',
        'callback'            => function (WP_REST_Request $request) {
            $enable = filter_var($request->get_param('enable'), FILTER_VALIDATE_BOOLEAN);
            return new WP_REST_Response(wpupdater_set_auto_updates($enable), 200);
        },
    ));

    register_rest_route($namespace, '/update', array(
        'methods'             => 'POST',
        'permission_callback' => 'wpupdater_check_auth',
        'callback'            => function (WP_REST_Request $request) {
            $targets = $request->get_param('targets');
            if (is_string($targets)) {
                $targets = array_filter(array_map('trim', explode(',', $targets)));
            }
            if (!is_array($targets)) {
                $targets = array();
            }
            $only_plugins = $request->get_param('plugins');
            if (is_string($only_plugins)) {
                $only_plugins = array_filter(array_map('trim', explode(',', $only_plugins)));
            }
            if (!is_array($only_plugins)) {
                $only_plugins = array();
            }
            $only_themes = $request->get_param('themes');
            if (is_string($only_themes)) {
                $only_themes = array_filter(array_map('trim', explode(',', $only_themes)));
            }
            if (!is_array($only_themes)) {
                $only_themes = array();
            }
            try {
                $results = wpupdater_apply_updates($targets, $only_plugins, $only_themes);
            } catch (\Throwable $e) {
                return new WP_REST_Response(array(
                    'applied' => array('plugins' => array(), 'themes' => array(), 'core' => null,
                                       'errors'  => array('fatal: ' . $e->getMessage())),
                    'status'  => null,
                    'error'   => $e->getMessage(),
                ), 200);
            }
            // Collect the post-update status, but never let a problem here turn
            // a successful update into an opaque 500.
            $status = null;
            $status_error = null;
            try {
                $status = wpupdater_collect_status();
            } catch (\Throwable $e) {
                $status_error = $e->getMessage();
            }
            return new WP_REST_Response(array(
                'applied'      => $results,
                'status'       => $status,
                'status_error' => $status_error,
            ), 200);
        },
    ));
}

/**
 * Register REST routes on both the current and legacy namespaces.
 */
add_action('rest_api_init', function () {
    wpupdater_register_routes('wpupdater/v1');
    wpupdater_register_routes('wpmonitor/v1');
});

/**
 * Admin settings page so the operator can read/rotate the API key.
 */
add_action('admin_menu', function () {
    add_options_page(
        'WP Updater',
        'WP Updater',
        'manage_options',
        'wp-updater',
        'wpupdater_render_settings_page'
    );
});

function wpupdater_render_settings_page() {
    if (!current_user_can('manage_options')) {
        return;
    }

    // Rotate key on request (only when key is option-based, not constant).
    if (isset($_POST['wpupdater_rotate']) && check_admin_referer('wpupdater_rotate_key')) {
        if ((defined('WPUPDATER_API_KEY') && WPUPDATER_API_KEY) || (defined('WPMONITOR_API_KEY') && WPMONITOR_API_KEY)) {
            echo '<div class="notice notice-warning"><p>Key is fixed by the WPUPDATER_API_KEY constant in wp-config.php and cannot be rotated here.</p></div>';
        } else {
            update_option('wpupdater_api_key', bin2hex(random_bytes(32)), false);
            echo '<div class="notice notice-success"><p>API key rotated. Update it in the dashboard.</p></div>';
        }
    }

    $key      = wpupdater_get_api_key();
    $rest_url = rest_url('wpupdater/v1/status');
    $fixed    = (defined('WPUPDATER_API_KEY') && WPUPDATER_API_KEY) || (defined('WPMONITOR_API_KEY') && WPMONITOR_API_KEY);
    ?>
    <div class="wrap">
        <h1>WP Updater Connector</h1>
        <p>Paste these two values into your WP Updater dashboard when adding this site.</p>
        <table class="form-table" role="presentation">
            <tr>
                <th scope="row">Site URL</th>
                <td><code><?php echo esc_html(home_url()); ?></code></td>
            </tr>
            <tr>
                <th scope="row">REST endpoint</th>
                <td><code><?php echo esc_html($rest_url); ?></code></td>
            </tr>
            <tr>
                <th scope="row">API key</th>
                <td>
                    <code style="user-select:all;"><?php echo esc_html($key); ?></code>
                    <?php if ($fixed) : ?>
                        <p class="description">Defined by the <code>WPUPDATER_API_KEY</code> constant in wp-config.php.</p>
                    <?php endif; ?>
                </td>
            </tr>
        </table>
        <?php if (!$fixed) : ?>
        <form method="post">
            <?php wp_nonce_field('wpupdater_rotate_key'); ?>
            <p>
                <button type="submit" name="wpupdater_rotate" value="1" class="button button-secondary"
                        onclick="return confirm('Rotate the API key? The dashboard will need the new key.');">
                    Rotate API key
                </button>
            </p>
        </form>
        <?php endif; ?>
    </div>
    <?php
}
