/**
 * Machines Window - displays all registered machines with status
 */

import { ListWindow } from '../list-window.js';

/**
 * Open the Machines window
 * @returns {ListWindow} The machines window instance
 */
export function openMachinesWindow() {
    const win = new ListWindow({
        id: 'machines',
        title: 'Machines',
        fetchData: fetchMachines,
        renderItem: renderMachineItem,
        onItemAction: null,  // Display only for now
        refreshInterval: 10000,
        emptyMessage: 'No machines configured'
    });

    win.open();
    return win;
}

/**
 * Fetch machines from API
 * API returns array: [{id, host, local, status}, ...]
 * @returns {Promise<Array>} Array of machine objects
 */
async function fetchMachines() {
    const response = await fetch('/api/machines');
    const machines = await response.json();
    return Array.isArray(machines) ? machines : [];
}

/**
 * Render a single machine item
 * @param {Object} machine - Machine data {id, host, local, status}
 * @returns {string} HTML string for the machine item
 */
function renderMachineItem(machine) {
    const isOnline = machine.status === 'online';
    const statusClass = isOnline ? 'connected' : 'disconnected';
    const statusText = isOnline ? '● Connected' : '○ Disconnected';
    const localTag = machine.local ? '<span class="machine-local">local</span>' : '';

    return `
        <div class="machine-info">
            <span class="machine-name">${machine.id}</span>
            ${localTag}
            <span class="machine-status ${statusClass}">${statusText}</span>
        </div>
        <div class="machine-details">
            <span class="machine-host">${machine.host || 'localhost'}</span>
        </div>
    `;
}
