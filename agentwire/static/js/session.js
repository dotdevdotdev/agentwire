/**
 * Session Page Orchestrator
 *
 * Imports and wires together all session modules:
 * - WebSocket connection and message routing
 * - Audio recording and TTS playback
 * - Orb state visualization
 * - Ask modal for user questions
 * - Output view for monitor mode
 */

import * as ws from './websocket.js';
import * as audio from './audio.js';
import * as orb from './orb.js';
import * as askModal from './ask-modal.js';
import * as output from './output.js';
import { TerminalMode } from './terminal.js';

// ============================================
// Configuration (set from template)
// ============================================

/** @type {string} */
let SESSION_NAME = '';

/** @type {boolean} */
let IS_SYSTEM_SESSION = false;

// ============================================
// State
// ============================================

const STATES = {
    IDLE: 'idle',
    LISTENING: 'listening',
    PROCESSING: 'processing',
    GENERATING: 'generating',
    SPEAKING: 'speaking',
    LOCKED: 'locked',
    AWAITING_PERMISSION: 'awaiting_permission'
};

let currentState = STATES.IDLE;
let currentMode = 'ambient';  // 'ambient', 'monitor', or 'terminal'
let isAmbientMode = true;  // Tracks ambient mode state
let textInputOpen = false;
let processingTimeout = null;
let pendingAiText = null;
let pendingImage = null;  // { file, preview, filename }
let currentQuestion = null;
let terminalMode = null;  // TerminalMode instance

// ============================================
// DOM Elements
// ============================================

const elements = {};

function cacheElements() {
    elements.output = document.getElementById('output');
    elements.outputContent = document.getElementById('outputContent');
    elements.ambient = document.getElementById('ambient');
    elements.orb = document.getElementById('orb');
    elements.orbRing = document.getElementById('orbRing');
    elements.stateLabel = document.getElementById('stateLabel');
    elements.status = document.getElementById('status');
    elements.micBtn = document.getElementById('micBtn');
    elements.modeToggle = document.getElementById('modeToggle');
    elements.micSelect = document.getElementById('micSelect');
    elements.speakerSelect = document.getElementById('speakerSelect');
    elements.voiceSelect = document.getElementById('voiceSelect');
    elements.settingsDropdown = document.getElementById('settingsDropdown');
    elements.aiBubble = document.getElementById('aiBubble');
    elements.userBubble = document.getElementById('userBubble');
    elements.aiBubbleContainer = document.querySelector('.ai-bubble-container');
    elements.userBubbleContainer = document.querySelector('.user-bubble-container');
    elements.questionModal = document.getElementById('questionModal');
    elements.questionBadge = document.getElementById('questionBadge');
    elements.questionText = document.getElementById('questionText');
    elements.questionOptions = document.getElementById('questionOptions');
    elements.questionCustom = document.getElementById('questionCustom');
    elements.questionCustomInput = document.getElementById('questionCustomInput');
    elements.permissionModal = document.getElementById('permissionModal');
    elements.permissionTitle = document.getElementById('permissionTitle');
    elements.permissionTarget = document.getElementById('permissionTarget');
    elements.permissionDiff = document.getElementById('permissionDiff');
    elements.permissionDiffContent = document.getElementById('permissionDiffContent');
    elements.textToggleBtn = document.getElementById('textToggleBtn');
    elements.textInputExpanded = document.getElementById('textInputExpanded');
    elements.textInputAmbient = document.getElementById('textInputAmbient');
    elements.attachBtnAmbient = document.getElementById('attachBtnAmbient');
    elements.ambientImagePreview = document.getElementById('ambientImagePreview');
    elements.fileInput = document.getElementById('fileInput');
    elements.actionsBtn = document.getElementById('actionsBtn');
    elements.actionsMenu = document.getElementById('actionsMenu');
    elements.exaggeration = document.getElementById('exaggeration');
    elements.cfgWeight = document.getElementById('cfgWeight');

    // Mode tabs and content
    elements.ambientTab = document.getElementById('ambientTab');
    elements.monitorTab = document.getElementById('monitorTab');
    elements.terminalTab = document.getElementById('terminalTab');
    elements.terminalModeContent = document.querySelector('.terminal-mode-content');
}

// ============================================
// State Management
// ============================================

function setState(newState) {
    currentState = newState;

    // Update orb
    orb.setOrbState(newState);

    // Update mic button
    if (elements.micBtn) {
        elements.micBtn.className = 'mic-btn ' + newState;
    }

    // Update bubbles
    if (elements.aiBubble) {
        elements.aiBubble.classList.toggle('speaking', newState === STATES.SPEAKING);
    }
    if (elements.userBubble) {
        elements.userBubble.classList.toggle('listening', newState === STATES.LISTENING);
    }
}

function handleSessionActivity() {
    if (currentState === STATES.IDLE) {
        setState(STATES.PROCESSING);
    }

    if (currentState === STATES.PROCESSING) {
        if (processingTimeout) clearTimeout(processingTimeout);
        processingTimeout = setTimeout(() => {
            if (currentState === STATES.PROCESSING) {
                setState(STATES.IDLE);
            }
        }, 5000);
    }
}

// ============================================
// Bubble Management
// ============================================

function showUserBubble(text) {
    if (currentMode !== 'ambient' || !elements.userBubble) return;
    elements.userBubble.textContent = text;
    elements.userBubble.classList.add('visible');
}

function hideUserBubble() {
    if (elements.userBubble) {
        elements.userBubble.classList.remove('visible');
    }
}

function cleanText(text) {
    return text.replace(/\\([!?.,;:'"])/g, '$1');
}

function showAiBubble(text) {
    if (currentMode !== 'ambient' || !elements.aiBubble) return;
    elements.aiBubble.textContent = cleanText(text);
    elements.aiBubble.classList.add('visible');
}

// ============================================
// WebSocket Message Handlers
// ============================================

function handleOutput(data) {
    output.setContent(output.ansiToHtml(data));
    handleSessionActivity();

    // Check for AskUserQuestion UI pattern
    if (!currentQuestion) {
        const question = parseQuestion(data);
        if (question) {
            showQuestionModal(question.header, question.question, question.options);
        }
    }
}

function handleTts(eventType, data) {
    if (eventType === 'start') {
        if (processingTimeout) {
            clearTimeout(processingTimeout);
            processingTimeout = null;
        }
        setState(STATES.GENERATING);
        if (data.text) {
            pendingAiText = data.text;
        }
    } else if (eventType === 'audio') {
        if (pendingAiText) {
            showAiBubble(pendingAiText);
            pendingAiText = null;
        }
        playTtsAudio(data.data);
    }
}

function handleAsk(eventType, data) {
    if (eventType === 'question') {
        showQuestionModal(data.header, data.question, data.options);
    } else if (eventType === 'question_answered') {
        hideQuestionModal();
    } else if (eventType === 'permission_request') {
        showPermissionModal(data.toolName, data.toolInput, data.message);
    } else if (eventType === 'permission_resolved') {
        hidePermissionModal();
    }
}

function handleState(state) {
    if (state === 'locked' && currentState === STATES.IDLE) {
        setState(STATES.LOCKED);
    } else if (state === 'unlocked' && currentState === STATES.LOCKED) {
        setState(STATES.IDLE);
    }
}

function handleConnect() {
    if (elements.status) {
        elements.status.textContent = 'connected';
        elements.status.className = 'status connected';
    }
}

function handleDisconnect() {
    if (elements.status) {
        elements.status.textContent = 'reconnecting...';
        elements.status.className = 'status';
    }
}

// ============================================
// TTS Playback
// ============================================

async function playTtsAudio(base64Data) {
    if (processingTimeout) {
        clearTimeout(processingTimeout);
        processingTimeout = null;
    }

    setState(STATES.SPEAKING);

    try {
        await audio.playTts(base64Data);
    } catch (err) {
        console.error('TTS playback error:', err);
    }

    // Return to idle when done (unless state changed)
    if (currentState === STATES.SPEAKING) {
        setState(STATES.IDLE);
    }
}

// ============================================
// Recording
// ============================================

async function startListening() {
    if (currentState === STATES.SPEAKING) {
        audio.stopTts();
    }

    if ([STATES.PROCESSING, STATES.GENERATING, STATES.LOCKED].includes(currentState)) {
        return;
    }

    ws.send('recording_started');

    const started = await audio.startRecording();
    if (started) {
        setState(STATES.LISTENING);
        showUserBubble('Recording...');
    }
}

function stopListening() {
    if (currentState !== STATES.LISTENING) return;

    showUserBubble('Transcribing...');
    ws.send('recording_stopped');
    audio.stopRecording();
}

async function handleRecordingComplete(audioBlob) {
    setState(STATES.PROCESSING);

    if (processingTimeout) clearTimeout(processingTimeout);

    try {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');

        const resp = await fetch('/transcribe', {
            method: 'POST',
            body: formData
        });

        const data = await resp.json();

        if (data.error || !data.text?.trim()) {
            hideUserBubble();
            setState(STATES.IDLE);
            return;
        }

        const text = data.text.trim();
        showUserBubble(text);

        await fetch('/send/' + SESSION_NAME, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: '[Voice] ' + text })
        });

        processingTimeout = setTimeout(() => {
            if (currentState === STATES.PROCESSING) {
                setState(STATES.IDLE);
            }
        }, 30000);

    } catch (err) {
        console.error('Transcribe error:', err);
        hideUserBubble();
        setState(STATES.IDLE);
    }
}

function handleAudioLevel(level) {
    if (currentState === STATES.LISTENING && elements.micBtn) {
        const shadow = level > 10
            ? `0 0 ${level/2}px ${level/4}px rgba(245, 158, 11, ${level/100})`
            : 'none';
        elements.micBtn.style.boxShadow = shadow;
    } else if (elements.micBtn) {
        elements.micBtn.style.boxShadow = '';
    }
}

// ============================================
// Question Modal (AskUserQuestion)
// ============================================

function parseQuestion(text) {
    const clean = text.replace(/\x1b\[[0-9;]*m/g, '');
    const fullPattern = /\s*☐\s+(.+?)\s*\n\s*\n([\s\S]+?\?)\s*\n\s*\n((?:[❯\s]+\d+\.\s+[\s\S]+?\n(?:\s{3,}[\s\S]+?\n)?)+)/;
    const blockMatch = clean.match(fullPattern);

    if (!blockMatch) return null;

    const header = blockMatch[1].trim();
    const question = blockMatch[2].trim();
    const optionsBlock = blockMatch[3];

    const options = [];
    const optionRegex = /[❯\s]+(\d+)\.\s+(.+?)(?:\n\s{3,}(.+?))?(?=\n[❯\s]+\d+\.|\n\s*\n|\n\s*Enter|$)/g;
    let match;
    while ((match = optionRegex.exec(optionsBlock)) !== null) {
        options.push({
            number: match[1],
            label: match[2].trim(),
            description: match[3] ? match[3].trim() : ''
        });
    }

    if (options.length === 0) return null;

    return { header, question, options };
}

function showQuestionModal(header, question, options) {
    currentQuestion = { header, question, options };

    askModal.show(header, question, options, async (answer, isCustom, optionNumber) => {
        try {
            const body = isCustom
                ? { answer, option_number: optionNumber }
                : { answer, custom: false };

            await fetch(`/api/answer/${SESSION_NAME}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
        } catch (e) {
            console.error('Failed to submit answer:', e);
        }
    });

    // Speak the question
    fetch(`/api/say/${SESSION_NAME}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: question })
    }).catch(e => console.error('Failed to speak question:', e));
}

function hideQuestionModal() {
    askModal.hide();
    currentQuestion = null;
}

// ============================================
// Permission Modal
// ============================================

function showPermissionModal(toolName, toolInput, message) {
    setState(STATES.AWAITING_PERMISSION);

    let title = 'Claude wants to...';
    let target = '';

    if (toolName === 'Edit') {
        title = 'Claude wants to edit';
        target = toolInput.file_path || '';
    } else if (toolName === 'Write') {
        title = 'Claude wants to write to';
        target = toolInput.file_path || '';
    } else if (toolName === 'Bash') {
        title = 'Claude wants to run';
        target = toolInput.command || '';
    } else {
        title = `Claude wants to use ${toolName}`;
        target = message || JSON.stringify(toolInput, null, 2);
    }

    if (elements.permissionTitle) elements.permissionTitle.textContent = title;
    if (elements.permissionTarget) elements.permissionTarget.textContent = target;

    // Show diff for Edit tool
    if (toolName === 'Edit' && toolInput.old_string && toolInput.new_string && elements.permissionDiff) {
        elements.permissionDiffContent.innerHTML = generateDiffHtml(toolInput.old_string, toolInput.new_string);
        elements.permissionDiff.style.display = 'block';
    } else if (elements.permissionDiff) {
        elements.permissionDiff.style.display = 'none';
    }

    if (elements.permissionModal) elements.permissionModal.classList.add('visible');
}

function hidePermissionModal() {
    if (elements.permissionModal) elements.permissionModal.classList.remove('visible');
    if (currentState === STATES.AWAITING_PERMISSION) {
        setState(STATES.IDLE);
    }
}

function generateDiffHtml(oldText, newText) {
    const escapeHtml = text => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    let html = '';

    oldText.split('\n').forEach(line => {
        html += `<div class="line-removed">- ${escapeHtml(line)}</div>`;
    });
    newText.split('\n').forEach(line => {
        html += `<div class="line-added">+ ${escapeHtml(line)}</div>`;
    });

    return html;
}

async function respondToPermission(decision, message = '') {
    // For custom feedback, require a message
    if (decision === 'custom' && !message.trim()) {
        return;
    }

    try {
        await fetch(`/api/permission/${SESSION_NAME}/respond`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ decision, message })
        });
        hidePermissionModal();
        // Clear the custom input
        const customInput = document.getElementById('permissionCustomInput');
        if (customInput) customInput.value = '';
    } catch (e) {
        console.error('Failed to respond to permission:', e);
    }
}

// ============================================
// Mode Toggle
// ============================================

function toggleMode() {
    isAmbientMode = !isAmbientMode;

    document.body.classList.toggle('monitor-mode', !isAmbientMode);

    if (elements.output) {
        elements.output.classList.remove('ambient-default');
        elements.output.classList.toggle('hidden', isAmbientMode);
    }
    if (elements.ambient) {
        elements.ambient.classList.remove('ambient-default');
        elements.ambient.classList.toggle('active', isAmbientMode);
    }
    if (elements.modeToggle) {
        elements.modeToggle.textContent = isAmbientMode ? 'Switch to Monitor' : 'Switch to Ambient';
    }
    if (elements.settingsDropdown) {
        elements.settingsDropdown.classList.remove('open');
    }

    if (currentMode !== 'ambient') {
        // Monitor mode
        if (elements.aiBubbleContainer) elements.aiBubbleContainer.style.display = 'none';
        if (elements.userBubbleContainer) elements.userBubbleContainer.style.display = 'none';

        textInputOpen = true;
        if (elements.textToggleBtn) elements.textToggleBtn.classList.add('active');
        if (elements.textInputExpanded) elements.textInputExpanded.classList.add('open');

        setTimeout(() => {
            output.scrollToBottom();
            if (elements.textInputAmbient) elements.textInputAmbient.focus();
        }, 50);
    } else {
        // Ambient mode
        if (elements.aiBubbleContainer) elements.aiBubbleContainer.style.display = '';
        if (elements.userBubbleContainer) elements.userBubbleContainer.style.display = '';
    }
}

/**
 * Switch to a specific mode: 'ambient', 'monitor', or 'terminal'
 */
function switchToMode(mode) {
    if (currentMode === mode) return;

    console.log('[Mode] Switching from', currentMode, 'to', mode);
    currentMode = mode;

    // Update ambient mode flag
    isAmbientMode = (mode === 'ambient');

    // Update tab states
    if (elements.ambientTab) elements.ambientTab.classList.toggle('active', mode === 'ambient');
    if (elements.monitorTab) elements.monitorTab.classList.toggle('active', mode === 'monitor');
    if (elements.terminalTab) elements.terminalTab.classList.toggle('active', mode === 'terminal');

    // Hide all mode content
    if (elements.ambient) {
        elements.ambient.style.display = 'none';
        elements.ambient.classList.remove('ambient-default');
    }
    if (elements.output) {
        elements.output.style.display = 'none';
        elements.output.classList.remove('ambient-default');
    }
    if (elements.terminalModeContent) elements.terminalModeContent.style.display = 'none';

    // Show selected mode content
    switch (mode) {
        case 'ambient':
            if (elements.ambient) {
                elements.ambient.style.display = '';
                elements.ambient.classList.add('ambient-default');
            }
            if (elements.aiBubbleContainer) elements.aiBubbleContainer.style.display = '';
            if (elements.userBubbleContainer) elements.userBubbleContainer.style.display = '';
            if (elements.output) elements.output.classList.add('ambient-default');
            document.body.classList.remove('monitor-mode');
            document.body.classList.remove('terminal-mode');
            break;

        case 'monitor':
            if (elements.output) {
                elements.output.style.display = 'block';
                elements.output.classList.remove('ambient-default');
                setTimeout(() => output.scrollToBottom(), 50);
            }
            if (elements.ambient) elements.ambient.classList.add('ambient-default');
            if (elements.aiBubbleContainer) elements.aiBubbleContainer.style.display = 'none';
            if (elements.userBubbleContainer) elements.userBubbleContainer.style.display = 'none';
            document.body.classList.add('monitor-mode');
            document.body.classList.remove('terminal-mode');

            // Open text input in monitor mode (but don't auto-focus)
            textInputOpen = true;
            if (elements.textToggleBtn) elements.textToggleBtn.classList.add('active');
            if (elements.textInputExpanded) elements.textInputExpanded.classList.add('open');
            break;

        case 'terminal':
            if (elements.terminalModeContent) {
                elements.terminalModeContent.style.display = '';
            }
            if (elements.aiBubbleContainer) elements.aiBubbleContainer.style.display = 'none';
            if (elements.userBubbleContainer) elements.userBubbleContainer.style.display = 'none';
            document.body.classList.remove('monitor-mode');
            document.body.classList.add('terminal-mode');

            // If terminal mode has been activated, show it
            if (terminalMode && terminalMode.isActivated) {
                terminalMode.onModeReturn();
            }
            break;
    }

    // Save preference to localStorage
    try {
        localStorage.setItem(`agentwire-mode-${SESSION_NAME}`, mode);
    } catch (e) {
        console.warn('Failed to save mode preference:', e);
    }

    // Close settings dropdown
    if (elements.settingsDropdown) {
        elements.settingsDropdown.classList.remove('open');
    }
}

// ============================================
// Text Input
// ============================================

function toggleTextInput() {
    textInputOpen = !textInputOpen;
    if (elements.textToggleBtn) elements.textToggleBtn.classList.toggle('active', textInputOpen);
    if (elements.textInputExpanded) elements.textInputExpanded.classList.toggle('open', textInputOpen);
    if (textInputOpen && elements.textInputAmbient) {
        setTimeout(() => elements.textInputAmbient.focus(), 100);
    }
}

async function sendTextInput() {
    const text = elements.textInputAmbient?.value.trim() || '';
    if (!text && !pendingImage) return;

    const sendBtn = document.getElementById('sendBtnAmbient');
    if (sendBtn) sendBtn.disabled = true;
    if (elements.textInputAmbient) elements.textInputAmbient.disabled = true;

    showUserBubble(text || '📷');

    try {
        let finalText = text;

        if (pendingImage) {
            const imagePath = await uploadImage();
            if (imagePath) {
                finalText = `@${imagePath} ${text}`;
            }
            removeImage();
        }

        await fetch('/send/' + SESSION_NAME, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: '[Remote text - use say "message"] ' + finalText })
        });

        if (elements.textInputAmbient) {
            elements.textInputAmbient.value = '';
            elements.textInputAmbient.style.height = 'auto';
        }
        setState(STATES.PROCESSING);

        if (isAmbientMode) {
            textInputOpen = false;
            if (elements.textToggleBtn) elements.textToggleBtn.classList.remove('active');
            if (elements.textInputExpanded) elements.textInputExpanded.classList.remove('open');
        }

        if (processingTimeout) clearTimeout(processingTimeout);
        processingTimeout = setTimeout(() => {
            if (currentState === STATES.PROCESSING) setState(STATES.IDLE);
        }, 30000);

    } catch (err) {
        console.error('Send error:', err);
    } finally {
        if (sendBtn) sendBtn.disabled = false;
        if (elements.textInputAmbient) elements.textInputAmbient.disabled = false;
    }
}

// ============================================
// Image Attachment
// ============================================

function triggerFileInput() {
    if (elements.fileInput) elements.fileInput.click();
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) attachImage(file);
    event.target.value = '';
}

function attachImage(file) {
    if (!file.type.startsWith('image/')) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        pendingImage = { file, preview: e.target.result, filename: file.name };
        showImagePreview();
    };
    reader.readAsDataURL(file);
}

function showImagePreview() {
    if (!pendingImage) return;
    if (elements.ambientImagePreview) {
        elements.ambientImagePreview.src = pendingImage.preview;
        elements.ambientImagePreview.classList.add('visible');
    }
    if (elements.attachBtnAmbient) elements.attachBtnAmbient.classList.add('has-image');
}

function removeImage() {
    pendingImage = null;
    if (elements.ambientImagePreview) elements.ambientImagePreview.classList.remove('visible');
    if (elements.attachBtnAmbient) elements.attachBtnAmbient.classList.remove('has-image');
}

async function uploadImage() {
    if (!pendingImage) return null;

    const formData = new FormData();
    formData.append('image', pendingImage.file);

    try {
        const resp = await fetch('/upload', { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.error) {
            alert('Image upload failed: ' + data.error);
            return null;
        }
        return data.path;
    } catch (err) {
        alert('Image upload error: ' + err.message);
        return null;
    }
}

// ============================================
// Settings & Config
// ============================================

function toggleSettings() {
    if (elements.settingsDropdown) elements.settingsDropdown.classList.toggle('open');
}

async function populateAudioDevices() {
    try {
        const { inputs, outputs } = await audio.enumerateDevices();
        const savedMic = audio.getInputDevice();
        const savedSpeaker = audio.getOutputDevice();

        if (elements.micSelect) {
            elements.micSelect.innerHTML = '<option value="">Default Mic</option>';
            inputs.forEach(mic => {
                const opt = document.createElement('option');
                opt.value = mic.deviceId;
                opt.textContent = mic.label || `Microphone ${mic.deviceId.slice(0, 8)}`;
                if (mic.deviceId === savedMic) opt.selected = true;
                elements.micSelect.appendChild(opt);
            });
        }

        if (elements.speakerSelect) {
            elements.speakerSelect.innerHTML = '<option value="">Default Speaker</option>';
            outputs.forEach(speaker => {
                const opt = document.createElement('option');
                opt.value = speaker.deviceId;
                opt.textContent = speaker.label || `Speaker ${speaker.deviceId.slice(0, 8)}`;
                if (speaker.deviceId === savedSpeaker) opt.selected = true;
                elements.speakerSelect.appendChild(opt);
            });

            if (!audio.isOutputSelectionSupported()) {
                elements.speakerSelect.style.display = 'none';
            }
        }
    } catch (e) {
        console.log('Could not enumerate audio devices:', e);
    }
}

function updateMic() {
    if (elements.micSelect) audio.setInputDevice(elements.micSelect.value);
}

function updateSpeaker() {
    if (elements.speakerSelect) audio.setOutputDevice(elements.speakerSelect.value);
}

async function updateVoice() {
    if (!elements.voiceSelect) return;
    await fetch('/api/session/' + SESSION_NAME + '/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice: elements.voiceSelect.value })
    });
}

async function updateTTS() {
    const exag = elements.exaggeration ? parseFloat(elements.exaggeration.value) : 0.3;
    const cfg = elements.cfgWeight ? parseFloat(elements.cfgWeight.value) : 0.5;
    await fetch('/api/session/' + SESSION_NAME + '/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exaggeration: exag, cfg_weight: cfg })
    });
}

// ============================================
// Actions Menu
// ============================================

function toggleActionsMenu() {
    if (elements.actionsMenu) {
        const isOpen = elements.actionsMenu.classList.toggle('open');
        if (elements.actionsBtn) elements.actionsBtn.classList.toggle('active', isOpen);
    }
}

function closeActionsMenu() {
    if (elements.actionsMenu) elements.actionsMenu.classList.remove('open');
    if (elements.actionsBtn) elements.actionsBtn.classList.remove('active');
}

async function actionNewSession() {
    closeActionsMenu();
    try {
        const resp = await fetch(`/api/session/${SESSION_NAME}/spawn-sibling`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await resp.json();
        if (resp.ok && data.session) {
            window.open(`/session/${data.session}`, '_blank');
        } else {
            alert('Failed to create new session: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Failed to create new session');
    }
}

async function actionForkSession() {
    closeActionsMenu();
    try {
        const resp = await fetch(`/api/session/${SESSION_NAME}/fork`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await resp.json();
        if (resp.ok && data.session) {
            window.open(`/session/${data.session}`, '_blank');
        } else {
            alert('Failed to fork session: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Failed to fork session');
    }
}

async function actionRecreateSession() {
    closeActionsMenu();
    if (!confirm('Recreate this session?\n\nThis will:\n• Close Claude Code and destroy the tmux session\n• Remove the git worktree directory\n• Pull latest changes\n• Create a fresh worktree and session')) {
        return;
    }
    try {
        const resp = await fetch(`/api/session/${SESSION_NAME}/recreate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await resp.json();
        if (resp.ok) {
            if (data.session && data.session !== SESSION_NAME) {
                window.location.href = `/session/${data.session}`;
            } else {
                window.location.reload();
            }
        } else {
            alert('Failed to recreate session: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Failed to recreate session');
    }
}

async function actionRestartService() {
    closeActionsMenu();
    const serviceName = SESSION_NAME.split('@')[0];
    if (!confirm(`Restart the ${serviceName} service?`)) return;

    try {
        const resp = await fetch(`/api/session/${SESSION_NAME}/restart-service`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await resp.json();
        if (resp.ok) {
            alert(data.message || 'Service restarted');
            if (serviceName === 'agentwire-portal') {
                setTimeout(() => window.location.reload(), 3000);
            } else {
                window.location.reload();
            }
        } else {
            alert('Failed to restart service: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Failed to restart service');
    }
}

// ============================================
// Event Binding
// ============================================

function bindEvents() {
    // Mic button
    if (elements.micBtn) {
        elements.micBtn.addEventListener('mousedown', startListening);
        elements.micBtn.addEventListener('mouseup', stopListening);
        elements.micBtn.addEventListener('mouseleave', stopListening);
        elements.micBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startListening(); });
        elements.micBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopListening(); });
    }

    // Text input
    if (elements.textInputAmbient) {
        elements.textInputAmbient.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendTextInput();
            }
        });

        // Auto-resize textarea
        elements.textInputAmbient.addEventListener('input', () => {
            const textarea = elements.textInputAmbient;
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        });
    }

    // Device selectors
    if (elements.micSelect) elements.micSelect.addEventListener('change', updateMic);
    if (elements.speakerSelect) elements.speakerSelect.addEventListener('change', updateSpeaker);
    if (elements.voiceSelect) elements.voiceSelect.addEventListener('change', updateVoice);
    if (elements.exaggeration) elements.exaggeration.addEventListener('change', updateTTS);
    if (elements.cfgWeight) elements.cfgWeight.addEventListener('change', updateTTS);

    // File input
    if (elements.fileInput) elements.fileInput.addEventListener('change', handleFileSelect);

    // Paste for images
    document.addEventListener('paste', async (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;
        for (const item of items) {
            if (item.type.startsWith('image/')) {
                e.preventDefault();
                const file = item.getAsFile();
                if (file) attachImage(file);
                break;
            }
        }
    });

    // Close dropdowns on outside click
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.header-right') && elements.settingsDropdown) {
            elements.settingsDropdown.classList.remove('open');
        }
        if (!elements.actionsBtn?.contains(e.target) && !elements.actionsMenu?.contains(e.target)) {
            closeActionsMenu();
        }
    });
}

// ============================================
// Initialization
// ============================================

export function init(config) {
    SESSION_NAME = config.session;
    IS_SYSTEM_SESSION = config.isSystemSession || false;

    cacheElements();

    // Initialize modules
    orb.init(elements.orb, elements.orbRing, elements.stateLabel);
    output.init(elements.output, elements.outputContent);
    audio.initRecorder(handleRecordingComplete, handleAudioLevel);
    askModal.init({
        modal: elements.questionModal,
        badge: elements.questionBadge,
        text: elements.questionText,
        options: elements.questionOptions,
        custom: elements.questionCustom,
        customInput: elements.questionCustomInput
    });

    // Initialize terminal mode
    terminalMode = new TerminalMode(SESSION_NAME);

    // Connect WebSocket
    ws.connect(SESSION_NAME, {
        onOutput: handleOutput,
        onTts: handleTts,
        onAsk: handleAsk,
        onState: handleState,
        onConnect: handleConnect,
        onDisconnect: handleDisconnect,
        onActivity: handleSessionActivity
    });

    // Bind events
    bindEvents();

    // Load saved mode preference from localStorage
    try {
        const savedMode = localStorage.getItem(`agentwire-mode-${SESSION_NAME}`);
        if (savedMode && (savedMode === 'ambient' || savedMode === 'monitor')) {
            switchToMode(savedMode);
        }
    } catch (e) {
        console.warn('Failed to save mode preference:', e);
    }

    // Populate devices
    populateAudioDevices();

    // Export functions for onclick handlers in HTML
    window.switchToMode = switchToMode;
    window.toggleSettings = toggleSettings;
    window.toggleTextInput = toggleTextInput;
    window.sendTextInputAmbient = sendTextInput;
    window.triggerFileInput = triggerFileInput;
    window.removeImage = removeImage;
    window.toggleActionsMenu = toggleActionsMenu;
    window.actionNewSession = actionNewSession;
    window.actionForkSession = actionForkSession;
    window.actionRecreateSession = actionRecreateSession;
    window.actionRestartService = actionRestartService;
    window.respondToPermission = respondToPermission;
    window.updateVoice = updateVoice;
    window.updateTTS = updateTTS;
    window.updateMic = updateMic;
    window.updateSpeaker = updateSpeaker;
}

// Auto-init when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (window.SESSION_CONFIG) {
        init(window.SESSION_CONFIG);
    }
});
