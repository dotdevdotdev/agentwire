/**
 * ListWindow - Reusable list-based window component
 *
 * Creates WinBox windows with scrollable lists, customizable item rendering,
 * action handlers, and optional auto-refresh.
 */

export class ListWindow {
    /**
     * @param {Object} options
     * @param {string} options.id - Unique window identifier
     * @param {string} options.title - Window title
     * @param {string} [options.icon] - Icon URL (defaults to favicon)
     * @param {Function} options.fetchData - Async function returning array of items
     * @param {Function} options.renderItem - Function(item) returning HTML string
     * @param {Function} [options.onItemAction] - Handler for item actions: function(action, item, event)
     * @param {number} [options.refreshInterval=0] - Auto-refresh interval in ms (0 = disabled)
     * @param {string} [options.emptyMessage='No items'] - Message when list is empty
     * @param {HTMLElement} [options.root] - Root element for WinBox (defaults to document body)
     * @param {number} [options.width=400] - Window width
     * @param {number} [options.height=500] - Window height
     * @param {number} [options.x] - Window X position
     * @param {number} [options.y] - Window Y position
     */
    constructor(options) {
        this.id = options.id;
        this.title = options.title;
        this.icon = options.icon || '/static/favicon-green.jpeg';
        this.fetchData = options.fetchData;
        this.renderItem = options.renderItem;
        this.onItemAction = options.onItemAction || (() => {});
        this.refreshInterval = options.refreshInterval || 0;
        this.emptyMessage = options.emptyMessage || 'No items';
        this.root = options.root || document.body;
        this.width = options.width || 400;
        this.height = options.height || 500;
        this.x = options.x;
        this.y = options.y;

        this.winbox = null;
        this.container = null;
        this.contentEl = null;
        this.refreshTimer = null;
        this.isLoading = false;
    }

    /**
     * Open the window and load initial data
     * @returns {WinBox} The WinBox instance
     */
    open() {
        // Don't create duplicate windows
        if (this.winbox) {
            this.winbox.focus();
            return this.winbox;
        }

        // Create container structure
        this.container = document.createElement('div');
        this.container.className = 'list-window';
        this.container.innerHTML = `
            <div class="list-header">
                <span class="list-title">${this.title}</span>
                <button class="list-refresh-btn" title="Refresh">↻</button>
            </div>
            <div class="list-content">
                <div class="list-loading">Loading...</div>
            </div>
        `;

        this.contentEl = this.container.querySelector('.list-content');

        // Attach refresh button handler
        const refreshBtn = this.container.querySelector('.list-refresh-btn');
        refreshBtn.addEventListener('click', () => this.refresh());

        // Calculate position (cascade if not specified)
        const existingWindows = document.querySelectorAll('.winbox').length;
        const offset = existingWindows * 30;
        const x = this.x ?? (100 + offset);
        const y = this.y ?? (80 + offset);

        // Create WinBox
        this.winbox = new WinBox({
            title: this.title,
            icon: this.icon,
            mount: this.container,
            root: this.root,
            x: x,
            y: y,
            width: this.width,
            height: this.height,
            minwidth: 300,
            minheight: 200,
            class: ['list-window-box'],
            onclose: () => this._onClose(),
        });

        // Initial data fetch
        this.refresh();

        // Start auto-refresh if configured
        if (this.refreshInterval > 0) {
            this.refreshTimer = setInterval(() => this.refresh(), this.refreshInterval);
        }

        return this.winbox;
    }

    /**
     * Close the window and clean up
     */
    close() {
        if (this.winbox) {
            this.winbox.close();
        }
    }

    /**
     * Refresh the list data
     */
    async refresh() {
        if (this.isLoading || !this.contentEl) return;

        this.isLoading = true;
        this._showLoading();

        try {
            const items = await this.fetchData();
            this._render(items);
        } catch (error) {
            console.error(`ListWindow[${this.id}] fetch error:`, error);
            this._showError('Failed to load data');
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * Render items into the list
     * @param {Array} items
     */
    _render(items) {
        if (!this.contentEl) return;

        if (!items || items.length === 0) {
            this._showEmpty();
            return;
        }

        // Build list HTML
        const html = items.map((item, index) => {
            const itemHtml = this.renderItem(item, index);
            return `<div class="list-item" data-index="${index}">${itemHtml}</div>`;
        }).join('');

        this.contentEl.innerHTML = html;

        // Attach action handlers to buttons with data-action
        this.contentEl.querySelectorAll('[data-action]').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                const action = el.dataset.action;
                const itemEl = el.closest('.list-item');
                const index = parseInt(itemEl?.dataset.index, 10);
                const item = items[index];
                if (item) {
                    this.onItemAction(action, item, e);
                }
            });
        });

        // Attach click handler to list items themselves
        this.contentEl.querySelectorAll('.list-item').forEach((itemEl, index) => {
            itemEl.addEventListener('click', (e) => {
                // Only fire if click wasn't on a button/action element
                if (!e.target.closest('[data-action]')) {
                    const item = items[index];
                    if (item) {
                        this.onItemAction('select', item, e);
                    }
                }
            });
        });
    }

    /**
     * Show loading state
     */
    _showLoading() {
        if (this.contentEl) {
            this.contentEl.innerHTML = '<div class="list-loading">Loading...</div>';
        }
    }

    /**
     * Show empty state
     */
    _showEmpty() {
        if (this.contentEl) {
            this.contentEl.innerHTML = `<div class="list-empty">${this.emptyMessage}</div>`;
        }
    }

    /**
     * Show error state
     * @param {string} message
     */
    _showError(message) {
        if (this.contentEl) {
            this.contentEl.innerHTML = `<div class="list-error">${message}</div>`;
        }
    }

    /**
     * Handle window close
     */
    _onClose() {
        // Stop refresh timer
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }

        // Clean up references
        this.winbox = null;
        this.container = null;
        this.contentEl = null;
    }
}
