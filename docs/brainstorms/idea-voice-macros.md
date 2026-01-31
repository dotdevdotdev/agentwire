# Voice Macros: Speak Less, Do More

> User-defined voice shortcuts that expand to full commands or workflows.

## Problem

Voice commands are verbose. Common operations require saying the same long phrases repeatedly:

```
"Spawn an opencode worker with the glm-worker role"
"Check the output of pane two"
"Kill all workers and start fresh"
"Send to the website session: check the build"
```

This verbosity creates friction:
- **Fatigue**: Repeating full commands dozens of times per session
- **Errors**: Long phrases have more room for STT mistakes
- **Speed**: Voice should be faster than typing, but isn't for complex commands

Push-to-talk already adds latency. Long commands compound it.

## Proposed Solution

**Voice Macros** - user-defined shortcuts that expand to full commands or multi-step workflows.

### Basic Macros

Define in `~/.agentwire/macros.yaml`:

```yaml
macros:
  # Simple expansion
  helper:
    expand: "spawn an opencode worker with the glm-worker role"

  scout:
    expand: "spawn a claude worker with the explorer role"

  status:
    expand: "check all worker panes and summarize their status"

  # With variables
  check:
    pattern: "check {pane}"
    expand: "show me the last 20 lines from pane {pane}"

  tell:
    pattern: "tell {session} {message}"
    expand: "send to session {session}: {message}"
```

Usage:
```
[User]: "Helper"
[System interprets as]: "Spawn an opencode worker with the glm-worker role"

[User]: "Check two"
[System interprets as]: "Show me the last 20 lines from pane 2"

[User]: "Tell website rebuild the nav"
[System interprets as]: "Send to session website: rebuild the nav"
```

### Workflow Macros

Chain multiple actions:

```yaml
macros:
  fresh-start:
    steps:
      - "kill all worker panes"
      - "wait 2 seconds"
      - "spawn an opencode worker with glm-worker role"
    confirm: true  # Ask before executing

  ship-it:
    steps:
      - "run the test suite"
      - "if tests pass, commit with message: {message}"
      - "push to origin"
    pattern: "ship it {message}"
```

### Context-Aware Macros

Macros can be scoped to specific sessions or projects:

```yaml
# In project's .agentwire.yml
macros:
  deploy:
    expand: "run vercel deploy --prod"
    # Only available in this project

  test:
    expand: "run npm test"
    # Overrides global "test" macro
```

### Learning Mode (Future)

Detect repeated patterns and suggest macros:

```
[System]: "You've said 'spawn an opencode worker with glm-worker role'
          8 times today. Create a shortcut?"
[User]: "Yes, call it helper"
[System]: "Done. Say 'helper' to spawn a GLM worker."
```

## Implementation Considerations

### Macro Resolution Pipeline

```
User speech → STT → Text
                      ↓
              Macro resolver
                      ↓
            ┌─────────┴─────────┐
            │ Check exact match │
            │ Check pattern match│
            │ Pass through      │
            └─────────┬─────────┘
                      ↓
              Expanded text → Agent
```

### Pattern Matching

Simple slot-based patterns, not full regex:
- `{word}` - Single word
- `{words}` - Multiple words (greedy)
- `{number}` - Numeric value

```python
def match_pattern(pattern: str, text: str) -> dict | None:
    # "check {pane}" matches "check two" → {"pane": "two"}
    # "tell {session} {message}" matches "tell website fix nav"
    #   → {"session": "website", "message": "fix nav"}
```

### Conflict Resolution

Priority order:
1. Project macros (`.agentwire.yml`)
2. User macros (`~/.agentwire/macros.yaml`)
3. Built-in macros (shipped with agentwire)

### STT Preprocessing

Macros need to handle STT variations:
- "Helper" vs "helper" (case)
- "Check 2" vs "Check two" (numbers)
- "tell web site" vs "tell website" (spacing)

Normalize before matching:
```python
def normalize(text: str) -> str:
    text = text.lower()
    text = words_to_numbers(text)  # "two" → "2"
    text = collapse_spaces(text)
    return text
```

### Feedback

When a macro expands, acknowledge it:

```
[User]: "Helper"
[TTS]: "Spawning GLM worker"
```

Short confirmation so user knows the macro fired. Configurable verbosity.

### Macro Listing

```bash
# CLI
agentwire macros list
agentwire macros show helper
agentwire macros add helper "spawn an opencode worker with glm-worker role"

# Voice
[User]: "What macros do I have?"
[System]: "You have 5 macros: helper, scout, status, check, and fresh-start"
```

## Built-in Macros

Ship useful defaults:

| Macro | Expands To |
|-------|------------|
| `workers` | "list all worker panes with status" |
| `quiet` | "kill all worker panes" |
| `again` | (repeat last command) |
| `nevermind` | "cancel the current operation" |
| `pause` | "stop listening until I say resume" |

## Potential Challenges

1. **Ambiguity with natural speech**: "Helper" might be part of a sentence. Solution: Require macros to be standalone utterances, or use a prefix ("macro helper").

2. **STT accuracy on short words**: Single-word macros may get mistranscribed. Solution: Require 2+ syllable macro names, or use distinctive words.

3. **Macro sprawl**: Users create too many, forget them. Solution: Usage tracking, "you haven't used X in 30 days" prompts.

4. **Variable extraction errors**: "Tell website session check build" - which part is session vs message? Solution: Use word boundaries, require explicit separators for ambiguous patterns.

5. **Workflow macro failures**: Step 2 fails, what happens to step 3? Solution: Stop on error, report which step failed, let user decide.

## Example Day-in-the-Life

```
# Morning setup
[User]: "Fresh start"
[System]: "Killing workers... Spawning GLM worker... Ready"

# During work
[User]: "Helper"
[System]: "Spawning GLM worker"
[User]: "Tell one fix the auth bug in login.ts"
[System]: "Sent to pane 1"

# Quick checks
[User]: "Check one"
[System]: "Pane 1: Working on auth fix, modified 2 files..."

# End of feature
[User]: "Ship it added user authentication"
[System]: "Running tests... 47 passed. Committing... Pushing..."
```

## Success Metrics

- Reduced average utterance length
- Fewer STT errors (shorter phrases = fewer mistakes)
- Increased commands per minute
- User-reported "feels faster" feedback
