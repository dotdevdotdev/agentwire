# Mission: Jinja2 Template Refactor

> Refactor portal templates from custom regex-based engine to proper Jinja2 with clean component structure.

## Goal

Transform 3000+ lines of monolithic HTML/CSS/JS into a clean, maintainable template structure that any Python dev can understand at a glance. This is for open source - it needs to be beautiful.

## Current State

- Custom `_render_template()` method with 70 lines of regex parsing
- `dashboard.html` - 956 lines (HTML + CSS + JS inline)
- `room.html` - 2314 lines (HTML + CSS + JS inline)
- No template inheritance, includes, or separation of concerns

## Target State

```
agentwire/
├── templates/
│   ├── base.html                 # Common structure, head, scripts
│   ├── dashboard.html            # {% extends 'base.html' %}
│   ├── room.html                 # {% extends 'base.html' %}
│   └── components/
│       ├── orb.html              # Animated orb with state classes
│       ├── device_selector.html  # Mic/speaker dropdown macro
│       ├── voice_selector.html   # TTS voice picker
│       ├── actions_menu.html     # Session action buttons
│       ├── output_view.html      # Text output view (terminal mode)
│       └── ask_modal.html        # AskUserQuestion popup
└── static/
    ├── css/
    │   ├── base.css              # Reset, variables, common
    │   ├── orb.css               # Orb animations
    │   ├── room.css              # Room layout
    │   └── dashboard.css         # Dashboard grid
    └── js/
        ├── websocket.js          # WS connection, reconnect
        ├── audio.js              # Recording, TTS playback
        ├── orb.js                # Orb state management
        ├── output.js             # Text output view handling
        └── room.js               # Room page orchestration (imports others)
```

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Static files location | `agentwire/static/` | Separate from templates, clean Python package pattern |
| JS module system | ES Modules | Modern import/export, better organization |
| Terminal mode | Text output view | No xterm.js, just styled text display |
| Testing | Manual | Checklist-based verification |

---

## Wave 1: Setup (BLOCKING - Human/Dependencies)

- [x] **1.1** Add `aiohttp-jinja2` and `jinja2` to dependencies in `pyproject.toml`
- [x] **1.2** Run `uv pip install -e .` to install new dependencies

---

## Wave 2: Core Infrastructure

These tasks have dependencies - run sequentially or coordinate carefully.

- [x] **2.1 Initialize Jinja2 in server.py** (do first)
  - Import aiohttp_jinja2 and jinja2
  - Setup jinja2 environment with templates directory
  - Configure auto-escaping
  - Keep `_render_template()` temporarily for compatibility
  - Files: `server.py`

- [x] **2.2 Setup static file serving** (needs 2.1)
  - Create `agentwire/static/` directory structure
  - Add static file route to aiohttp app (`/static/` → `agentwire/static/`)
  - Ensure CSS/JS files are served with correct MIME types
  - Files: `server.py`, `agentwire/static/`

- [x] **2.3 Create base.html template** (needs 2.1)
  - DOCTYPE, html, head with meta tags
  - `{% block title %}` for page titles
  - `{% block styles %}` for page-specific CSS links
  - Common CSS variables in base.css link
  - Body structure with `{% block content %}`
  - `{% block scripts %}` at end for page-specific JS
  - Files: `templates/base.html`

- [x] **2.4 Create base.css**
  - CSS reset (* { box-sizing, margin, padding })
  - CSS custom properties (colors, spacing, typography)
  - Common body styles
  - Files: `static/css/base.css`

---

## Wave 3: Extract Dashboard

These tasks can run in parallel.

- [x] **3.1 Extract dashboard CSS**
  - Pull all `<style>` content from dashboard.html
  - Create `static/css/dashboard.css`
  - Organize into logical sections (layout, cards, buttons, forms)
  - Files: `static/css/dashboard.css`

- [x] **3.2 Extract dashboard JS**
  - Pull all `<script>` content from dashboard.html
  - Create `static/js/dashboard.js` as ES module
  - Convert inline onclick handlers to addEventListener
  - Export init function, call on DOMContentLoaded
  - Files: `static/js/dashboard.js`

- [x] **3.3 Refactor dashboard.html**
  - `{% extends 'base.html' %}`
  - `{% block title %}AgentWire{% endblock %}`
  - `{% block styles %}<link rel="stylesheet" href="/static/css/dashboard.css">{% endblock %}`
  - `{% block content %}` with page HTML
  - `{% block scripts %}<script type="module" src="/static/js/dashboard.js">{% endblock %}`
  - Use Jinja2 for loops: `{% for session in sessions %}`
  - Target: ~100-150 lines
  - Files: `templates/dashboard.html`

---

## Wave 4: Extract Room Components

These tasks can run in parallel.

- [x] **4.1 Extract orb component**
  - Create `components/orb.html` with orb markup (ring, orb, state label)
  - Create `static/css/orb.css` with all orb animations and state colors
  - Create `static/js/orb.js` as ES module:
    - `export function setOrbState(state)` - ready, listening, processing, generating, speaking
    - `export function init(orbElement, ringElement, labelElement)`
  - Files: `templates/components/orb.html`, `static/css/orb.css`, `static/js/orb.js`

- [x] **4.2 Extract device selectors**
  - Create `components/device_selector.html` as Jinja2 macro:
    ```jinja2
    {% macro device_selector(id, label, icon) %}
    <div class="device-selector">...</div>
    {% endmacro %}
    ```
  - Reusable for mic, speaker, voice selectors
  - Files: `templates/components/device_selector.html`

- [x] **4.3 Extract actions menu**
  - Create `components/actions_menu.html`
  - Accept `is_system_session` variable for conditional buttons
  - New Room, Fork Session, Recreate Session (or Restart Service for system)
  - Hover popovers for button labels
  - Files: `templates/components/actions_menu.html`

- [x] **4.4 Extract ask modal**
  - Create `components/ask_modal.html`
  - Hidden by default, shown via JS
  - Question display, dynamic option buttons, text input for "Other"
  - Create `static/js/ask-modal.js` as ES module:
    - `export function show(question, options, callback)`
    - `export function hide()`
  - Files: `templates/components/ask_modal.html`, `static/js/ask-modal.js`

- [x] **4.5 Extract output view**
  - Create `components/output_view.html` for text output display
  - Create `static/js/output.js` as ES module:
    - `export function append(text)`
    - `export function clear()`
    - `export function scrollToBottom()`
  - Mode toggle between ambient/output view
  - Files: `templates/components/output_view.html`, `static/js/output.js`

---

## Wave 5: Extract Room Core

These tasks can run in parallel.

- [ ] **5.1 Extract room CSS**
  - Pull remaining styles from room.html
  - Create `static/css/room.css`
  - Organize: layout, header, controls, floating-controls, bubbles
  - Files: `static/css/room.css`

- [ ] **5.2 Extract WebSocket handling**
  - Create `static/js/websocket.js` as ES module:
    - `export function connect(roomName, handlers)`
    - `export function send(type, data)`
    - `export function disconnect()`
  - Handlers object: `{ onOutput, onTts, onAsk, onState, onConnect, onDisconnect }`
  - Auto-reconnect with exponential backoff
  - Files: `static/js/websocket.js`

- [ ] **5.3 Extract audio handling**
  - Create `static/js/audio.js` as ES module:
    - `export function initRecorder(onRecordingComplete)`
    - `export function startRecording()`
    - `export function stopRecording()`
    - `export function playTts(audioData)`
    - `export function setInputDevice(deviceId)`
    - `export function setOutputDevice(deviceId)`
  - MediaRecorder for push-to-talk
  - AudioContext for TTS playback
  - Device selection with localStorage persistence
  - Files: `static/js/audio.js`

---

## Wave 6: Finalize Room

These tasks are sequential.

- [ ] **6.1 Create room.js orchestrator** (do first)
  - ES module that imports all room modules:
    ```js
    import * as ws from './websocket.js';
    import * as audio from './audio.js';
    import * as orb from './orb.js';
    import * as askModal from './ask-modal.js';
    import * as output from './output.js';
    ```
  - Initialize on DOMContentLoaded
  - Wire up event handlers between modules
  - State management across components
  - Files: `static/js/room.js`

- [ ] **6.2 Refactor room.html** (needs 6.1)
  - `{% extends 'base.html' %}`
  - `{% from 'components/device_selector.html' import device_selector %}`
  - `{% include 'components/orb.html' %}`
  - `{% include 'components/actions_menu.html' %}`
  - `{% include 'components/ask_modal.html' %}`
  - `{% include 'components/output_view.html' %}`
  - Link all static CSS/JS with `type="module"`
  - Target: ~150-200 lines of clean template
  - Files: `templates/room.html`

- [ ] **6.3 Remove old template engine** (do last)
  - Delete `_render_template()` method from server.py
  - Replace all `self._render_template()` calls with `aiohttp_jinja2.render_template()`
  - Clean up unused regex imports
  - Files: `server.py`

---

## Wave 7: Testing & Polish

Manual testing checklist.

- [ ] **7.1 Test dashboard functionality**
  - [ ] Dashboard loads without errors
  - [ ] Session list displays correctly
  - [ ] Create new session works
  - [ ] System sessions show correct actions
  - [ ] All room links work

- [ ] **7.2 Test room functionality**
  - [ ] Room page loads without errors
  - [ ] WebSocket connects (check console)
  - [ ] Push-to-talk records audio
  - [ ] Transcription appears in session
  - [ ] TTS audio plays back
  - [ ] Orb states animate correctly
  - [ ] Device selectors persist across refresh
  - [ ] Voice selector works
  - [ ] Actions menu opens/closes
  - [ ] AskUserQuestion modal works
  - [ ] Output view mode toggle works
  - [ ] Text input sends messages

- [ ] **7.3 Browser compatibility**
  - [ ] Chrome desktop
  - [ ] Firefox desktop
  - [ ] Safari desktop
  - [ ] Chrome Android
  - [ ] iOS Safari

---

## Completion Criteria

- [ ] All templates use Jinja2 (no custom regex engine)
- [ ] `room.html` under 200 lines
- [ ] `dashboard.html` under 150 lines
- [ ] All CSS in `agentwire/static/css/`
- [ ] All JS in `agentwire/static/js/` as ES modules
- [ ] Components are reusable via includes/macros
- [ ] Portal fully functional (no regressions)
- [ ] Code is clean and readable for open source

---

## Notes

- Keep the same visual design - this is a refactor, not a redesign
- Jinja2 syntax is already compatible with our current `{{ var }}` and `{% for %}` patterns
- **Use vanilla JS with ES modules** - modern, clean, no build step
- Static files served from `agentwire/static/` at `/static/` URL path
- JS modules use `type="module"` script tags
- Manual testing is sufficient for this refactor
