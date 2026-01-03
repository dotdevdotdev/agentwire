/**
 * Output View Component - Terminal text output handling
 *
 * Manages the text output display area for terminal mode.
 */

// Element references
let outputElement = null;
let contentElement = null;

/**
 * Initialize the output view with DOM element references
 * @param {HTMLElement} output - The output container element
 * @param {HTMLElement} content - The content element inside output
 */
export function init(output, content) {
    outputElement = output;
    contentElement = content;
}

/**
 * Set the output content (replaces existing content)
 * @param {string} html - HTML content to display
 */
export function setContent(html) {
    if (contentElement) {
        contentElement.innerHTML = html;
        scrollToBottom();
    }
}

/**
 * Append text to the output
 * @param {string} html - HTML content to append
 */
export function append(html) {
    if (contentElement) {
        contentElement.innerHTML += html;
        scrollToBottom();
    }
}

/**
 * Clear all output content
 */
export function clear() {
    if (contentElement) {
        contentElement.innerHTML = '';
    }
}

/**
 * Scroll the output view to the bottom
 */
export function scrollToBottom() {
    if (outputElement) {
        outputElement.scrollTop = outputElement.scrollHeight;
    }
}

/**
 * Show the output view (terminal mode)
 */
export function show() {
    if (outputElement) {
        outputElement.classList.remove('hidden');
        outputElement.classList.remove('ambient-default');
        scrollToBottom();
    }
}

/**
 * Hide the output view (ambient mode)
 */
export function hide() {
    if (outputElement) {
        outputElement.classList.add('hidden');
    }
}

/**
 * Check if the output view is visible
 * @returns {boolean}
 */
export function isVisible() {
    return outputElement && !outputElement.classList.contains('hidden');
}

/**
 * Convert ANSI escape codes to HTML
 * @param {string} text - Text with ANSI codes
 * @returns {string} HTML string
 */
export function ansiToHtml(text) {
    const colors = {
        '30': '#000', '31': '#e55', '32': '#5e5', '33': '#ee5',
        '34': '#55e', '35': '#e5e', '36': '#5ee', '37': '#eee',
        '90': '#888', '91': '#f88', '92': '#8f8', '93': '#ff8',
        '94': '#88f', '95': '#f8f', '96': '#8ff', '97': '#fff',
        '39': '#aaa'
    };
    const bgColors = {
        '40': '#000', '41': '#a00', '42': '#0a0', '43': '#a50',
        '44': '#00a', '45': '#a0a', '46': '#0aa', '47': '#aaa',
        '49': 'transparent'
    };

    let html = '';
    let currentStyle = {};
    const regex = /\x1b\[([0-9;]*)m/g;
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            const chunk = text.slice(lastIndex, match.index);
            html += escapeHtml(chunk);
        }

        const codes = match[1].split(';').filter(c => c !== '');
        for (const code of codes) {
            if (code === '0' || code === '') {
                currentStyle = {};
            } else if (code === '1') {
                currentStyle.bold = true;
            } else if (code === '2') {
                currentStyle.dim = true;
            } else if (code === '3') {
                currentStyle.italic = true;
            } else if (code === '4') {
                currentStyle.underline = true;
            } else if (colors[code]) {
                currentStyle.color = colors[code];
            } else if (bgColors[code]) {
                currentStyle.bg = bgColors[code];
            }
        }

        html += '</span>';
        const styles = [];
        if (currentStyle.color) styles.push(`color:${currentStyle.color}`);
        if (currentStyle.bg && currentStyle.bg !== 'transparent') styles.push(`background:${currentStyle.bg}`);
        if (currentStyle.bold) styles.push('font-weight:bold');
        if (currentStyle.dim) styles.push('opacity:0.6');
        if (currentStyle.italic) styles.push('font-style:italic');
        if (currentStyle.underline) styles.push('text-decoration:underline');
        html += `<span style="${styles.join(';')}">`;

        lastIndex = match.index + match[0].length;
    }

    if (lastIndex < text.length) {
        html += escapeHtml(text.slice(lastIndex));
    }

    return '<span>' + html + '</span>';
}

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
