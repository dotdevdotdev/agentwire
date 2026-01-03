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
templates/
├── base.html                 # Common structure, head, scripts
├── dashboard.html            # {% extends 'base.html' %}
├── room.html                 # {% extends 'base.html' %}
├── components/
│   ├── orb.html              # Animated orb with state classes
│   ├── device_selector.html  # Mic/speaker dropdown macro
│   ├── voice_selector.html   # TTS voice picker
│   ├── actions_menu.html     # Session action buttons
│   ├── terminal.html         # Terminal mode view
│   └── ask_modal.html        # AskUserQuestion popup
└── static/
    ├── css/
    │   ├── base.css          # Reset, variables, common
    │   ├── orb.css           # Orb animations
    │   ├── room.css          # Room layout
    │   └── dashboard.css     # Dashboard grid
    └── js/
        ├── websocket.js      # WS connection, reconnect
        ├── audio.js          # Recording, TTS playback
        ├── orb.js            # Orb state management
        ├── terminal.js       # Terminal mode (xterm.js)
        └── room.js           # Room page orchestration
```

---

## Wave 1: Setup (BLOCKING - Human/Dependencies)

- [ ] **1.1** Add `aiohttp-jinja2` and `jinja2` to dependencies in `pyproject.toml`
- [ ] **1.2** Run `uv pip install -e .` to install new dependencies

---

## Wave 2: Core Infrastructure

- [ ] **2.1 Initialize Jinja2 in server.py**
  - Import aiohttp_jinja2 and jinja2
  - Setup jinja2 environment with templates directory
  - Configure auto-escaping, static file handling
  - Replace `_render_template()` with `aiohttp_jinja2.render_template()`
  - Files: `server.py`

- [ ] **2.2 Create base.html template**
  - DOCTYPE, html, head with meta tags
  - CSS block for page-specific styles
  - Common CSS variables (colors, spacing)
  - Body structure with content block
  - Scripts block at end
  - Files: `templates/base.html`

- [ ] **2.3 Setup static file serving**
  - Create `templates/static/` directory structure
  - Add static file route to aiohttp app
  - Ensure CSS/JS files are served with correct MIME types
  - Files: `server.py`, `templates/static/`

---

## Wave 3: Extract Dashboard

- [ ] **3.1 Extract dashboard CSS**
  - Pull all `<style>` content from dashboard.html
  - Create `static/css/dashboard.css`
  - Organize into logical sections (grid, cards, buttons)
  - Files: `templates/static/css/dashboard.css`

- [ ] **3.2 Extract dashboard JS**
  - Pull all `<script>` content from dashboard.html
  - Create `static/js/dashboard.js`
  - Convert inline handlers to addEventListener
  - Files: `templates/static/js/dashboard.js`

- [ ] **3.3 Refactor dashboard.html**
  - Extend base.html
  - Replace inline styles/scripts with static file links
  - Use Jinja2 for loops and conditionals (already compatible syntax)
  - Clean up to ~100-150 lines
  - Files: `templates/dashboard.html`

---

## Wave 4: Extract Room Components

- [ ] **4.1 Extract orb component**
  - Create `components/orb.html` with orb markup
  - Create `static/css/orb.css` with animations
  - Create `static/js/orb.js` with state management
  - Orb states: ready, listening, processing, generating, speaking
  - Files: `templates/components/orb.html`, `static/css/orb.css`, `static/js/orb.js`

- [ ] **4.2 Extract device selectors**
  - Create Jinja2 macro for dropdown selectors
  - Reusable for mic, speaker, voice
  - Create `components/device_selector.html`
  - Files: `templates/components/device_selector.html`

- [ ] **4.3 Extract actions menu**
  - Create `components/actions_menu.html`
  - New Room, Fork Session, Recreate Session buttons
  - Hover popovers for button labels
  - Files: `templates/components/actions_menu.html`

- [ ] **4.4 Extract ask modal**
  - Create `components/ask_modal.html`
  - Question display, option buttons, text input
  - Modal show/hide logic
  - Files: `templates/components/ask_modal.html`

---

## Wave 5: Extract Room Core

- [ ] **5.1 Extract room CSS**
  - Pull remaining styles from room.html
  - Create `static/css/room.css`
  - Create `static/css/base.css` for shared variables
  - Files: `templates/static/css/base.css`, `templates/static/css/room.css`

- [ ] **5.2 Extract WebSocket handling**
  - Create `static/js/websocket.js`
  - Connection, reconnection logic
  - Message routing (output, tts, ask, state)
  - Files: `templates/static/js/websocket.js`

- [ ] **5.3 Extract audio handling**
  - Create `static/js/audio.js`
  - MediaRecorder for push-to-talk
  - AudioContext for TTS playback
  - Device selection persistence
  - Files: `templates/static/js/audio.js`

- [ ] **5.4 Extract terminal handling**
  - Create `static/js/terminal.js`
  - Create `components/terminal.html`
  - xterm.js initialization, fit addon
  - Mode toggle between ambient/terminal
  - Files: `templates/static/js/terminal.js`, `templates/components/terminal.html`

---

## Wave 6: Finalize Room

- [ ] **6.1 Create room.js orchestrator**
  - Import/coordinate all room modules
  - Initialize on DOMContentLoaded
  - State management across components
  - Files: `templates/static/js/room.js`

- [ ] **6.2 Refactor room.html**
  - Extend base.html
  - Include all components
  - Link all static CSS/JS
  - Target: ~150-200 lines of clean template
  - Files: `templates/room.html`

- [ ] **6.3 Remove old template engine**
  - Delete `_render_template()` method from server.py
  - Update all template render calls
  - Clean up unused imports
  - Files: `server.py`

---

## Wave 7: Testing & Polish

- [ ] **7.1 Test dashboard functionality**
  - Session list loads
  - Create session works
  - System sessions detected
  - All links work

- [ ] **7.2 Test room functionality**
  - WebSocket connects
  - Push-to-talk records and transcribes
  - TTS audio plays
  - Orb states animate correctly
  - Device selectors persist
  - Actions menu works
  - AskUserQuestion modal works
  - Terminal mode works

- [ ] **7.3 Browser compatibility**
  - Test Chrome, Firefox, Safari
  - Test mobile (iOS Safari, Chrome Android)
  - Fix any issues

---

## Completion Criteria

- [ ] All templates use Jinja2 (no custom regex engine)
- [ ] `room.html` under 200 lines
- [ ] `dashboard.html` under 150 lines
- [ ] All CSS in static files
- [ ] All JS in static files (modular)
- [ ] Components are reusable via includes/macros
- [ ] Portal fully functional (no regressions)
- [ ] Code is clean and readable for open source

---

## Notes

- Keep the same visual design - this is a refactor, not a redesign
- Jinja2 syntax is already compatible with our current `{{ var }}` and `{% for %}` patterns
- Consider adding Alpine.js for lightweight reactivity (separate decision)
- Static files should be served with cache headers for production
