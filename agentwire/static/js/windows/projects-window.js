/**
 * Projects Window - displays discovered projects with drill-down detail view
 */

import { ListWindow } from '../list-window.js';

/** @type {ListWindow|null} */
let projectsWindow = null;

/** @type {Object|null} */
let selectedProject = null;

/** @type {Array|null} */
let cachedProjects = null;

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

    const typeClass = `type-${project.type || 'claude-bypass'}`;

    return `
        <div class="project-info" data-path="${project.path}" data-machine="${project.machine}">
            <div class="project-row">
                <span class="project-name">${project.name}</span>
                <span class="project-type ${typeClass}">${project.type || 'claude-bypass'}</span>
            </div>
            <div class="project-path">${project.path}</div>
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
        showDetailView(item);
    }
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

                <div class="detail-section history-section">
                    <label>History</label>
                    <div class="history-placeholder">
                        Coming soon
                    </div>
                </div>
            </div>
        </div>
    `;

    // Attach handlers
    container.querySelector('.back-btn')?.addEventListener('click', showListView);
    container.querySelector('.new-session-btn')?.addEventListener('click', () => openNewSessionForProject(project));
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
        /* Project list item */
        .project-info {
            display: flex;
            flex-direction: column;
            gap: 4px;
            width: 100%;
        }

        .project-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }

        .project-name {
            font-weight: 500;
            color: var(--text);
        }

        .project-type {
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            text-transform: uppercase;
            flex-shrink: 0;
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
            font-size: 11px;
            color: var(--text-muted);
            word-break: break-all;
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

        .history-placeholder {
            font-size: 12px;
            color: var(--text-muted);
            font-style: italic;
            padding: 12px;
            background: var(--background);
            border-radius: 4px;
            text-align: center;
        }
    `;
    document.head.appendChild(style);
}
