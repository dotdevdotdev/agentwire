/**
 * Projects Window - displays all projects with type, path, and machine info
 */

import { ListWindow } from '../list-window.js';

/** @type {ListWindow|null} */
let projectsWindow = null;

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
        width: 500,
        fetchData: fetchProjects,
        renderItem: renderProjectItem,
        onItemAction: handleProjectAction,
        emptyMessage: 'No projects found'
    });

    projectsWindow._cleanup = () => {
        projectsWindow = null;
    };

    projectsWindow.open();
    return projectsWindow;
}

/**
 * Fetch projects from API
 * API returns {projects: [{name, path, type, roles, machine}, ...]}
 * @returns {Promise<Array>} Array of project objects, grouped by machine if multiple
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
 * Truncate path for display
 * @param {string} path - Full path
 * @param {number} maxLen - Max length before truncation
 * @returns {string} Truncated path with ellipsis if needed
 */
function truncatePath(path, maxLen = 40) {
    if (!path || path.length <= maxLen) return path || '';
    // Keep the end of the path (most relevant part)
    return '...' + path.slice(-(maxLen - 3));
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

    const typeClass = project.type === 'agentwire' ? 'type-agentwire' : 'type-worker';
    const truncatedPath = truncatePath(project.path);

    return `
        <div class="project-info">
            <span class="project-name">${project.name}</span>
            <span class="project-type ${typeClass}">${project.type || 'agentwire'}</span>
        </div>
        <div class="project-details">
            <span class="project-path" title="${project.path || ''}">${truncatedPath}</span>
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
        // For now, just log selection. Future: could open session creation dialog
        console.log('[Projects] Selected:', item.name, item.path);
    }
}
