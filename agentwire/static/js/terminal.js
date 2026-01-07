/**
 * terminal.js
 *
 * Terminal Mode integration using xterm.js
 * Handles activation, WebSocket connection to tmux, error handling
 */

export class TerminalMode {
  constructor(roomName) {
    this.roomName = roomName;
    this.term = null;
    this.socket = null;
    this.fitAddon = null;
    this.isActivated = false;

    // DOM elements
    this.terminalActivation = document.getElementById('terminalActivation');
    this.terminalContainer = document.getElementById('terminal');
    this.terminalStatus = document.getElementById('terminalStatus');
    this.activateBtn = document.getElementById('activateTerminal');

    // Bind activation handler
    if (this.activateBtn) {
      this.activateBtn.addEventListener('click', () => this.activate());
    }
  }

  async activate() {
    // Detect if mobile/tablet (desktop-only feature)
    const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    if (isMobile) {
      this.showMobileMessage();
      return;
    }

    if (this.isActivated) {
      console.log('[Terminal] Already activated');
      return;
    }

    console.log('[Terminal] Activating...');
    this.isActivated = true;

    // Hide activation button, show terminal container
    if (this.terminalActivation) {
      this.terminalActivation.style.display = 'none';
    }
    if (this.terminalContainer) {
      this.terminalContainer.style.display = 'block';
    }

    // Create xterm instance with theme matching portal
    const isDark = document.body.classList.contains('dark');

    // Read CSS custom properties for theme colors
    const styles = getComputedStyle(document.documentElement);
    const bgDark = styles.getPropertyValue('--bg-dark').trim();
    const textPrimary = styles.getPropertyValue('--text-primary').trim();

    this.term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: isDark ? {
        background: bgDark || '#000',
        foreground: textPrimary || '#E8EEF2',
      } : {
        background: '#ffffff',
        foreground: '#333333',
      },
    });

    // Add fit addon for auto-resize
    this.fitAddon = new FitAddon.FitAddon();
    this.term.loadAddon(this.fitAddon);

    // Add web links addon (clickable URLs)
    this.term.loadAddon(new WebLinksAddon.WebLinksAddon());

    // Add WebGL addon for performance
    try {
      const webglAddon = new WebglAddon.WebglAddon();
      this.term.loadAddon(webglAddon);
    } catch (e) {
      console.warn('[Terminal] WebGL not available, using canvas renderer:', e);
    }

    // Attach to DOM
    this.term.open(this.terminalContainer);
    this.fitAddon.fit();

    // Show connecting status
    this.updateStatus('connecting', 'Connecting...');

    // Connect WebSocket
    await this.connect();

    // Handle window resize
    window.addEventListener('resize', () => {
      if (this.term && this.fitAddon) {
        this.fitAddon.fit();
        this.sendResize();
      }
    });
  }

  async connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws/terminal/${this.roomName}`;

    console.log('[Terminal] Connecting to', url);

    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      console.log('[Terminal] Connected');
      this.updateStatus('connected', `Connected (${this.term.cols}x${this.term.rows})`);

      // Send initial size
      this.sendResize();
    };

    this.socket.onmessage = (event) => {
      // Write tmux output to terminal
      if (this.term) {
        this.term.write(event.data);
      }
    };

    this.socket.onerror = (error) => {
      console.error('[Terminal] WebSocket error:', error);
      this.updateStatus('error', '❌ Connection failed', true);
    };

    this.socket.onclose = (event) => {
      console.log('[Terminal] WebSocket closed, code:', event.code);

      if (event.code === 1000) {
        // Normal closure
        this.updateStatus('disconnected', 'Disconnected');
      } else {
        // Abnormal closure
        this.updateStatus('error', '⚠️ Connection lost', true);
      }
    };

    // Send terminal input to WebSocket
    this.term.onData((data) => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: 'input', data }));
      }
    });

    // Add keyboard shortcuts (only active when terminal is focused)
    this.setupKeyboardShortcuts();
  }

  setupKeyboardShortcuts() {
    // Keyboard shortcuts only work when terminal tab is showing
    // These are handled at the document level but checked for terminal visibility
    this.keyboardHandler = (e) => {
      // Only handle shortcuts if terminal is activated and container is visible
      if (!this.isActivated || !this.terminalContainer || this.terminalContainer.style.display === 'none') {
        return;
      }

      // Cmd/Ctrl+K - Clear terminal
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
          // Send 'clear' command followed by Enter
          this.socket.send(JSON.stringify({ type: 'input', data: 'clear\r' }));
        }
        return;
      }

      // Cmd/Ctrl+D - Disconnect terminal
      if ((e.metaKey || e.ctrlKey) && e.key === 'd') {
        e.preventDefault();
        this.disconnect();
        return;
      }

      // Don't intercept Cmd/Ctrl+C or Cmd/Ctrl+V - let terminal handle copy/paste
    };

    document.addEventListener('keydown', this.keyboardHandler);
  }

  sendResize() {
    if (this.socket && this.socket.readyState === WebSocket.OPEN && this.term) {
      this.socket.send(JSON.stringify({
        type: 'resize',
        cols: this.term.cols,
        rows: this.term.rows,
      }));

      // Update status with new size
      this.updateStatus('connected', `Connected (${this.term.cols}x${this.term.rows})`);
    }
  }

  updateStatus(state, message, showReconnect = false) {
    if (!this.terminalStatus) return;

    const statusClasses = {
      connecting: 'terminal-status connecting',
      connected: 'terminal-status connected',
      disconnected: 'terminal-status disconnected',
      error: 'terminal-status error',
    };

    this.terminalStatus.className = statusClasses[state] || 'terminal-status';

    if (showReconnect) {
      this.terminalStatus.innerHTML = `
        ${message}
        <button class="reconnect-btn">Reconnect</button>
        <button class="close-terminal-btn">Close Terminal</button>
      `;
      this.attachReconnectHandler();
      this.attachCloseHandler();
    } else if (state === 'connected') {
      this.terminalStatus.innerHTML = `
        <span class="status-indicator ${state}"></span>
        ${message}
        <button class="close-terminal-btn">Close Terminal</button>
      `;
      this.attachCloseHandler();
    } else {
      this.terminalStatus.innerHTML = `
        <span class="status-indicator ${state}"></span>
        ${message}
      `;
    }
  }

  attachReconnectHandler() {
    const reconnectBtn = this.terminalStatus.querySelector('.reconnect-btn');
    if (reconnectBtn) {
      reconnectBtn.onclick = () => {
        console.log('[Terminal] Reconnecting...');
        this.updateStatus('connecting', 'Reconnecting...');
        this.connect();
      };
    }
  }

  attachCloseHandler() {
    const closeBtn = this.terminalStatus.querySelector('.close-terminal-btn');
    if (closeBtn) {
      closeBtn.onclick = () => {
        console.log('[Terminal] Closing terminal...');
        this.disconnect();
      };
    }
  }

  disconnect() {
    console.log('[Terminal] Disconnecting...');

    // Remove keyboard event listener
    if (this.keyboardHandler) {
      document.removeEventListener('keydown', this.keyboardHandler);
      this.keyboardHandler = null;
    }

    // Close WebSocket
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    // Dispose xterm.js instance
    if (this.term) {
      this.term.dispose();
      this.term = null;
    }

    // Reset state
    this.isActivated = false;

    // Show activation button again
    if (this.terminalActivation) {
      this.terminalActivation.style.display = 'block';
    }
    if (this.terminalContainer) {
      this.terminalContainer.style.display = 'none';
    }
    if (this.terminalStatus) {
      this.terminalStatus.innerHTML = '';
    }
  }

  showMobileMessage() {
    if (this.terminalActivation) {
      this.terminalActivation.innerHTML = `
        <div class="terminal-mobile-message">
          <p>📱 Terminal Mode is not available on mobile devices.</p>
          <p>Please use a desktop browser for full terminal access.</p>
        </div>
      `;
    }
  }

  // Called when switching away from terminal tab
  onModeSwitch() {
    // Keep terminal connected in background (don't disconnect)
    console.log('[Terminal] Switched to another mode, keeping connection alive');
  }

  // Called when switching back to terminal tab
  onModeReturn() {
    // Terminal is still connected, just show it
    console.log('[Terminal] Returned to terminal mode');
  }
}
