/**
 * TypeTag - Reusable type tag component for consistent styling
 *
 * Used for session types, project types, and other categorical tags.
 */

/**
 * Generate HTML for a type tag
 * @param {string} type - The type value (e.g., 'claude-bypass', 'bare', 'local')
 * @param {Object} [options] - Options
 * @param {string} [options.label] - Custom label (defaults to type value)
 * @returns {string} HTML string for the tag
 */
export function TypeTag(type, options = {}) {
    if (!type) return '';

    const label = options.label || type;
    const typeClass = `type-${type}`;

    return `<span class="type-tag ${typeClass}">${escapeHtml(label)}</span>`;
}

/**
 * Generate HTML for a type tag as a span with session-type class
 * (for use in meta lines where we want inline display)
 * @param {string} type - The type value
 * @returns {string} HTML string
 */
export function TypeTagInline(type) {
    if (!type) return '';
    return `<span class="type-tag type-${type}">${escapeHtml(type)}</span>`;
}

/**
 * Escape HTML special characters
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}
