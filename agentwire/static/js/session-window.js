/**
 * session-window.js
 *
 * SessionWindow class - encapsulates a terminal window for a session.
 * Wraps WinBox window, xterm.js Terminal, and WebSocket connection.
 * Supports two modes: Monitor (read-only) and Terminal (interactive).
 */


import { desktop } from './desktop-manager.js';
import { getSessionIconByName } from './windows/sessions-window.js';

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
        this.outputEl = null;  // For monitor mode
        this.fitAddon = null;
        this.ws = null;
        this.resizeObserver = null;
        this.isOpen = false;

        // PTT (Push-to-talk) state
        this.pttButton = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.pttState = 'idle'; // idle | recording | processing

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
        // Create WinBox FIRST so container is in DOM with real dimensions
        this._createWinBox(container);
        // Now create terminal - fit addon will have actual dimensions to work with
        this._createTerminal(container);
        this._connectWebSocket();
        this._setupResizeObserver(container);
        // Set up PTT button for terminal mode
        if (this.mode === 'terminal') {
            this._setupPTT(container);
        }
        // Set up reconnect button handler
        this._setupReconnectButton(container);

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

        // Clean up PTT keyboard handler
        if (this._pttKeyHandler) {
            document.removeEventListener('keydown', this._pttKeyHandler);
            document.removeEventListener('keyup', this._pttKeyHandler);
            this._pttKeyHandler = null;
        }

        // Cancel any active recording
        if (this.mediaRecorder && this.pttState === 'recording') {
            this._cancelRecording();
        }

        // Close WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        // Dispose terminal (terminal mode) or output element (monitor mode)
        if (this.terminal) {
            this.terminal.dispose();
            this.terminal = null;
        }
        this.outputEl = null;
        this.fitAddon = null;

        // Close WinBox (if not already closed)
        if (this.winbox) {
            // Prevent recursive close call
            const wb = this.winbox;
            this.winbox = null;
            wb.close();
        }

        // Unregister from desktop manager
        desktop.unregisterWindow(this.sessionId);

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
        // Avoid doubling machine suffix if session name already includes it
        if (this.machine && !this.session.endsWith(`@${this.machine}`)) {
            return `${this.session}@${this.machine}`;
        }
        return this.session;
    }

    // Private methods

    _createContainer() {
        const container = document.createElement('div');
        container.className = 'session-window-content';

        if (this.mode === 'monitor') {
            // Monitor mode: simple pre element for text output
            container.innerHTML = `
                <pre class="session-output"></pre>
                <div class="session-disconnect-overlay hidden">
                    <div class="disconnect-content">
                        <div class="disconnect-message">Session Disconnected</div>
                        <button class="btn btn-primary reconnect-btn">Reconnect</button>
                    </div>
                </div>
                <div class="session-status-bar">
                    <span class="status-indicator connecting"></span>
                    <span class="status-text">Connecting...</span>
                </div>
            `;
        } else {
            // Terminal mode: xterm.js for interactive terminal + PTT button
            container.innerHTML = `
                <div class="session-terminal"></div>
                <button class="ptt-button" title="Hold to record voice input">
                    <span class="ptt-icon">🎤</span>
                </button>
                <div class="session-disconnect-overlay hidden">
                    <div class="disconnect-content">
                        <div class="disconnect-message">Session Disconnected</div>
                        <button class="btn btn-primary reconnect-btn">Reconnect</button>
                    </div>
                </div>
                <div class="session-status-bar">
                    <span class="status-indicator connecting"></span>
                    <span class="status-text">Connecting...</span>
                </div>
            `;
        }
        return container;
    }

    _createTerminal(container) {
        if (this.mode === 'monitor') {
            // Monitor mode: just store reference to pre element
            this.outputEl = container.querySelector('.session-output');
            return;
        }

        // Terminal mode: full xterm.js setup
        const terminalEl = container.querySelector('.session-terminal');

        this.terminal = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: '"FiraMono Nerd Font Mono", Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#000',
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

        // Fit after font loads and layout is complete
        const fontFamily = '"FiraMono Nerd Font Mono", Menlo, Monaco, "Courier New", monospace';
        const fontSize = 14;

        const doInitialFit = (fontLoaded) => {
            requestAnimationFrame(() => {
                if (fontLoaded) {
                    // Force xterm to recalculate cell dimensions by re-setting font
                    // This triggers internal re-measurement with the now-loaded font
                    this.terminal.options.fontFamily = fontFamily;
                    this.terminal.options.fontSize = fontSize;
                }
                this._handleResize();
                setTimeout(() => this._handleResize(), 100);
            });
        };

        if (document.fonts && document.fonts.load) {
            // Wait for font to load, then fit
            document.fonts.load(`${fontSize}px ${fontFamily}`).then(() => {
                console.log('[SessionWindow] Font loaded, fitting terminal');
                doInitialFit(true);
            }).catch(() => {
                // Font load failed, fit anyway with fallback font
                console.warn('[SessionWindow] Font load failed, using fallback');
                doInitialFit(false);
            });
        } else {
            // Font loading API not available, use delayed fit
            doInitialFit(false);
        }
    }

    _createWinBox(container) {
        const title = `${this.sessionId} (${this.mode})`;
        const windowId = `session_${this.sessionId}_${this.mode}`;

        // Load saved position/size (null on mobile)
        const savedState = desktop.loadWindowState(windowId);
        const x = savedState?.x ?? this.position.x;
        const y = savedState?.y ?? this.position.y;
        const width = savedState?.width ?? 700;
        const height = savedState?.height ?? 500;

        this.winbox = new WinBox({
            title: title,
            icon: getSessionIconByName(this.session),
            mount: container,
            root: this.root,
            x: x,
            y: y,
            width: width,
            height: height,
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
            onmove: () => {
                this._saveWindowState(windowId);
            },
            onresize: () => {
                this._handleResize();
                this._saveWindowState(windowId);
            },
            onmaximize: () => {
                // WinBox animates maximize - wait for animation to complete
                this._handleResizeAfterAnimation();
            },
            onfullscreen: () => {
                // Browser fullscreen uses fullscreenchange event, not CSS transitions
                this._handleFullscreenResize();
            },
            onminimize: () => {
                // Optionally disconnect on minimize to save resources
                // For now, keep connection alive
            },
            onrestore: () => {
                // Restore from maximize/minimize animates
                this._handleResizeAfterAnimation();
                // Reconnect if disconnected
                if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                    this._connectWebSocket();
                }
            },
        });

        // Register with desktop manager for window management (auto-maximize on mobile, etc.)
        desktop.registerWindow(this.sessionId, this.winbox);
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
            this._hideDisconnectOverlay();

            // Send initial terminal size (both modes need it for proper display)
            this._sendResize();
        };

        this.ws.onmessage = (event) => {
            if (this.mode === 'terminal') {
                // Terminal mode: binary data or string to xterm
                // But first check for JSON messages (audio, tts_start, etc.)
                const data = event.data;

                // Check if this looks like a JSON message from the server
                if (typeof data === 'string') {
                    // Check for JSON audio/control messages
                    if (data.includes('"type"')) {
                        try {
                            const msg = JSON.parse(data);
                            console.log('[SessionWindow] JSON message received:', msg.type);

                            if (msg.type === 'audio' && msg.data) {
                                console.log('[SessionWindow] Audio received, forwarding to device');
                                desktop._playAudio(msg.data, this.sessionId);
                                return;
                            } else if (msg.type === 'tts_start') {
                                console.log('[SessionWindow] TTS starting:', msg.text);
                                return;
                            } else if (msg.type === 'session_unlocked' || msg.type === 'session_locked') {
                                return; // Ignore lock messages
                            } else if (msg.type === 'remote_session_ended') {
                                // Clean exit - tmux session ended, close window like local
                                console.log('[SessionWindow] Remote session ended cleanly:', msg.session);
                                this.close();
                                return;
                            } else if (msg.type === 'remote_disconnected') {
                                // Connection issue - show overlay for reconnect
                                console.log('[SessionWindow] Remote connection lost:', msg.session);
                                this._updateStatus('disconnected', 'Connection lost');
                                this._showDisconnectOverlay();
                                return;
                            }
                            // Other JSON messages - don't write to terminal
                            return;
                        } catch (e) {
                            console.warn('[SessionWindow] JSON parse failed:', e.message);
                            // Fall through to terminal
                        }
                    }
                }

                if (!this.terminal) return;
                if (data instanceof ArrayBuffer) {
                    this.terminal.write(new Uint8Array(data));
                } else {
                    this.terminal.write(data);
                }
            } else {
                // Monitor mode: JSON messages to pre element
                if (!this.outputEl) return;
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'audio' && msg.data) {
                        desktop._playAudio(msg.data, this.sessionId);
                    } else if (msg.type === 'output' && msg.data) {
                        // Convert ANSI to HTML and display
                        this.outputEl.innerHTML = this._ansiToHtml(msg.data);
                        this.outputEl.scrollTop = this.outputEl.scrollHeight;
                    }
                } catch (e) {
                    // Fallback: display as plain text
                    this.outputEl.textContent = event.data;
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

            // Local sessions: close window when WebSocket closes (session died)
            // Remote sessions: don't close - we detect disconnect via terminal output patterns
            if (!this.machine) {
                console.log(`[SessionWindow] Local session WebSocket closed, closing window`);
                this.close();
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

        // Only observe resize for terminal mode
        if (terminalEl) {
            this.resizeObserver = new ResizeObserver(() => {
                this._handleResize();
            });
            this.resizeObserver.observe(terminalEl);
        }
    }

    _handleResize() {
        if (this.mode === 'terminal' && this.fitAddon && this.terminal) {
            requestAnimationFrame(() => {
                try {
                    // Ensure font options are correct before fitting
                    const fontFamily = '"FiraMono Nerd Font Mono", Menlo, Monaco, "Courier New", monospace';
                    const fontSize = 14;
                    this.terminal.options.fontFamily = fontFamily;
                    this.terminal.options.fontSize = fontSize;

                    this.fitAddon.fit();
                    this._sendResize();
                } catch (e) {
                    // Terminal might not be fully initialized
                }
            });
        }
    }

    /**
     * Save window position/size to localStorage (skip on mobile).
     * @param {string} windowId - Unique window identifier
     */
    _saveWindowState(windowId) {
        if (!this.winbox || desktop.isNarrowViewport()) return;

        desktop.saveWindowState(windowId, {
            x: this.winbox.x,
            y: this.winbox.y,
            width: this.winbox.width,
            height: this.winbox.height
        });
    }

    _handleFullscreenResize() {
        // Handle browser fullscreen - uses fullscreenchange event, not CSS transitions
        if (this.mode !== 'terminal' || !this.fitAddon || !this.terminal) return;

        const doFit = () => {
            try {
                const container = this.winbox?.body?.querySelector('.session-terminal');
                console.log('[SessionWindow] Fullscreen container:', container?.offsetWidth, 'x', container?.offsetHeight);

                const fontFamily = '"FiraMono Nerd Font Mono", Menlo, Monaco, "Courier New", monospace';
                const fontSize = 14;
                this.terminal.options.fontFamily = fontFamily;
                this.terminal.options.fontSize = fontSize;
                this.fitAddon.fit();
                this._sendResize();
                console.log('[SessionWindow] Fullscreen terminal:', this.terminal.cols, 'x', this.terminal.rows);
            } catch (err) {
                console.error('[SessionWindow] Fullscreen fit error:', err);
            }
        };

        // fullscreenchange fires AFTER the browser completes the fullscreen transition
        const onFullscreenChange = () => {
            document.removeEventListener('fullscreenchange', onFullscreenChange);
            console.log('[SessionWindow] fullscreenchange fired, isFullscreen:', !!document.fullscreenElement);

            // Multiple fits with increasing delays to ensure it sticks
            setTimeout(doFit, 50);
            setTimeout(doFit, 150);
            setTimeout(doFit, 300);
        };

        document.addEventListener('fullscreenchange', onFullscreenChange);

        // Fallback: if fullscreenchange doesn't fire within 1s, force fit
        setTimeout(() => {
            document.removeEventListener('fullscreenchange', onFullscreenChange);
            console.log('[SessionWindow] Fullscreen fallback triggered');
            doFit();
            setTimeout(doFit, 200);
        }, 1000);
    }

    _handleResizeAfterAnimation() {
        // Listen for CSS transition to complete before fitting terminal
        if (this.mode !== 'terminal' || !this.fitAddon || !this.terminal || !this.winbox) return;

        const doFit = () => {
            try {
                const container = this.winbox.body.querySelector('.session-terminal');
                console.log('[SessionWindow] Container dimensions:', container?.offsetWidth, container?.offsetHeight);
                console.log('[SessionWindow] Terminal before fit:', this.terminal.cols, 'x', this.terminal.rows);

                // Ensure font options are set before fitting (in case they weren't applied correctly)
                const fontFamily = '"FiraMono Nerd Font Mono", Menlo, Monaco, "Courier New", monospace';
                const fontSize = 14;
                this.terminal.options.fontFamily = fontFamily;
                this.terminal.options.fontSize = fontSize;

                this.fitAddon.fit();
                console.log('[SessionWindow] Terminal after fit:', this.terminal.cols, 'x', this.terminal.rows);
                this._sendResize();
            } catch (err) {
                console.error('[SessionWindow] Fit error:', err);
            }
        };

        const winboxEl = this.winbox.window;
        let handled = false;

        const onTransitionEnd = (e) => {
            console.log('[SessionWindow] transitionend:', e.propertyName, e.target);
            if (e.target === winboxEl && (e.propertyName === 'width' || e.propertyName === 'height')) {
                handled = true;
                winboxEl.removeEventListener('transitionend', onTransitionEnd);
                doFit();
            }
        };

        winboxEl.addEventListener('transitionend', onTransitionEnd);

        // Fallback: if transitionend doesn't fire within 500ms, force fit
        setTimeout(() => {
            if (!handled) {
                console.log('[SessionWindow] transitionend timeout - forcing fit');
                winboxEl.removeEventListener('transitionend', onTransitionEnd);
                doFit();
            }
        }, 500);
    }

    _sendResize() {
        // Only terminal mode sends resize (monitor doesn't need it)
        if (this.mode === 'terminal' && this.ws && this.ws.readyState === WebSocket.OPEN && this.terminal) {
            const msg = {
                type: 'resize',
                cols: this.terminal.cols,
                rows: this.terminal.rows,
            };
            console.log('[SessionWindow] Sending resize:', msg);
            this.ws.send(JSON.stringify(msg));
        } else {
            console.log('[SessionWindow] Cannot send resize:', {
                mode: this.mode,
                wsExists: !!this.ws,
                wsState: this.ws?.readyState,
                terminalExists: !!this.terminal
            });
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

    _showDisconnectOverlay() {
        if (!this.winbox) return;
        const container = this.winbox.body;
        if (!container) return;

        const overlay = container.querySelector('.session-disconnect-overlay');
        if (overlay) {
            overlay.classList.remove('hidden');
        }
    }

    _hideDisconnectOverlay() {
        if (!this.winbox) return;
        const container = this.winbox.body;
        if (!container) return;

        const overlay = container.querySelector('.session-disconnect-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
        }
    }

    async _reconnect() {
        console.log(`[SessionWindow] Reconnecting to ${this.sessionId}...`);
        this._updateStatus('connecting', 'Checking session...');

        // For remote sessions, check if the session still exists before reconnecting
        if (this.machine) {
            try {
                const response = await fetch(`/api/sessions/remote`);
                const data = await response.json();
                // Flatten sessions from all machines: {machines: [{sessions: [...]}]} -> [...]
                const allSessions = (data.machines || []).flatMap(m => m.sessions || []);
                const sessionExists = allSessions.some(s =>
                    s.name === this.session && s.machine === this.machine
                );

                if (!sessionExists) {
                    console.log(`[SessionWindow] Remote session ${this.sessionId} no longer exists, closing window`);
                    this.close();
                    return;
                }
            } catch (err) {
                console.error('[SessionWindow] Failed to check session:', err);
                // Continue with reconnect attempt anyway
            }
        }

        this._hideDisconnectOverlay();
        this._updateStatus('connecting', 'Reconnecting...');

        // Close existing connection if any
        if (this.ws) {
            this.ws.onclose = null; // Prevent triggering overlay again
            this.ws.close();
            this.ws = null;
        }

        // Clear terminal to avoid escape sequence garbage on reconnect
        if (this.terminal) {
            this.terminal.clear();
        }

        // Reconnect
        this._connectWebSocket();
    }

    /**
     * Convert ANSI escape codes to HTML for monitor mode display.
     * Supports basic colors, 256-color, and true color (24-bit).
     * @param {string} text - Text with ANSI codes
     * @returns {string} HTML string
     */
    _ansiToHtml(text) {
        // Escape HTML entities first
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Basic 16 colors (standard + bright)
        const basicColors = {
            0: '#000', 1: '#cd0000', 2: '#00cd00', 3: '#cdcd00',
            4: '#0000ee', 5: '#cd00cd', 6: '#00cdcd', 7: '#e5e5e5',
            8: '#7f7f7f', 9: '#ff0000', 10: '#00ff00', 11: '#ffff00',
            12: '#5c5cff', 13: '#ff00ff', 14: '#00ffff', 15: '#ffffff'
        };

        // Convert 256-color index to hex
        const color256ToHex = (n) => {
            if (n < 16) return basicColors[n];
            if (n < 232) {
                // 216 color cube: 6x6x6
                n -= 16;
                const r = Math.floor(n / 36) * 51;
                const g = Math.floor((n % 36) / 6) * 51;
                const b = (n % 6) * 51;
                return `rgb(${r},${g},${b})`;
            }
            // Grayscale: 24 shades
            const gray = (n - 232) * 10 + 8;
            return `rgb(${gray},${gray},${gray})`;
        };

        // Track current styles
        let fg = null, bg = null, bold = false, italic = false, underline = false;

        const buildSpan = () => {
            const styles = [];
            if (fg) styles.push(`color:${fg}`);
            if (bg) styles.push(`background:${bg}`);
            if (bold) styles.push('font-weight:bold');
            if (italic) styles.push('font-style:italic');
            if (underline) styles.push('text-decoration:underline');
            return styles.length ? `<span style="${styles.join(';')}">` : '';
        };

        // Process ANSI sequences
        html = html.replace(/\x1b\[([0-9;]*)m/g, (match, codes) => {
            const parts = (codes || '0').split(';').map(Number);
            let i = 0;
            let needsNewSpan = false;

            while (i < parts.length) {
                const code = parts[i];

                if (code === 0) {
                    // Reset all
                    fg = bg = null;
                    bold = italic = underline = false;
                    needsNewSpan = true;
                } else if (code === 1) {
                    bold = true; needsNewSpan = true;
                } else if (code === 3) {
                    italic = true; needsNewSpan = true;
                } else if (code === 4) {
                    underline = true; needsNewSpan = true;
                } else if (code === 22) {
                    bold = false; needsNewSpan = true;
                } else if (code === 23) {
                    italic = false; needsNewSpan = true;
                } else if (code === 24) {
                    underline = false; needsNewSpan = true;
                } else if (code >= 30 && code <= 37) {
                    fg = basicColors[code - 30]; needsNewSpan = true;
                } else if (code >= 90 && code <= 97) {
                    fg = basicColors[code - 90 + 8]; needsNewSpan = true;
                } else if (code === 39) {
                    fg = null; needsNewSpan = true;
                } else if (code >= 40 && code <= 47) {
                    bg = basicColors[code - 40]; needsNewSpan = true;
                } else if (code >= 100 && code <= 107) {
                    bg = basicColors[code - 100 + 8]; needsNewSpan = true;
                } else if (code === 49) {
                    bg = null; needsNewSpan = true;
                } else if (code === 38 && parts[i + 1] === 5) {
                    // 256-color foreground: 38;5;N
                    fg = color256ToHex(parts[i + 2]);
                    i += 2; needsNewSpan = true;
                } else if (code === 48 && parts[i + 1] === 5) {
                    // 256-color background: 48;5;N
                    bg = color256ToHex(parts[i + 2]);
                    i += 2; needsNewSpan = true;
                } else if (code === 38 && parts[i + 1] === 2) {
                    // True color foreground: 38;2;R;G;B
                    fg = `rgb(${parts[i + 2]},${parts[i + 3]},${parts[i + 4]})`;
                    i += 4; needsNewSpan = true;
                } else if (code === 48 && parts[i + 1] === 2) {
                    // True color background: 48;2;R;G;B
                    bg = `rgb(${parts[i + 2]},${parts[i + 3]},${parts[i + 4]})`;
                    i += 4; needsNewSpan = true;
                }
                i++;
            }

            // Close previous span and open new one with current styles
            return needsNewSpan ? `</span>${buildSpan()}` : '';
        });

        // Wrap in initial span and close at end
        return `<span>${html}</span>`;
    }

    // Reconnect button handler

    _setupReconnectButton(container) {
        const reconnectBtn = container.querySelector('.reconnect-btn');
        if (reconnectBtn) {
            reconnectBtn.addEventListener('click', () => this._reconnect());
        }
    }

    // PTT (Push-to-talk) Methods

    _setupPTT(container) {
        this.pttButton = container.querySelector('.ptt-button');
        if (!this.pttButton) return;

        // Mouse events
        this.pttButton.addEventListener('mousedown', (e) => {
            e.preventDefault();
            this._startRecording();
        });
        this.pttButton.addEventListener('mouseup', () => this._stopRecording());
        this.pttButton.addEventListener('mouseleave', () => {
            if (this.pttState === 'recording') {
                this._stopRecording();
            }
        });

        // Touch events for mobile
        this.pttButton.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this._startRecording();
        });
        this.pttButton.addEventListener('touchend', () => this._stopRecording());
        this.pttButton.addEventListener('touchcancel', () => {
            if (this.pttState === 'recording') {
                this._cancelRecording();
            }
        });

        // Keyboard shortcut: Ctrl+Space to toggle recording (when window focused)
        this._pttKeyHandler = (e) => {
            // Only respond when this window is focused
            if (!this.winbox || !document.activeElement?.closest('.winbox')?.contains(container)) {
                return;
            }

            // Ctrl+Space (or Cmd+Space on Mac) to record
            if (e.code === 'Space' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                e.stopPropagation();

                if (e.type === 'keydown' && this.pttState === 'idle') {
                    this._startRecording();
                } else if (e.type === 'keyup' && this.pttState === 'recording') {
                    this._stopRecording();
                }
            }
        };

        document.addEventListener('keydown', this._pttKeyHandler);
        document.addEventListener('keyup', this._pttKeyHandler);
    }

    async _startRecording() {
        if (this.pttState !== 'idle') return;

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.audioChunks = [];

            // Use webm/opus for efficient transfer
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : 'audio/webm';

            this.mediaRecorder = new MediaRecorder(stream, { mimeType });

            this.mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    this.audioChunks.push(e.data);
                }
            };

            this.mediaRecorder.onstop = () => {
                // Stop all tracks to release microphone
                stream.getTracks().forEach(track => track.stop());

                if (this.audioChunks.length > 0 && this.pttState === 'processing') {
                    const blob = new Blob(this.audioChunks, { type: mimeType });
                    this._processRecording(blob);
                }
            };

            this.mediaRecorder.start();
            this._setPTTState('recording');
            console.log('[SessionWindow] Recording started');

        } catch (err) {
            console.error('[SessionWindow] Failed to start recording:', err);
            this._updateStatus('error', 'Microphone access denied');
            this._setPTTState('idle');
        }
    }

    _stopRecording() {
        if (this.pttState !== 'recording' || !this.mediaRecorder) return;

        this._setPTTState('processing');
        this.mediaRecorder.stop();
        console.log('[SessionWindow] Recording stopped, processing...');
    }

    _cancelRecording() {
        if (!this.mediaRecorder) return;

        this.audioChunks = [];
        this.mediaRecorder.stop();
        this._setPTTState('idle');
        console.log('[SessionWindow] Recording cancelled');
    }

    async _processRecording(blob) {
        try {
            // Step 1: Transcribe audio
            const formData = new FormData();
            formData.append('audio', blob, 'recording.webm');

            const transcribeRes = await fetch('/transcribe', {
                method: 'POST',
                body: formData,
            });

            const transcribeData = await transcribeRes.json();

            if (transcribeData.error) {
                throw new Error(transcribeData.error);
            }

            const text = transcribeData.text?.trim();
            if (!text) {
                this._updateStatus('error', 'No speech detected');
                this._setPTTState('idle');
                return;
            }

            console.log('[SessionWindow] Transcribed:', text);

            // Step 2: Send to session with voice prompt hint
            const sendRes = await fetch(`/send/${this.sessionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: `[User said: '${text}' - respond using CLI: agentwire say 'your message']`
                }),
            });

            const sendData = await sendRes.json();

            if (sendData.error) {
                throw new Error(sendData.error);
            }

            console.log('[SessionWindow] Sent to session:', this.sessionId);
            this._updateStatus('connected', `Sent: "${text.substring(0, 30)}${text.length > 30 ? '...' : ''}"`);

            // Reset status after a moment
            setTimeout(() => {
                if (this.pttState === 'idle') {
                    this._updateStatus('connected', 'Connected');
                }
            }, 3000);

        } catch (err) {
            console.error('[SessionWindow] PTT processing failed:', err);
            this._updateStatus('error', err.message || 'Voice input failed');
        } finally {
            this._setPTTState('idle');
        }
    }

    _setPTTState(state) {
        this.pttState = state;
        if (!this.pttButton) return;

        this.pttButton.classList.remove('recording', 'processing');

        switch (state) {
            case 'recording':
                this.pttButton.classList.add('recording');
                this.pttButton.querySelector('.ptt-icon').textContent = '🔴';
                break;
            case 'processing':
                this.pttButton.classList.add('processing');
                this.pttButton.querySelector('.ptt-icon').textContent = '⏳';
                break;
            default:
                this.pttButton.querySelector('.ptt-icon').textContent = '🎤';
        }
    }

}
