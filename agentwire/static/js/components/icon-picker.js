/**
 * IconPicker - Modal component for selecting icons
 *
 * Usage:
 *   const picker = new IconPicker(iconManager);
 *   picker.show(itemName, (newIconFilename) => {
 *     // Handle selection
 *     refreshList();
 *   });
 */

export class IconPicker {
    /**
     * @param {import('../icon-manager.js').IconManager} iconManager
     */
    constructor(iconManager) {
        this.iconManager = iconManager;
        this.modal = null;
        this.currentItem = null;
        this.onSelect = null;
    }

    /**
     * Show the icon picker modal
     * @param {string} itemName - Item to change icon for
     * @param {Function} onSelect - Callback when icon selected (receives iconFilename)
     */
    async show(itemName, onSelect) {
        this.currentItem = itemName;
        this.onSelect = onSelect;

        // Create modal if not exists
        if (!this.modal) {
            this._createModal();
        }

        // Show modal with loading state
        this.modal.classList.add('visible');
        this.modal.querySelector('.icon-picker-title').textContent = `Select icon for "${itemName}"`;

        // Populate icons (async)
        await this._populateIcons();
    }

    /**
     * Hide the icon picker modal
     */
    hide() {
        if (this.modal) {
            this.modal.classList.remove('visible');
        }
        this.currentItem = null;
        this.onSelect = null;
    }

    /**
     * Create the modal DOM element
     */
    _createModal() {
        this.modal = document.createElement('div');
        this.modal.className = 'icon-picker-modal';
        this.modal.innerHTML = `
            <div class="icon-picker-content">
                <div class="icon-picker-header">
                    <span class="icon-picker-title">Select Icon</span>
                    <button class="icon-picker-close" title="Close">&times;</button>
                </div>
                <div class="icon-picker-grid"></div>
            </div>
        `;

        // Close button handler
        this.modal.querySelector('.icon-picker-close').addEventListener('click', () => {
            this.hide();
        });

        // Click outside to close
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.hide();
            }
        });

        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('visible')) {
                this.hide();
            }
        });

        document.body.appendChild(this.modal);
    }

    /**
     * Populate the icon grid
     */
    async _populateIcons() {
        const grid = this.modal.querySelector('.icon-picker-grid');
        grid.innerHTML = '<div class="icon-picker-loading">Loading icons...</div>';

        const icons = await this.iconManager.getAvailableIcons(this.currentItem);

        grid.innerHTML = icons.map(icon => `
            <button class="icon-option ${icon.isAssigned ? 'selected' : ''}"
                    data-filename="${icon.filename}"
                    title="${icon.filename.replace(/\.[^.]+$/, '')}">
                <img src="${icon.url}" alt="${icon.filename}" />
            </button>
        `).join('');

        // Add click handlers
        grid.querySelectorAll('.icon-option').forEach(btn => {
            btn.addEventListener('click', () => {
                const filename = btn.dataset.filename;
                this._selectIcon(filename);
            });
        });
    }

    /**
     * Handle icon selection
     * @param {string} filename - Selected icon filename
     */
    _selectIcon(filename) {
        // Update assignment
        this.iconManager.setIcon(this.currentItem, filename);

        // Callback
        if (this.onSelect) {
            this.onSelect(filename);
        }

        // Close modal
        this.hide();
    }
}
