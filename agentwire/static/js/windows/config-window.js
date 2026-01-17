/**
 * Config Window - displays current configuration values (read-only)
 */

import { ListWindow } from '../list-window.js';

/**
 * Open the Config window
 * @returns {ListWindow} The config window instance
 */
export function openConfigWindow() {
    const win = new ListWindow({
        id: 'config',
        title: 'Configuration',
        fetchData: fetchConfig,
        renderItem: renderConfigItem,
        onItemAction: null,  // Read-only, no actions
        refreshInterval: 0,  // No auto-refresh needed
        emptyMessage: 'No configuration loaded'
    });

    win.open();
    return win;
}

/**
 * Fetch config as key/value pairs from API
 * @returns {Promise<Array>} Array of {key, value} objects
 */
async function fetchConfig() {
    const response = await fetch('/api/config?format=display');
    const data = await response.json();
    return data.items || [];
}

/**
 * Render a single config item
 * @param {Object} item - Config item with key and value
 * @returns {string} HTML string for the config item
 */
function renderConfigItem(item) {
    return `
        <div class="config-item">
            <span class="config-key">${item.key}</span>
            <span class="config-value">${formatValue(item.value)}</span>
        </div>
    `;
}

/**
 * Format a config value for display
 * @param {any} value - The config value
 * @returns {string} Formatted HTML string
 */
function formatValue(value) {
    if (value === null || value === undefined) {
        return '<span class="config-null">not set</span>';
    }
    if (typeof value === 'boolean') {
        return value
            ? '<span class="config-enabled">&#10003; enabled</span>'
            : '<span class="config-disabled">&#10007; disabled</span>';
    }
    if (typeof value === 'object') {
        return `<span class="config-object">${JSON.stringify(value)}</span>`;
    }
    return String(value);
}
