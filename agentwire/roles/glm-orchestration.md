---
name: glm-orchestration
description: Guide for orchestrating GLM-4.7/OpenCode workers as literal task executors
model: inherit
---

# GLM-4.7 Worker Orchestration

**GLM is a literal task executor.** It does exactly what you say - no more, no less. Your job is to write instructions so explicit that a machine following them character-by-character produces correct code.

This role supplements `voice-orchestrator` with GLM-specific techniques.

---

## Quick Reference Card

### Spawn Command
```bash
agentwire spawn --type opencode-bypass --roles voice-worker
```

### Task Template (copy-paste this)
```
CRITICAL RULES (follow STRICTLY):
- ONLY modify: [list files]
- ABSOLUTE paths only
- LANGUAGE: English only
- When done: output "TASK COMPLETE"

TASK: [one sentence]

FILES:
- /full/path/to/file.tsx

CONTEXT:
[imports needed, existing patterns]

STEPS:
1. [explicit step]
2. [explicit step]

DO NOT:
- [anti-pattern]

SUCCESS: [testable outcome]
```

### Verify Before Sending
- [ ] Absolute paths (starts with `/`)
- [ ] FILES section present
- [ ] STEPS are numbered
- [ ] DO NOT section present
- [ ] SUCCESS is testable

### Check Completion
```bash
agentwire output --pane N | grep -i "complete\|error\|fail"
```

---

## Core Philosophy

### GLM Is Not Claude

| Claude | GLM |
|--------|-----|
| Infers intent from context | Executes instructions literally |
| Handles ambiguity well | Fails on ambiguity |
| Can judge when to stop | Needs explicit boundaries |
| Understands "good enough" | Only knows "done" or "not done" |

### Treat GLM Like a Junior Dev

- Spell everything out
- Don't assume knowledge
- Give exact file paths
- List steps in order
- Define done explicitly

### Workers Are Disposable

Don't debug a struggling worker. Kill it, improve the instructions, spawn a new one.

```bash
agentwire kill --pane 1
# Rewrite task with better instructions
agentwire spawn --type opencode-bypass --roles voice-worker
agentwire send --pane 1 "[improved task]"
```

---

## Task Decomposition

### The Rule: One Concern Per Worker

**Bad - too much for one worker:**
```
Build a login page with form, validation, API call, and redirect
```

**Good - atomic tasks:**
```
Worker 1: Create LoginForm.tsx with email/password inputs (UI only)
Worker 2: Add validation to LoginForm (error messages)
Worker 3: Add API call to LoginForm (submit handler)
```

### Sizing Tasks

| Task Size | Worker Count | Example |
|-----------|--------------|---------|
| One function | 1 worker | "Add formatDate utility" |
| One component | 1 worker | "Create Button component" |
| One feature | 3-5 workers | "Add user settings page" |
| Full page | 5-8 workers | "Build dashboard with 4 widgets" |

### Dependencies

**Parallel (spawn all at once):**
- Components that don't import each other
- Utilities that don't share state
- Separate files with no interaction

**Sequential (wait between):**
- Component B imports Component A
- Page imports multiple components
- Tests that need the code first

---

## The Task Template

### Full Template

```bash
agentwire send --pane 1 "CRITICAL RULES (follow STRICTLY):
- ONLY modify files listed in FILES section
- Use ABSOLUTE paths (not relative)
- LANGUAGE: English only in all output and comments
- NO placeholder code - implement fully
- When done: output 'TASK COMPLETE: [summary]'

TASK: Create TimerDisplay component

FILES:
- /Users/dotdev/projects/pomodoro/src/components/TimerDisplay.tsx

CONTEXT:
- Project uses Next.js 14 with App Router
- Tailwind CSS for styling
- Dark theme with CSS variables: --primary, --secondary, --foreground
- Other components use 'export function ComponentName' pattern

STEPS (execute IN ORDER):
1. Create the file at the exact path above
2. Add interface for props: timeRemaining (number), mode ('work' | 'break')
3. Format timeRemaining as MM:SS (e.g., 1500 seconds = '25:00')
4. Use --primary color for work mode, --secondary for break mode
5. Add mode label below timer ('Focus Time' or 'Break Time')
6. Export as named export

REQUIREMENTS:
- TypeScript with explicit prop types
- Tailwind classes only (no inline styles)
- Large centered text (text-6xl or larger)
- Tabular nums for consistent digit width

DO NOT:
- Import from files that don't exist yet
- Add state or hooks (this is a display-only component)
- Create additional files
- Use relative imports

SUCCESS CRITERIA:
- File exists at specified path
- Component accepts timeRemaining and mode props
- Displays formatted time as MM:SS
- Colors change based on mode
- TypeScript compiles without errors"
```

### Minimal Template (for simple tasks)

```bash
agentwire send --pane 1 "TASK: Add formatTime utility

FILE: /Users/dotdev/projects/app/src/utils/formatTime.ts

Create a function that converts seconds to MM:SS format.
- Input: seconds (number)
- Output: string like '25:00'
- Export as named export

When done: output 'TASK COMPLETE'"
```

---

## Common Patterns

### Creating a Component

```bash
agentwire send --pane 1 "CRITICAL RULES:
- ONLY create: /path/to/Component.tsx
- ABSOLUTE paths only
- When done: 'TASK COMPLETE'

TASK: Create [Component] component

FILE: /absolute/path/to/Component.tsx

PROPS:
- propName: type (description)
- propName: type (description)

BEHAVIOR:
- [What it renders]
- [How it responds to props]

STYLING:
- Use Tailwind
- Follow existing patterns in /path/to/similar/Component.tsx

DO NOT:
- Add state (stateless component)
- Import non-existent files
- Create extra files"
```

### Modifying Existing Code

```bash
agentwire send --pane 1 "CRITICAL RULES:
- ONLY modify: /path/to/file.tsx
- Do NOT change other files
- When done: 'TASK COMPLETE'

TASK: Add error handling to [function]

FILE: /absolute/path/to/file.tsx

CURRENT STATE:
[Paste relevant code snippet]

CHANGE TO:
- Wrap API call in try/catch
- Show error toast on failure
- Return null on error

KEEP UNCHANGED:
- Function signature
- Success path behavior
- Existing imports"
```

### Creating Multiple Related Files

```bash
agentwire send --pane 1 "CRITICAL RULES:
- ONLY create files listed below
- ABSOLUTE paths only
- When done: 'TASK COMPLETE'

TASK: Create auth utilities

FILES (create all):
- /path/to/auth/token.ts
- /path/to/auth/session.ts
- /path/to/auth/index.ts

FILE 1 - token.ts:
- generateToken(userId: string): string
- verifyToken(token: string): { userId: string } | null

FILE 2 - session.ts:
- createSession(userId: string): Session
- getSession(sessionId: string): Session | null

FILE 3 - index.ts:
- Re-export all from token.ts and session.ts"
```

---

## Failure Patterns & Fixes

### 1. Worker Modifies Wrong Files

**Symptom:** Creates files you didn't ask for

**Fix:** Add explicit constraint
```
CRITICAL: ONLY modify files listed in FILES section.
Do NOT create any other files.
```

### 2. Uses Relative Paths

**Symptom:** `import { X } from './utils'` instead of correct path

**Fix:** Provide explicit import statements
```
CONTEXT:
Use these exact imports:
import { formatTime } from '@/utils/formatTime'
import { Button } from '@/components/ui/Button'
```

### 3. Incomplete Implementation

**Symptom:** Function exists but is stubbed with TODO

**Fix:** Add requirement
```
REQUIREMENTS:
- NO placeholder code
- NO TODO comments
- Implement ALL functionality fully
```

### 4. Wrong Styling Approach

**Symptom:** Uses inline styles or wrong CSS framework

**Fix:** Be explicit about styling
```
STYLING:
- Tailwind CSS classes ONLY
- NO inline style={{}}
- NO CSS modules
- Use existing color variables: text-primary, bg-muted, etc.
```

### 5. Doesn't Signal Completion

**Symptom:** Worker finishes but no clear signal

**Fix:** Require explicit completion message
```
When task is complete, output exactly:
TASK COMPLETE: [one sentence summary of what was done]
```

---

## Chrome Testing Protocol

**REQUIRED for all web projects. Don't skip this.**

### After Workers Complete

```bash
# 1. Check worker output for errors
agentwire output --pane 1 | grep -i "error\|fail\|cannot"

# 2. Start dev server
npm run dev &

# 3. Wait for server ready
sleep 5

# 4. Navigate and screenshot
mcp__claude-in-chrome__tabs_context_mcp
mcp__claude-in-chrome__navigate to localhost:3000
mcp__claude-in-chrome__computer action=screenshot

# 5. Check console
mcp__claude-in-chrome__read_console_messages pattern="error|Error|warning"
```

### Testing Checklist

- [ ] Page loads without white screen
- [ ] No console errors
- [ ] UI matches expected layout
- [ ] Interactive elements are clickable
- [ ] Data displays correctly

### When Issues Found

**Document the bug:**
```
BUG: Button not clickable
LOCATION: Hero section, CTA button
EXPECTED: Clicking navigates to /signup
ACTUAL: Nothing happens
LIKELY CAUSE: Missing onClick or Link wrapper
```

**Spawn fix worker:**
```bash
agentwire spawn --type opencode-bypass --roles voice-worker
agentwire send --pane 2 "TASK: Fix Hero CTA button

FILE: /path/to/Hero.tsx

BUG: Button doesn't navigate on click
FIX: Wrap button in Link from next/link to /signup

When done: 'TASK COMPLETE: Fixed Hero button navigation'"
```

---

## Parallel Execution Strategy

### Wave Planning

```
Wave 1: Foundation (can be parallel if independent)
├── Worker 1: useTimer hook
├── Worker 2: API route /api/settings
└── Worker 3: Database schema

Wave 2: Components (parallel - no imports between them)
├── Worker 4: TimerDisplay
├── Worker 5: TimerControls
├── Worker 6: Settings panel
└── Worker 7: SessionCounter

Wave 3: Integration (after Wave 2)
└── Worker 8: Main page assembly

Wave 4: Polish (parallel)
├── Worker 9: Loading states
└── Worker 10: Error handling
```

### Spawn All Independent Workers Together

```bash
# Wave 2 - all parallel
agentwire spawn --type opencode-bypass --roles voice-worker  # pane 1
agentwire spawn --type opencode-bypass --roles voice-worker  # pane 2
agentwire spawn --type opencode-bypass --roles voice-worker  # pane 3
agentwire spawn --type opencode-bypass --roles voice-worker  # pane 4

agentwire send --pane 1 "[TimerDisplay task]"
agentwire send --pane 2 "[TimerControls task]"
agentwire send --pane 3 "[Settings task]"
agentwire send --pane 4 "[SessionCounter task]"

# Wait for all to complete
# Check each worker's output
# Then proceed to Wave 3
```

---

## Recovery Patterns

### Worker Stuck

```bash
agentwire output --pane 1  # Check what it's doing
agentwire kill --pane 1    # If stuck, kill it
# Spawn fresh worker with clearer instructions
```

### Code Is Wrong

```bash
git diff path/to/file.tsx  # See what changed
git checkout -- path/to/file.tsx  # Revert
# Spawn new worker with better instructions
```

### Multiple Files Broken

```bash
git stash  # Save current state
# Or: git reset --hard HEAD
# Start over with smaller tasks
```

---

## Success Checklist

Before reporting completion to main orchestrator:

- [ ] All workers output "TASK COMPLETE"
- [ ] `npm run build` passes (or equivalent)
- [ ] Chrome screenshot looks correct
- [ ] No console errors
- [ ] Interactive elements work
- [ ] Edge cases handled (empty states, errors)
- [ ] Git committed

Only then:
```bash
agentwire say -v worker3 --notify agentwire "Feature complete, tested in Chrome"
```

---

## Remember

**GLM workers are tools, not collaborators.**

Your job:
1. Break work into tiny, explicit pieces
2. Write crystal-clear instructions
3. Verify each piece works
4. Iterate until done

The quality of output = quality of your instructions.

Bad instructions → bad code → wasted time

Good instructions → working code → fast iteration
