# Mission: Multi-line Text Input

> Simple UI improvement for the portal text input.

## Problem

The text input field in the portal room UI is a single-line `<input>`. When typing longer prompts, content scrolls horizontally which is hard to read/edit.

## Solution

Either:
1. **Replace with textarea** - Always use `<textarea>` with auto-resize
2. **Convert on overflow** - Start as `<input>`, convert to `<textarea>` when content would scroll

Option 1 is simpler and probably better UX.

## Implementation

**File:** `agentwire/templates/room.html` (or wherever the input is)

```html
<!-- Before -->
<input type="text" id="prompt-input" ... />

<!-- After -->
<textarea id="prompt-input" rows="1" ...></textarea>
```

**Auto-resize behavior:**
```javascript
const textarea = document.getElementById('prompt-input');
textarea.addEventListener('input', () => {
  textarea.style.height = 'auto';
  textarea.style.height = textarea.scrollHeight + 'px';
});
```

**Submit on Enter (without Shift):**
```javascript
textarea.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    submitPrompt();
  }
});
```

## Acceptance Criteria

- [x] Text input expands vertically as user types
- [x] Enter submits, Shift+Enter adds newline
- [x] Collapses back to single line when cleared
- [x] Styling matches current input appearance
