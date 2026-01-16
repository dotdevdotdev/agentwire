/**
 * session-window.js
 *
 * SessionWindow class - encapsulates a terminal window for a session.
 * Wraps WinBox window, xterm.js Terminal, and WebSocket connection.
 * Supports two modes: Monitor (read-only) and Terminal (interactive).
 */

export class SessionWindow {
    /**
     * @param {Object} options
     * @param {string} options.session - Session name
     * @param {'monitor'|'terminal'} options.mode - Window mode
     * @param {string|null} options.machine - Remote machine ID (optional)
     * @param {HTMLElement} options.root - Parent element for WinBox
     * @param {Object} options.position - Initial position {x, y}
     * @param {Function} options.onClose - Callback when window closes
     * @param {Function} options.onFocus - Callback when window gains focus
     */
    constructor(options) {
        this.session = options.session;
        this.mode = options.mode || 'terminal';
        this.machine = options.machine || null;
        this.root = options.root || document.body;
        this.position = options.position || { x: 50, y: 50 };
        this.onCloseCallback = options.onClose || null;
        this.onFocusCallback = options.onFocus || null;

        this.winbox = null;
        this.terminal = null;
        this.fitAddon = null;
        this.ws = null;
        this.resizeObserver = null;
        this.isOpen = false;
    }

    /**
     * Open the session window.
     * Creates WinBox, initializes terminal, connects WebSocket.
     */
    open() {
        if (this.isOpen) {
            this.focus();
            return;
        }

        const container = this._createContainer();
        this._createTerminal(container);
        this._createWinBox(container);
        this._connectWebSocket();
        this._setupResizeObserver(container);

        this.isOpen = true;
    }

    /**
     * Close the session window and clean up resources.
     */
    close() {
        if (!this.isOpen) return;

        // Clean up resize observer
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }

        // Close WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        // Dispose terminal
        if (this.terminal) {
            this.terminal.dispose();
            this.terminal = null;
        }

        this.fitAddon = null;

        // Close WinBox (if not already closed)
        if (this.winbox) {
            // Prevent recursive close call
            const wb = this.winbox;
            this.winbox = null;
            wb.close();
        }

        this.isOpen = false;

        // Callback
        if (this.onCloseCallback) {
            this.onCloseCallback(this);
        }
    }

    /**
     * Focus the window.
     */
    focus() {
        if (this.winbox) {
            this.winbox.focus();
        }
    }

    /**
     * Minimize the window.
     */
    minimize() {
        if (this.winbox) {
            this.winbox.minimize();
        }
    }

    /**
     * Restore the window from minimized state.
     */
    restore() {
        if (this.winbox) {
            this.winbox.restore();
        }
    }

    /**
     * Check if window is minimized.
     */
    get isMinimized() {
        return this.winbox ? this.winbox.min : false;
    }

    /**
     * Get the full session identifier (includes machine if remote).
     */
    get sessionId() {
        return this.machine ? `${this.session}@${this.machine}` : this.session;
    }

    // Private methods

    _createContainer() {
        const container = document.createElement('div');
        container.className = 'session-window-content';
        container.innerHTML = `
            <div class="session-terminal"></div>
            <div class="session-status-bar">
                <span class="status-indicator connecting"></span>
                <span class="status-text">Connecting...</span>
            </div>
        `;
        return container;
    }

    _createTerminal(container) {
        const terminalEl = container.querySelector('.session-terminal');

        this.terminal = new Terminal({
            cursorBlink: this.mode === 'terminal',
            disableStdin: this.mode === 'monitor',
            fontSize: 13,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#0d1117',
                foreground: '#e6edf3',
                cursor: '#2ea043',
                selection: 'rgba(46, 160, 67, 0.3)',
            },
        });

        this.fitAddon = new FitAddon.FitAddon();
        this.terminal.loadAddon(this.fitAddon);

        // Add WebGL addon for performance (optional)
        try {
            if (typeof WebglAddon !== 'undefined') {
                const webglAddon = new WebglAddon.WebglAddon();
                this.terminal.loadAddon(webglAddon);
            }
        } catch (e) {
            console.warn('[SessionWindow] WebGL not available:', e);
        }

        this.terminal.open(terminalEl);

        // Fit after a brief delay to ensure DOM is ready
        setTimeout(() => this._handleResize(), 50);
    }

    _createWinBox(container) {
        const title = `${this.sessionId} (${this.mode})`;

        this.winbox = new WinBox({
            title: title,
            icon: '/static/favicon-green.jpeg',
            mount: container,
            root: this.root,
            x: this.position.x,
            y: this.position.y,
            width: 700,
            height: 500,
            minwidth: 400,
            minheight: 300,
            class: ['session-window'],
            onclose: () => {
                // WinBox is closing, clean up our resources
                // Set winbox to null first to prevent recursive close
                this.winbox = null;
                this.close();
                return false; // Allow WinBox to proceed with close
            },
            onfocus: () => {
                if (this.onFocusCallback) {
                    this.onFocusCallback(this);
                }
            },
            onresize: () => {
                this._handleResize();
            },
            onminimize: () => {
                // Optionally disconnect on minimize to save resources
                // For now, keep connection alive
            },
            onrestore: () => {
                this._handleResize();
                // Reconnect if disconnected
                if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                    this._connectWebSocket();
                }
            },
        });
    }

    _connectWebSocket() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const sessionPath = this.sessionId;

        // Choose endpoint based on mode
        // Terminal mode: /ws/terminal/{session} - bidirectional
        // Monitor mode: /ws/{session} - output only (JSON messages)
        const endpoint = this.mode === 'terminal'
            ? `/ws/terminal/${sessionPath}`
            : `/ws/${sessionPath}`;

        const url = `${protocol}//${location.host}${endpoint}`;

        console.log(`[SessionWindow] Connecting to ${url} (${this.mode} mode)`);

        this.ws = new WebSocket(url);

        if (this.mode === 'terminal') {
            // Binary data for terminal mode
            this.ws.binaryType = 'arraybuffer';
        }

        this.ws.onopen = () => {
            console.log(`[SessionWindow] Connected: ${this.sessionId}`);
            this._updateStatus('connected', 'Connected');

            if (this.mode === 'terminal') {
                // Send initial terminal size
                this._sendResize();
            }
        };

        this.ws.onmessage = (event) => {
            if (!this.terminal) return;

            if (this.mode === 'terminal') {
                // Terminal mode: binary data or string
                if (event.data instanceof ArrayBuffer) {
                    this.terminal.write(new Uint8Array(event.data));
                } else {
                    this.terminal.write(event.data);
                }
            } else {
                // Monitor mode: JSON messages from output endpoint
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'output' && msg.data) {
                        this.terminal.write(msg.data);
                    }
                } catch (e) {
                    // Fallback: write as plain text
                    this.terminal.write(event.data);
                }
            }
        };

        this.ws.onerror = (error) => {
            console.error(`[SessionWindow] WebSocket error:`, error);
            this._updateStatus('error', 'Connection error');
        };

        this.ws.onclose = (event) => {
            console.log(`[SessionWindow] WebSocket closed: ${event.code}`);
            if (event.code === 1000) {
                this._updateStatus('disconnected', 'Disconnected');
            } else {
                this._updateStatus('error', 'Connection lost');
            }
        };

        // For terminal mode, send input to WebSocket
        if (this.mode === 'terminal' && this.terminal) {
            this.terminal.onData((data) => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({ type: 'input', data }));
                }
            });
        }
    }

    _setupResizeObserver(container) {
        const terminalEl = container.querySelector('.session-terminal');
        if (!terminalEl) return;

        this.resizeObserver = new ResizeObserver(() => {
            this._handleResize();
        });
        this.resizeObserver.observe(terminalEl);
    }

    _handleResize() {
        if (this.fitAddon && this.terminal) {
            try {
                this.fitAddon.fit();
                if (this.mode === 'terminal') {
                    this._sendResize();
                }
            } catch (e) {
                // Terminal might not be fully initialized
            }
        }
    }

    _sendResize() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN && this.terminal) {
            this.ws.send(JSON.stringify({
                type: 'resize',
                cols: this.terminal.cols,
                rows: this.terminal.rows,
            }));
        }
    }

    _updateStatus(state, message) {
        if (!this.winbox) return;

        const container = this.winbox.body;
        if (!container) return;

        const statusBar = container.querySelector('.session-status-bar');
        if (!statusBar) return;

        const indicator = statusBar.querySelector('.status-indicator');
        const text = statusBar.querySelector('.status-text');

        if (indicator) {
            indicator.className = `status-indicator ${state}`;
        }
        if (text) {
            text.textContent = message;
        }
    }
}
