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
    const rawValue = getRawValue(item.value);
    const formattedValue = formatValue(item.value);
    return `
        <div class="config-item">
            <span class="config-key">${item.key}</span>
            <span class="config-value" title="${escapeAttr(rawValue)}">${formattedValue}</span>
        </div>
    `;
}

/**
 * Get raw string value for tooltip
 * @param {any} value - The config value
 * @returns {string} Raw string representation
 */
function getRawValue(value) {
    if (value === null || value === undefined) {
        return 'not set';
    }
    if (typeof value === 'boolean') {
        return value ? 'enabled' : 'disabled';
    }
    if (typeof value === 'object') {
        return JSON.stringify(value);
    }
    return String(value);
}

/**
 * Escape string for use in HTML attribute
 * @param {string} str - The string to escape
 * @returns {string} Escaped string
 */
function escapeAttr(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
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
