/**
 * Chat Window - Voice chat with orb visualization
 *
 * Provides a conversational voice interface to Claude Code sessions.
 * Features:
 * - Orb visualization showing voice states (idle, listening, processing, speaking)
 * - Session selector dropdown
 * - Push-to-talk button
 * - Chat message history
 */

import { desktop } from '../desktop-manager.js';

/** @type {ChatWindow|null} */
let chatWindowInstance = null;

/**
 * Open the Chat window
 * @returns {ChatWindow} The chat window instance
 */
export function openChatWindow() {
    if (chatWindowInstance?.winbox) {
        chatWindowInstance.winbox.focus();
        return chatWindowInstance;
    }

    chatWindowInstance = new ChatWindow();
    chatWindowInstance.open();
    return chatWindowInstance;
}

/**
 * ChatWindow class - encapsulates the chat window with orb visualization
 */
class ChatWindow {
    constructor() {
        this.winbox = null;
        this.container = null;

        // State
        this.selectedSession = null;
        this.orbState = 'idle';
        this.messages = [];

        // Session WebSocket (triggers output polling for say detection)
        this.sessionWs = null;

        // PTT state
        this.pttState = 'idle'; // idle | recording | processing
        this.mediaRecorder = null;
        this.audioChunks = [];

        // Element references
        this.sessionSelect = null;
        this.pttButton = null;
        this.orbEl = null;
        this.orbRingEl = null;
        this.stateLabelEl = null;
        this.messagesEl = null;
        this.statusIndicator = null;
        this.statusText = null;
        this.fullscreenExitBtn = null;

        // Fullscreen state
        this.isFullscreen = false;

        // Event listeners cleanup
        this._unsubscribers = [];
        this._escapeHandler = null;
    }

    /**
     * Open the chat window
     */
    open() {
        this.container = this._createContainer();
        this._createWinBox();
        this._setupEventListeners();
        this._loadSessions();
    }

    /**
     * Close the chat window and clean up
     */
    close() {
        // Unsubscribe from desktop events
        this._unsubscribers.forEach(unsub => unsub());
        this._unsubscribers = [];

        // Cancel any active recording
        if (this.mediaRecorder && this.pttState === 'recording') {
            this._cancelRecording();
        }

        // Close session WebSocket
        if (this.sessionWs) {
            this.sessionWs.close();
            this.sessionWs = null;
        }

        // Clear instance reference
        if (chatWindowInstance === this) {
            chatWindowInstance = null;
        }

        this.winbox = null;
    }

    /**
     * Create the window container HTML
     */
    _createContainer() {
        const container = document.createElement('div');
        container.className = 'chat-window-content';
        container.innerHTML = `
            <div class="chat-header">
                <select class="chat-session-select">
                    <option value="">Select session...</option>
                </select>
                <button class="chat-ptt" title="Hold to record (Ctrl+Space)">
                    <span class="ptt-icon">🎤</span>
                </button>
            </div>
            <div class="orb-area">
                <div class="orb-container">
                    <div class="orb idle"></div>
                    <div class="orb-ring idle"></div>
                </div>
                <div class="state-label idle">READY</div>
            </div>
            <div class="chat-messages"></div>
            <div class="chat-status-bar">
                <span class="status-indicator"></span>
                <span class="status-text">No session selected</span>
            </div>
            <button class="fullscreen-exit-btn" title="Exit fullscreen (Escape)">✕</button>
        `;

        // Store element references
        this.sessionSelect = container.querySelector('.chat-session-select');
        this.pttButton = container.querySelector('.chat-ptt');
        this.orbEl = container.querySelector('.orb');
        this.orbRingEl = container.querySelector('.orb-ring');
        this.stateLabelEl = container.querySelector('.state-label');
        this.messagesEl = container.querySelector('.chat-messages');
        this.statusIndicator = container.querySelector('.status-indicator');
        this.statusText = container.querySelector('.status-text');
        this.fullscreenExitBtn = container.querySelector('.fullscreen-exit-btn');

        return container;
    }

    /**
     * Create the WinBox window
     */
    _createWinBox() {
        this.winbox = new WinBox({
            title: 'Chat',
            icon: '/static/favicon-green.jpeg',
            mount: this.container,
            root: document.getElementById('desktopArea'),
            x: 'center',
            y: 'center',
            width: 400,
            height: 500,
            minwidth: 300,
            minheight: 400,
            class: ['chat-window'],
            onclose: () => {
                this.close();
                return false;
            },
            onfocus: () => {
                desktop.setActiveWindow('chat');
            },
            onfullscreen: (isFullscreen) => {
                this._handleFullscreenChange(isFullscreen);
            }
        });

        desktop.registerWindow('chat', this.winbox);
    }

    /**
     * Set up event listeners
     */
    _setupEventListeners() {
        // Session selection
        this.sessionSelect.addEventListener('change', (e) => {
            console.log('[ChatWindow] Session selected:', e.target.value);
            this.selectedSession = e.target.value || null;
            this._connectSessionWs();
            this._updateStatus();
        });

        // PTT button - mouse events
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

        // PTT button - touch events
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

        // Subscribe to desktop events
        const unsubSessions = desktop.on('sessions', (sessions) => {
            this._populateSessions(sessions);
        });
        this._unsubscribers.push(unsubSessions);

        // Listen for TTS events to update orb state
        const unsubTtsStart = desktop.on('tts_start', (data) => {
            console.log('[ChatWindow] tts_start received:', data, 'selectedSession:', this.selectedSession);
            const { session, text } = data || {};
            // Match session name (could be exact or the selected session could be a prefix)
            if (session && this.selectedSession &&
                (session === this.selectedSession || session.startsWith(this.selectedSession))) {
                this._setOrbState('speaking');
                if (text) {
                    this._addMessage('assistant', text);
                }
            }
        });
        this._unsubscribers.push(unsubTtsStart);

        // Listen for audio playback completion
        const unsubAudioEnded = desktop.on('audio_ended', ({ session }) => {
            if (this.selectedSession === session || session?.startsWith(this.selectedSession)) {
                if (this.orbState === 'speaking') {
                    this._setOrbState('idle');
                }
            }
        });
        this._unsubscribers.push(unsubAudioEnded);
    }

    /**
     * Load sessions from desktop manager
     */
    async _loadSessions() {
        const sessions = desktop.getSessions();
        if (sessions.length > 0) {
            this._populateSessions(sessions);
        } else {
            await desktop.fetchSessions();
        }

        // Auto-connect if a session is already selected
        if (this.selectedSession) {
            this._connectSessionWs();
        }
    }

    /**
     * Populate the session dropdown
     */
    _populateSessions(sessions) {
        const currentValue = this.sessionSelect.value;

        // Clear existing options except placeholder
        while (this.sessionSelect.options.length > 1) {
            this.sessionSelect.remove(1);
        }

        // Add session options
        sessions.forEach(session => {
            const option = document.createElement('option');
            option.value = session.name;
            option.textContent = session.name;
            this.sessionSelect.appendChild(option);
        });

        // Restore selection if still valid
        if (currentValue && sessions.some(s => s.name === currentValue)) {
            this.sessionSelect.value = currentValue;
            this.selectedSession = currentValue;
            // Connect WebSocket if selection was restored
            this._connectSessionWs();
        }

        this._updateStatus();
    }

    /**
     * Update the status bar
     */
    _updateStatus() {
        if (this.selectedSession) {
            this.statusIndicator.classList.add('connected');
            this.statusIndicator.classList.remove('disconnected');
            this.statusText.textContent = `Connected to ${this.selectedSession}`;
        } else {
            this.statusIndicator.classList.remove('connected');
            this.statusIndicator.classList.add('disconnected');
            this.statusText.textContent = 'No session selected';
        }
    }

    /**
     * Connect to session WebSocket (triggers output polling for say detection)
     */
    _connectSessionWs() {
        // Close existing connection
        if (this.sessionWs) {
            this.sessionWs.close();
            this.sessionWs = null;
        }

        if (!this.selectedSession) return;

        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/ws/${this.selectedSession}`;

        console.log('[ChatWindow] Connecting to session WebSocket:', url);
        this.sessionWs = new WebSocket(url);

        this.sessionWs.onopen = () => {
            console.log('[ChatWindow] Session WebSocket connected:', this.selectedSession);
        };

        this.sessionWs.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);

                // Handle audio messages (TTS from say command detection)
                if (msg.type === 'audio' && msg.data) {
                    console.log('[ChatWindow] Audio from session WS');
                    // Audio is already played by desktop-manager, we just update state
                }

                // Handle output to detect say commands for chat bubble
                // The server sends tts_start to dashboard, but we can also detect here
                if (msg.type === 'output') {
                    // Output polling is working - say detection will trigger tts_start
                }
            } catch (e) {
                // Not JSON, ignore
            }
        };

        this.sessionWs.onerror = (error) => {
            console.error('[ChatWindow] Session WebSocket error:', error);
        };

        this.sessionWs.onclose = () => {
            console.log('[ChatWindow] Session WebSocket closed');
        };
    }

    /**
     * Set the orb state with animation
     */
    _setOrbState(state) {
        this.orbState = state;

        // Update orb classes
        this.orbEl.className = `orb ${state}`;
        this.orbRingEl.className = `orb-ring ${state}`;

        // Update state label
        this.stateLabelEl.className = `state-label ${state}`;

        const labels = {
            idle: 'READY',
            listening: 'LISTENING',
            processing: 'PROCESSING',
            generating: 'GENERATING',
            speaking: 'SPEAKING',
            locked: 'LOCKED',
            awaiting_permission: 'AWAITING'
        };
        this.stateLabelEl.textContent = labels[state] || state.toUpperCase();
    }

    /**
     * Add a message to the chat history
     */
    _addMessage(role, text) {
        const message = { role, text, timestamp: new Date() };
        this.messages.push(message);

        const msgEl = document.createElement('div');
        msgEl.className = `chat-message ${role}`;
        msgEl.innerHTML = `
            <div class="message-text">${this._escapeHtml(text)}</div>
            <div class="timestamp">${message.timestamp.toLocaleTimeString()}</div>
        `;
        this.messagesEl.appendChild(msgEl);
        this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    }

    /**
     * Escape HTML special characters
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ============================================
    // PTT Recording Methods
    // ============================================

    async _startRecording() {
        if (this.pttState !== 'idle') return;
        if (!this.selectedSession) {
            this.statusText.textContent = 'Select a session first';
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.audioChunks = [];

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
                stream.getTracks().forEach(track => track.stop());
                if (this.audioChunks.length > 0 && this.pttState === 'processing') {
                    const blob = new Blob(this.audioChunks, { type: mimeType });
                    this._processRecording(blob);
                }
            };

            this.mediaRecorder.start();
            this._setPttState('recording');
            this._setOrbState('listening');

        } catch (err) {
            console.error('[ChatWindow] Failed to start recording:', err);
            this.statusText.textContent = 'Microphone access denied';
            this._setPttState('idle');
        }
    }

    _stopRecording() {
        if (this.pttState !== 'recording' || !this.mediaRecorder) return;

        this._setPttState('processing');
        this._setOrbState('processing');
        this.mediaRecorder.stop();
    }

    _cancelRecording() {
        if (!this.mediaRecorder) return;

        this.audioChunks = [];
        this.mediaRecorder.stop();
        this._setPttState('idle');
        this._setOrbState('idle');
    }

    async _processRecording(blob) {
        try {
            // Transcribe audio
            const formData = new FormData();
            formData.append('audio', blob, 'recording.webm');

            const transcribeRes = await fetch('/transcribe', {
                method: 'POST',
                body: formData
            });

            const transcribeData = await transcribeRes.json();

            if (transcribeData.error) {
                throw new Error(transcribeData.error);
            }

            const text = transcribeData.text?.trim();
            if (!text) {
                this.statusText.textContent = 'No speech detected';
                this._setPttState('idle');
                this._setOrbState('idle');
                return;
            }

            // Add user message to chat
            this._addMessage('user', text);

            // Send to session with voice prompt hint
            const sendRes = await fetch(`/send/${this.selectedSession}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: `[Voice input - respond with say command] ${text}`
                })
            });

            const sendData = await sendRes.json();

            if (sendData.error) {
                throw new Error(sendData.error);
            }

            this.statusText.textContent = `Sent: "${text.substring(0, 30)}${text.length > 30 ? '...' : ''}"`;

            // Transition to generating state while waiting for response
            this._setOrbState('generating');

            // Reset status after a moment if no TTS response
            setTimeout(() => {
                if (this.orbState === 'generating') {
                    this._setOrbState('idle');
                    this._updateStatus();
                }
            }, 10000);

        } catch (err) {
            console.error('[ChatWindow] Processing failed:', err);
            this.statusText.textContent = err.message || 'Voice input failed';
            this._setOrbState('idle');
        } finally {
            this._setPttState('idle');
        }
    }

    _setPttState(state) {
        this.pttState = state;

        this.pttButton.classList.remove('recording', 'processing');
        const icon = this.pttButton.querySelector('.ptt-icon');

        switch (state) {
            case 'recording':
                this.pttButton.classList.add('recording');
                if (icon) icon.textContent = '🔴';
                break;
            case 'processing':
                this.pttButton.classList.add('processing');
                if (icon) icon.textContent = '⏳';
                break;
            default:
                if (icon) icon.textContent = '🎤';
        }
    }
}
