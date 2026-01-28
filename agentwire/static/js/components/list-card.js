/**
 * ListCard - Reusable card component for list windows
 *
 * Outputs the exact same HTML structure as the original sessions list card.
 * All lists (sessions, projects, machines) use this for consistent appearance.
 */

/**
 * Get inner HTML for activity indicator based on state
 * @param {string} state - Activity state: 'idle' | 'processing' | 'generating' | 'playing'
 * @returns {string} Inner HTML
 */
export function getActivityIndicatorHtml(state) {
    switch (state) {
        case 'processing':
            return '<div class="spinner"></div>';
        case 'generating':
            return '<div class="generating-dots"><span></span><span></span><span></span></div>';
        case 'playing':
            return '<div class="audio-wave"><span></span><span></span><span></span><span></span><span></span></div>';
        default:  // idle
            return '<div class="stop-icon"></div>';
    }
}

/**
 * Render a list card with the session card structure
 *
 * @param {Object} options
 * @param {string} options.id - Item identifier (used in data-session-name)
 * @param {string} options.iconUrl - Icon image URL
 * @param {boolean} [options.iconEditable=true] - Show icon edit button
 * @param {string} [options.activityState] - Activity state: 'idle'|'processing'|'generating'|'playing' (omit for no indicator)
 * @param {boolean} [options.statusOnline] - Show status dot: true=online (green), false=offline (gray), undefined=hidden
 * @param {string} options.name - Primary display name
 * @param {string} [options.machineTag] - Machine name to show as yellow tag after name (e.g. "@dotdev-gpu")
 * @param {number} [options.clientCount=0] - Attached client count for presence indicator
 * @param {string} [options.meta] - Meta HTML content (already formatted with spans)
 * @param {Array} [options.actions] - Action buttons [{label, action, primary?, danger?, title?}]
 *
 * @returns {string} HTML string
 */
export function ListCard(options) {
    const {
        id,
        iconUrl,
        iconEditable = true,
        activityState = null,
        statusOnline = undefined,
        name,
        machineTag = null,
        clientCount = 0,
        meta = '',
        actions = []
    } = options;

    // Icon edit button
    const editBtnHtml = iconEditable
        ? '<button class="icon-edit-btn" data-action="edit-icon" title="Change icon">⚙</button>'
        : '';

    // Activity indicator (only if activityState provided)
    let badgeHtml = '';
    if (activityState !== null) {
        badgeHtml = `<div class="session-activity-indicator ${activityState}" data-session="${escapeAttr(id)}">
               ${getActivityIndicatorHtml(activityState)}
           </div>`;
    } else if (statusOnline !== undefined) {
        // Status dot (online/offline)
        const statusClass = statusOnline ? 'online' : 'offline';
        badgeHtml = `<span class="session-status-dot ${statusClass}"></span>`;
    }

    // Machine tag (yellow, after name)
    const machineTagHtml = machineTag
        ? `<span class="session-machine">${escapeHtml(machineTag)}</span>`
        : '';

    // Presence indicator
    const presenceHtml = clientCount > 0
        ? `<span class="presence-indicator" title="${clientCount} client${clientCount !== 1 ? 's' : ''} attached">
               <span class="presence-icon">👤</span>
               <span class="presence-count">${clientCount}</span>
           </span>`
        : '';

    // Meta line
    const metaHtml = meta ? `<div class="session-meta">${meta}</div>` : '';

    // Actions
    const actionsHtml = actions.length > 0
        ? `<div class="session-actions">${actions.map(a => {
              const classes = ['btn', 'btn-small'];
              if (a.primary) classes.push('btn-primary');
              if (a.danger) classes.push('danger');
              const titleAttr = a.title ? ` title="${escapeAttr(a.title)}"` : '';

              // Support combo buttons (main + chevron dropdown)
              if (a.combo) {
                  const comboTitleAttr = a.combo.title ? ` title="${escapeAttr(a.combo.title)}"` : '';
                  return `<div class="combo-btn combo-btn-small">
                      <button class="${classes.join(' ')}" data-action="${a.action}"${titleAttr}>${a.label}</button>
                      <button class="${classes.join(' ')} combo-btn-chevron" data-action="${a.combo.action}"${comboTitleAttr}>${a.combo.label || '▾'}</button>
                  </div>`;
              }

              return `<button class="${classes.join(' ')}" data-action="${a.action}"${titleAttr}>${a.label}</button>`;
          }).join('')}</div>`
        : '';

    return `
        <div class="session-card" data-session-name="${escapeAttr(id)}">
            <div class="session-card-top">
                <div class="session-icon-wrapper">
                    ${editBtnHtml}
                    <img src="${escapeAttr(iconUrl)}" alt="" class="session-icon" />
                    ${badgeHtml}
                </div>
                <div class="session-content">
                    <div class="session-header">
                        <span class="session-name" data-session="${escapeAttr(id)}">${escapeHtml(name)}</span>
                        ${machineTagHtml}
                        ${presenceHtml}
                    </div>
                    ${metaHtml}
                </div>
            </div>
            ${actionsHtml}
        </div>
    `;
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

/**
 * Escape attribute value
 * @param {string} str
 * @returns {string}
 */
function escapeAttr(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;');
}
