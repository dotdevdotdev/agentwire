/**
 * Projects Window - displays discovered projects with drill-down detail view
 */

import { ListWindow } from '../list-window.js';
import { projectIcons } from '../icon-manager.js';
import { IconPicker } from '../components/icon-picker.js';
import { ListCard } from '../components/list-card.js';

/** @type {IconPicker|null} */
let iconPicker = null;

/** @type {ListWindow|null} */
let projectsWindow = null;

/** @type {Object|null} */
let selectedProject = null;

/** @type {Array|null} */
let cachedProjects = null;

/**
 * Format timestamp as relative time
 * @param {number} timestampMs - Unix timestamp in milliseconds
 * @returns {string} Relative time string
 */
function formatRelativeTime(timestampMs) {
    const seconds = Math.floor((Date.now() - timestampMs) / 1000);
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

/**
 * Format timestamp for display
 * @param {number|string} timestamp - Unix timestamp (ms) or ISO string
 * @returns {string} Formatted date/time
 */
function formatTimestamp(timestamp) {
    const date = typeof timestamp === 'number' ? new Date(timestamp) : new Date(timestamp);
    return date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Truncate text to max length with ellipsis
 * @param {string} text - Text to truncate
 * @param {number} maxLen - Maximum length
 * @returns {string} Truncated text
 */
function truncateText(text, maxLen = 60) {
    if (!text || text.length <= maxLen) return text || '';
    return text.substring(0, maxLen - 3) + '...';
}

/**
 * Show toast notification
 * @param {string} message - Toast message
 * @param {'success'|'error'} type - Toast type
 */
function showToast(message, type = 'success') {
    // Remove existing toast if any
    const existing = document.querySelector('.toast-notification');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => toast.classList.add('show'));

    // Auto-dismiss
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/**
 * Open the Projects window
 * @returns {ListWindow} The projects window instance
 */
export function openProjectsWindow() {
    if (projectsWindow?.winbox) {
        projectsWindow.winbox.focus();
        return projectsWindow;
    }

    projectsWindow = new ListWindow({
        id: 'projects',
        title: 'Projects',
        fetchData: fetchProjects,
        renderItem: renderProjectItem,
        onItemAction: handleProjectAction,
        emptyMessage: 'No projects found'
    });

    projectsWindow._cleanup = () => {
        projectsWindow = null;
        selectedProject = null;
        cachedProjects = null;
    };

    // Add styles
    addProjectsStyles();

    projectsWindow.open();
    return projectsWindow;
}

/**
 * Fetch projects from API
 * Groups by machine if multiple machines are present
 * @returns {Promise<Array>} Array of project objects, with group headers if needed
 */
async function fetchProjects() {
    const response = await fetch('/api/projects');
    const data = await response.json();
    const projects = data.projects || [];

    // Sort alphabetically
    projects.sort((a, b) => a.name.localeCompare(b.name));

    // Get icons using IconManager (persistent, name-matched or random)
    const projectNames = projects.map(p => p.name);
    const iconUrls = await projectIcons.getIconsForItems(projectNames);
    projects.forEach((p) => {
        p.iconUrl = iconUrls[p.name];
    });

    // Cache for detail view
    cachedProjects = projects;

    // Check if there are multiple machines
    const machines = new Set(projects.map(p => p.machine || 'local'));
    const hasMultipleMachines = machines.size > 1;

    if (!hasMultipleMachines) {
        return projects;
    }

    // Group by machine and flatten with group headers
    const grouped = {};
    for (const project of projects) {
        const machine = project.machine || 'local';
        if (!grouped[machine]) {
            grouped[machine] = [];
        }
        grouped[machine].push(project);
    }

    // Flatten with markers for group headers
    const result = [];
    for (const [machine, machineProjects] of Object.entries(grouped)) {
        result.push({ _groupHeader: true, machine });
        result.push(...machineProjects);
    }
    return result;
}

/**
 * Format path for display - show abbreviated version
 * @param {string|null} path - Full path
 * @returns {string} Formatted path
 */
function formatPath(path) {
    if (!path) return '';

    // Replace home directory with ~ (detect common patterns)
    const homeMatch = path.match(/^(\/Users\/[^/]+|\/home\/[^/]+|\/root)/);
    if (homeMatch) {
        return '~' + path.slice(homeMatch[1].length);
    }

    return path;
}

/**
 * Render a single project item or group header
 * @param {Object} project - Project data {name, path, type, roles, machine} or {_groupHeader, machine}
 * @returns {string} HTML string for the project item
 */
function renderProjectItem(project) {
    // Render group header
    if (project._groupHeader) {
        return `
            <div class="project-group-header">
                <span class="machine-icon">&#128421;</span>
                <span class="machine-name">${project.machine}</span>
            </div>
        `;
    }

    const pathDisplay = formatPath(project.path);

    // Build meta with path and type
    const metaParts = [];
    if (project.type && project.type !== 'bare') {
        metaParts.push(`<span class="session-type">${project.type}</span>`);
    }
    if (pathDisplay) {
        metaParts.push(`<span class="session-path">${pathDisplay}</span>`);
    }

    return ListCard({
        id: project.name,
        iconUrl: project.iconUrl,
        name: project.name,
        meta: metaParts.join(' · ')
        // No actions - clicking opens detail view
    });
}

/**
 * Handle action on project items
 * @param {string} action - The action type ('select', 'edit-icon')
 * @param {Object} item - The project data object
 */
function handleProjectAction(action, item) {
    // Skip group headers
    if (item._groupHeader) return;

    if (action === 'select') {
        selectedProject = item;
        showDetailView(item);
    } else if (action === 'edit-icon') {
        openIconPicker(item.name);
    }
}

/**
 * Open the icon picker for a project
 * @param {string} projectName - Project name
 */
function openIconPicker(projectName) {
    if (!iconPicker) {
        iconPicker = new IconPicker(projectIcons);
    }
    iconPicker.show(projectName, () => {
        // Refresh the list after icon change
        projectsWindow?.refresh();
    });
}

/**
 * Show the detail view for a project
 * @param {Object} project - Project data
 */
function showDetailView(project) {
    const container = projectsWindow?.container;
    if (!container) return;

    const rolesBadges = (project.roles || [])
        .map(role => `<span class="role-badge">${role}</span>`)
        .join('') || '<span class="no-roles">No roles assigned</span>';

    const typeClass = `type-${project.type || 'claude-bypass'}`;

    // Check if this is a Claude session type (has history)
    const sessionType = project.type || 'claude-bypass';
    const hasHistory = sessionType.startsWith('claude-');

    container.innerHTML = `
        <div class="project-detail-view">
            <div class="detail-header">
                <button class="back-btn">← Back</button>
                <span class="detail-machine">${project.machine}</span>
            </div>

            <div class="detail-body">
                <div class="detail-title-row">
                    <h2 class="detail-name">${project.name}</h2>
                    <span class="project-type ${typeClass}">${project.type || 'claude-bypass'}</span>
                </div>

                <div class="detail-section">
                    <label>Path</label>
                    <div class="detail-path">${project.path}</div>
                </div>

                <div class="detail-section">
                    <label>Roles</label>
                    <div class="detail-roles">${rolesBadges}</div>
                </div>

                <div class="detail-actions">
                    <button class="btn primary new-session-btn">New Session</button>
                </div>

                ${hasHistory ? `
                <div class="detail-section history-section">
                    <label>History</label>
                    <div class="history-list">
                        <div class="history-loading">Loading...</div>
                    </div>
                </div>
                ` : ''}
            </div>
        </div>
    `;

    // Attach handlers
    container.querySelector('.back-btn')?.addEventListener('click', showListView);
    container.querySelector('.new-session-btn')?.addEventListener('click', () => openNewSessionForProject(project));

    // Fetch history if applicable
    if (hasHistory) {
        fetchProjectHistory(project);
    }
}

/**
 * Fetch and render history for a project
 * @param {Object} project - Project data
 */
async function fetchProjectHistory(project) {
    const historyList = projectsWindow?.container?.querySelector('.history-list');
    if (!historyList) return;

    try {
        const params = new URLSearchParams({
            project: project.path,
            machine: project.machine || 'local',
            limit: '10'
        });

        const response = await fetch(`/api/history?${params}`);
        const data = await response.json();

        if (data.error) {
            historyList.innerHTML = `<div class="history-empty">${data.error}</div>`;
            return;
        }

        const history = data.history || [];
        if (history.length === 0) {
            historyList.innerHTML = '<div class="history-empty">No conversation history</div>';
            return;
        }

        historyList.innerHTML = history.map(entry => `
            <div class="history-item" data-session-id="${entry.sessionId}" data-machine="${project.machine || 'local'}">
                <div class="history-item-header">
                    <span class="history-id">${entry.sessionId.substring(0, 8)}</span>
                    <span class="history-time">${formatRelativeTime(entry.timestamp)}</span>
                </div>
                <div class="history-summary">${truncateText(entry.lastSummary || entry.firstMessage || 'No summary', 80)}</div>
                <div class="history-meta">${entry.messageCount || 0} message${entry.messageCount !== 1 ? 's' : ''}</div>
            </div>
        `).join('');

        // Attach click handlers to history items
        historyList.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', () => {
                const sessionId = item.dataset.sessionId;
                const machine = item.dataset.machine;
                showHistoryDetailModal(sessionId, machine, project);
            });
        });

    } catch (err) {
        console.error('[Projects] Failed to fetch history:', err);
        historyList.innerHTML = '<div class="history-empty">Failed to load history</div>';
    }
}

/**
 * Show history detail modal for a conversation
 * @param {string} sessionId - Session ID
 * @param {string} machine - Machine ID
 * @param {Object} project - Project data
 */
async function showHistoryDetailModal(sessionId, machine, project) {
    // Create modal overlay
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.innerHTML = `
        <div class="modal-content history-modal">
            <div class="modal-header">
                <h2>Conversation Details</h2>
                <button class="modal-close">&times;</button>
            </div>
            <div class="modal-body">
                <div class="history-detail-loading">Loading...</div>
            </div>
            <div class="modal-footer">
                <button class="btn" data-action="close">Close</button>
                <button class="btn btn-primary" data-action="resume">Resume</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Close handlers
    const closeModal = () => modal.remove();
    modal.querySelector('.modal-close')?.addEventListener('click', closeModal);
    modal.querySelector('[data-action="close"]')?.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    // Resume handler
    modal.querySelector('[data-action="resume"]')?.addEventListener('click', async () => {
        await resumeSession(sessionId, project);
        closeModal();
    });

    // Fetch detail
    try {
        const params = new URLSearchParams({ machine });
        const response = await fetch(`/api/history/${sessionId}?${params}`);
        const data = await response.json();

        if (data.error) {
            modal.querySelector('.modal-body').innerHTML = `
                <div class="history-detail-error">${data.error}</div>
            `;
            return;
        }

        // Render detail
        const summaries = data.summaries || [];
        const summariesHtml = summaries.length > 0
            ? summaries.map((s, i) => `
                <div class="summary-item">
                    <span class="summary-index">${i + 1}</span>
                    <span class="summary-text">${s}</span>
                </div>
            `).join('')
            : '<div class="no-summaries">No summaries available</div>';

        modal.querySelector('.modal-body').innerHTML = `
            <div class="history-detail">
                <div class="detail-row">
                    <label>Session ID</label>
                    <div class="session-id-copyable" title="Click to copy">
                        <code>${data.sessionId}</code>
                        <button class="copy-btn" data-copy="${data.sessionId}">Copy</button>
                    </div>
                </div>

                ${data.timestamps?.start ? `
                <div class="detail-row">
                    <label>Started</label>
                    <span>${formatTimestamp(data.timestamps.start)}</span>
                </div>
                ` : ''}

                ${data.timestamps?.end ? `
                <div class="detail-row">
                    <label>Last Activity</label>
                    <span>${formatTimestamp(data.timestamps.end)}</span>
                </div>
                ` : ''}

                ${data.gitBranch ? `
                <div class="detail-row">
                    <label>Git Branch</label>
                    <code class="git-branch">${data.gitBranch}</code>
                </div>
                ` : ''}

                <div class="detail-row">
                    <label>Messages</label>
                    <span>${data.messageCount || 0}</span>
                </div>

                ${data.firstMessage ? `
                <div class="detail-section">
                    <label>First Message</label>
                    <div class="first-message">${truncateText(data.firstMessage, 200)}</div>
                </div>
                ` : ''}

                <div class="detail-section">
                    <label>Summaries</label>
                    <div class="summaries-timeline">
                        ${summariesHtml}
                    </div>
                </div>
            </div>
        `;

        // Copy button handler
        modal.querySelector('.copy-btn')?.addEventListener('click', (e) => {
            const text = e.target.dataset.copy;
            navigator.clipboard.writeText(text).then(() => {
                e.target.textContent = 'Copied!';
                setTimeout(() => e.target.textContent = 'Copy', 2000);
            });
        });

    } catch (err) {
        console.error('[Projects] Failed to fetch history detail:', err);
        modal.querySelector('.modal-body').innerHTML = `
            <div class="history-detail-error">Failed to load conversation details</div>
        `;
    }
}

/**
 * Resume a session from history
 * @param {string} sessionId - Session ID to resume
 * @param {Object} project - Project data
 */
async function resumeSession(sessionId, project) {
    try {
        const response = await fetch(`/api/history/${sessionId}/resume`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                projectPath: project.path,
                machine: project.machine || 'local'
            })
        });

        const data = await response.json();

        if (data.error) {
            showToast(`Failed to resume: ${data.error}`, 'error');
            return;
        }

        showToast(`Session resumed: ${data.session}`, 'success');

        // Refresh sessions list to show new session
        import('../desktop-manager.js').then(module => {
            module.desktop?.fetchSessions?.();
        });

    } catch (err) {
        console.error('[Projects] Failed to resume session:', err);
        showToast('Failed to resume session', 'error');
    }
}

/**
 * Return to the list view
 */
function showListView() {
    if (!projectsWindow) return;

    const container = projectsWindow.container;
    if (!container) return;

    // Rebuild the list structure that was replaced by detail view
    container.innerHTML = `
        <div class="list-header">
            <span class="list-title">Projects</span>
            <button class="list-refresh-btn" title="Refresh">↻</button>
        </div>
        <div class="list-content">
            <div class="list-loading">Loading...</div>
        </div>
    `;

    // Re-attach contentEl reference
    projectsWindow.contentEl = container.querySelector('.list-content');

    // Re-attach refresh button handler
    const refreshBtn = container.querySelector('.list-refresh-btn');
    refreshBtn.addEventListener('click', () => projectsWindow.refresh());

    // Fetch and render data
    projectsWindow.refresh();
}

/**
 * Open new session modal pre-filled with project info
 * @param {Object} project - Project data
 */
function openNewSessionForProject(project) {
    // Import desktop.js to check for openNewSessionModal
    import('../desktop.js').then(async (desktop) => {
        if (desktop.openNewSessionModal) {
            desktop.openNewSessionModal({
                name: project.name,
                path: project.path,
                machine: project.machine,
                type: project.type,
                roles: project.roles
            });
        } else {
            // Fallback: create session directly via API
            const sessionName = prompt(`Create new session for ${project.name}:`, project.name);
            if (!sessionName) return;

            try {
                const response = await fetch('/api/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: sessionName,
                        path: project.path,
                        machine: project.machine,
                        type: project.type
                    })
                });

                const result = await response.json();
                if (result.error) {
                    alert(`Failed to create session: ${result.error}`);
                } else {
                    // Refresh sessions list
                    import('../desktop-manager.js').then(module => {
                        module.desktop?.fetchSessions?.();
                    });
                }
            } catch (err) {
                alert(`Failed to create session: ${err.message}`);
            }
        }
    });
}

/**
 * Add CSS styles for projects window (group headers and detail view)
 */
function addProjectsStyles() {
    if (document.getElementById('projects-window-styles')) return;

    const style = document.createElement('style');
    style.id = 'projects-window-styles';
    style.textContent = `
        /* Group headers */
        .project-group-header {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 4px 0;
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .project-group-header .machine-icon {
            font-size: 14px;
        }

        .list-item:has(.project-group-header) {
            background: var(--chrome);
            cursor: default;
            border-bottom: none;
        }

        .list-item:has(.project-group-header):hover {
            background: var(--chrome);
        }

        /* Detail view */
        .project-detail-view {
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        .detail-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            border-bottom: 1px solid var(--chrome-border);
            background: var(--chrome);
        }

        .back-btn {
            background: none;
            border: none;
            color: var(--accent);
            cursor: pointer;
            font-size: 13px;
            padding: 4px 8px;
            border-radius: 4px;
        }

        .back-btn:hover {
            background: var(--hover);
        }

        .detail-machine {
            font-size: 11px;
            padding: 2px 8px;
            background: var(--background);
            border-radius: 3px;
            color: var(--text-muted);
        }

        .detail-body {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }

        .detail-title-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--chrome-border);
        }

        .detail-name {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
            color: var(--text);
        }

        .detail-section {
            margin-bottom: 16px;
        }

        .detail-section label {
            display: block;
            font-size: 10px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }

        .detail-path {
            font-size: 12px;
            color: var(--text);
            word-break: break-all;
            font-family: 'Menlo', 'Monaco', monospace;
            background: var(--background);
            padding: 8px 10px;
            border-radius: 4px;
        }

        .detail-roles {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }

        .role-badge {
            font-size: 11px;
            padding: 4px 10px;
            background: rgba(74, 222, 128, 0.15);
            color: var(--accent);
            border-radius: 4px;
        }

        .no-roles {
            font-size: 12px;
            color: var(--text-muted);
            font-style: italic;
        }

        .detail-actions {
            margin: 20px 0;
        }

        .detail-actions .btn {
            width: 100%;
            padding: 10px;
            font-size: 13px;
        }

        .history-section {
            margin-top: 20px;
            padding-top: 16px;
            border-top: 1px solid var(--chrome-border);
        }

        /* History list */
        .history-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .history-loading,
        .history-empty {
            font-size: 12px;
            color: var(--text-muted);
            font-style: italic;
            padding: 12px;
            background: var(--background);
            border-radius: 4px;
            text-align: center;
        }

        .history-item {
            padding: 10px 12px;
            background: var(--background);
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.15s;
        }

        .history-item:hover {
            background: var(--hover);
        }

        .history-item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }

        .history-id {
            font-family: 'Menlo', 'Monaco', monospace;
            font-size: 11px;
            color: var(--accent);
            font-weight: 500;
        }

        .history-time {
            font-size: 10px;
            color: var(--text-muted);
        }

        .history-summary {
            font-size: 12px;
            color: var(--text);
            line-height: 1.4;
            margin-bottom: 4px;
        }

        .history-meta {
            font-size: 10px;
            color: var(--text-muted);
        }

        /* History detail modal */
        .history-modal {
            max-width: 500px;
            max-height: 80vh;
        }

        .history-modal .modal-body {
            overflow-y: auto;
            max-height: 50vh;
        }

        .history-detail-loading,
        .history-detail-error {
            padding: 20px;
            text-align: center;
            color: var(--text-muted);
        }

        .history-detail-error {
            color: var(--error);
        }

        .history-detail .detail-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid var(--chrome-border);
        }

        .history-detail .detail-row label {
            font-size: 11px;
            font-weight: 500;
            color: var(--text-muted);
            margin-bottom: 0;
        }

        .history-detail .detail-row span,
        .history-detail .detail-row code {
            font-size: 12px;
            color: var(--text);
        }

        .session-id-copyable {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .session-id-copyable code {
            font-family: 'Menlo', 'Monaco', monospace;
            font-size: 11px;
            background: var(--background);
            padding: 2px 6px;
            border-radius: 3px;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .copy-btn {
            padding: 2px 8px;
            font-size: 10px;
            background: var(--chrome);
            border: 1px solid var(--chrome-border);
            border-radius: 3px;
            color: var(--text-muted);
            cursor: pointer;
        }

        .copy-btn:hover {
            background: var(--hover);
            color: var(--text);
        }

        .git-branch {
            font-family: 'Menlo', 'Monaco', monospace;
            font-size: 11px;
            background: rgba(74, 222, 128, 0.1);
            padding: 2px 6px;
            border-radius: 3px;
            color: var(--accent);
        }

        .history-detail .detail-section {
            margin-top: 12px;
        }

        .history-detail .detail-section label {
            display: block;
            font-size: 10px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }

        .first-message {
            font-size: 12px;
            color: var(--text);
            background: var(--background);
            padding: 10px;
            border-radius: 4px;
            line-height: 1.4;
        }

        .summaries-timeline {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .summary-item {
            display: flex;
            gap: 10px;
            padding: 8px 10px;
            background: var(--background);
            border-radius: 4px;
        }

        .summary-index {
            flex-shrink: 0;
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--chrome);
            border-radius: 50%;
            font-size: 10px;
            font-weight: 600;
            color: var(--text-muted);
        }

        .summary-text {
            font-size: 12px;
            color: var(--text);
            line-height: 1.4;
        }

        .no-summaries {
            font-size: 12px;
            color: var(--text-muted);
            font-style: italic;
            padding: 10px;
            background: var(--background);
            border-radius: 4px;
        }

        /* Toast notification */
        .toast-notification {
            position: fixed;
            bottom: 60px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: var(--chrome);
            border: 1px solid var(--chrome-border);
            border-radius: 6px;
            padding: 12px 20px;
            font-size: 13px;
            color: var(--text);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            z-index: 3000;
            opacity: 0;
            transition: transform 0.3s ease, opacity 0.3s ease;
        }

        .toast-notification.show {
            transform: translateX(-50%) translateY(0);
            opacity: 1;
        }

        .toast-notification.toast-success {
            border-left: 3px solid var(--accent);
        }

        .toast-notification.toast-error {
            border-left: 3px solid var(--error);
        }
    `;
    document.head.appendChild(style);
}
