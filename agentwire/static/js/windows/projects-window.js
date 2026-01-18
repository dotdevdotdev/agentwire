/**
 * Projects Window - displays discovered projects with detail panel
 */

import { ListWindow } from '../list-window.js';

/** @type {ListWindow|null} */
let projectsWindow = null;

/** @type {Object|null} */
let selectedProject = null;

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
        width: 700,
        height: 500,
        fetchData: fetchProjects,
        renderItem: renderProjectItem,
        onItemAction: handleProjectAction,
        emptyMessage: 'No projects found'
    });

    projectsWindow._cleanup = () => {
        projectsWindow = null;
        selectedProject = null;
    };

    // Override the container creation to add detail panel
    const originalOpen = projectsWindow.open.bind(projectsWindow);
    projectsWindow.open = function() {
        const winbox = originalOpen();

        // Restructure: wrap list-content in a two-column layout
        const container = this.container;
        const listContent = container.querySelector('.list-content');

        // Create wrapper for split view
        const splitView = document.createElement('div');
        splitView.className = 'projects-split-view';

        // Wrap list in left panel
        const leftPanel = document.createElement('div');
        leftPanel.className = 'projects-list-panel';
        listContent.parentNode.insertBefore(splitView, listContent);
        leftPanel.appendChild(listContent);

        // Create detail panel
        const detailPanel = document.createElement('div');
        detailPanel.className = 'projects-detail-panel';
        detailPanel.innerHTML = `
            <div class="detail-empty">
                Select a project to view details
            </div>
        `;

        splitView.appendChild(leftPanel);
        splitView.appendChild(detailPanel);

        // Add styles for split view
        addProjectsStyles();

        return winbox;
    };

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

    const machineLabel = project.machine === 'local' ? '' : `<span class="project-machine">${project.machine}</span>`;
    const typeClass = `type-${project.type || 'claude-bypass'}`;

    return `
        <div class="project-info" data-path="${project.path}" data-machine="${project.machine}">
            <div class="project-header">
                <span class="project-name">${project.name}</span>
                ${machineLabel}
            </div>
            <div class="project-meta">
                <span class="project-type ${typeClass}">${project.type || 'claude-bypass'}</span>
                <span class="project-path">${project.path}</span>
            </div>
        </div>
    `;
}

/**
 * Handle action on project items
 * @param {string} action - The action type ('select')
 * @param {Object} item - The project data object
 */
function handleProjectAction(action, item) {
    // Skip group headers
    if (item._groupHeader) return;

    if (action === 'select') {
        selectedProject = item;
        updateDetailPanel(item);

        // Highlight selected row
        const container = projectsWindow.container;
        container.querySelectorAll('.list-item').forEach(el => {
            el.classList.remove('selected');
        });
        const selected = container.querySelector(`[data-path="${item.path}"][data-machine="${item.machine}"]`);
        if (selected) {
            selected.closest('.list-item').classList.add('selected');
        }
    }
}

/**
 * Update the detail panel with project info
 * @param {Object} project - Project data
 */
function updateDetailPanel(project) {
    const container = projectsWindow?.container;
    if (!container) return;

    const detailPanel = container.querySelector('.projects-detail-panel');
    if (!detailPanel) return;

    const rolesBadges = (project.roles || [])
        .map(role => `<span class="role-badge">${role}</span>`)
        .join('') || '<span class="no-roles">No roles</span>';

    detailPanel.innerHTML = `
        <div class="detail-content">
            <div class="detail-header">
                <h3 class="detail-name">${project.name}</h3>
                <span class="detail-machine">${project.machine}</span>
            </div>

            <div class="detail-section">
                <label>Path</label>
                <div class="detail-path">${project.path}</div>
            </div>

            <div class="detail-section">
                <label>Type</label>
                <div class="detail-type">${project.type || 'claude-bypass'}</div>
            </div>

            <div class="detail-section">
                <label>Roles</label>
                <div class="detail-roles">${rolesBadges}</div>
            </div>

            <div class="detail-actions">
                <button class="btn primary new-session-btn">New Session</button>
            </div>

            <div class="detail-section history-section">
                <label>History</label>
                <div class="history-placeholder">
                    History available in future update
                </div>
            </div>
        </div>
    `;

    // Attach new session handler
    const newSessionBtn = detailPanel.querySelector('.new-session-btn');
    newSessionBtn?.addEventListener('click', () => openNewSessionForProject(project));
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
                    desktop.desktop?.fetchSessions?.();
                }
            } catch (err) {
                alert(`Failed to create session: ${err.message}`);
            }
        }
    });
}

/**
 * Add CSS styles for projects window
 */
function addProjectsStyles() {
    if (document.getElementById('projects-window-styles')) return;

    const style = document.createElement('style');
    style.id = 'projects-window-styles';
    style.textContent = `
        /* Split view layout */
        .projects-split-view {
            display: flex;
            flex: 1;
            min-height: 0;
            overflow: hidden;
        }

        .projects-list-panel {
            flex: 1;
            min-width: 250px;
            border-right: 1px solid var(--chrome-border);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .projects-list-panel .list-content {
            flex: 1;
            overflow-y: auto;
        }

        .projects-detail-panel {
            width: 280px;
            flex-shrink: 0;
            overflow-y: auto;
            background: var(--chrome);
        }

        /* Project list item */
        .project-info {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .project-header {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .project-name {
            font-weight: 500;
            color: var(--text);
        }

        .project-machine {
            font-size: 10px;
            padding: 2px 6px;
            background: var(--chrome);
            border-radius: 3px;
            color: var(--text-muted);
        }

        .project-meta {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 11px;
        }

        .project-type {
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            text-transform: uppercase;
        }

        .project-type.type-claude-bypass {
            background: rgba(74, 222, 128, 0.15);
            color: var(--accent);
        }

        .project-type.type-claude-prompted {
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
        }

        .project-type.type-claude-restricted {
            background: rgba(248, 81, 73, 0.15);
            color: var(--error);
        }

        .project-path {
            color: var(--text-muted);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

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

        /* Selected state */
        .list-item.selected {
            background: var(--hover);
            border-left: 2px solid var(--accent);
        }

        /* Detail panel */
        .detail-empty {
            padding: 24px;
            text-align: center;
            color: var(--text-muted);
            font-size: 13px;
        }

        .detail-content {
            padding: 16px;
        }

        .detail-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--chrome-border);
        }

        .detail-name {
            margin: 0;
            font-size: 16px;
            font-weight: 600;
            color: var(--text);
        }

        .detail-machine {
            font-size: 11px;
            padding: 2px 8px;
            background: var(--background);
            border-radius: 3px;
            color: var(--text-muted);
        }

        .detail-section {
            margin-bottom: 14px;
        }

        .detail-section label {
            display: block;
            font-size: 10px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }

        .detail-path {
            font-size: 12px;
            color: var(--text);
            word-break: break-all;
            font-family: 'Menlo', 'Monaco', monospace;
            background: var(--background);
            padding: 6px 8px;
            border-radius: 4px;
        }

        .detail-type {
            font-size: 12px;
            color: var(--text);
        }

        .detail-roles {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }

        .role-badge {
            font-size: 11px;
            padding: 3px 8px;
            background: rgba(74, 222, 128, 0.15);
            color: var(--accent);
            border-radius: 3px;
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

        .history-placeholder {
            font-size: 12px;
            color: var(--text-muted);
            font-style: italic;
            padding: 12px;
            background: var(--background);
            border-radius: 4px;
            text-align: center;
        }

        /* Responsive: stack on narrow */
        @media (max-width: 600px) {
            .projects-split-view {
                flex-direction: column;
            }

            .projects-list-panel {
                border-right: none;
                border-bottom: 1px solid var(--chrome-border);
                min-height: 200px;
            }

            .projects-detail-panel {
                width: 100%;
            }
        }
    `;
    document.head.appendChild(style);
}
