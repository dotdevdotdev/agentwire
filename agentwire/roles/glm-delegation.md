---
name: glm-delegation
description: Guide for delegating tasks to GLM-4.7/OpenCode workers as focused executors
model: inherit
---

# GLM-4.7 Task Delegation

**GLM is a focused task executor.** It uses all its capabilities to complete tasks but needs clear guidance on goals and constraints. Your job is to provide clear goals and explicit constraints, then let GLM figure out the details.

This role supplements `leader` with GLM-specific techniques.

---

## Quick Reference Card

### Spawn Command
```bash
agentwire spawn --type opencode-bypass --roles glm-worker
```

### Task Template (copy-paste this)
```
CRITICAL RULES (follow STRICTLY):
- ONLY modify: [list files]
- ABSOLUTE paths only
- LANGUAGE: English only
- Output exit summary when done

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

Workers output structured exit summaries. Look for:
```
─── DONE ───      (success)
─── BLOCKED ───   (needs help)
─── ERROR ───     (failed)
```

### API Concurrency Limits (CRITICAL)

**GLM/Z.ai supports max 3 concurrent requests, but quality degrades at 3.**

| Workers | Quality | Recommendation |
|---------|---------|----------------|
| 1 | Best | Complex multi-step tasks |
| 2 | Good | **Standard tasks (use this)** |
| 3 | ~50% degraded | Avoid |

**Rule: Spawn max 2 GLM workers at a time.**

If you need more parallelism, mix worker types:
- 2 GLM workers for execution tasks
- Claude workers for judgment-heavy tasks (no limit)

---

## Core Philosophy

### GLM vs Claude: Communication Style

| Claude | GLM |
|--------|-----|
| Infers intent from minimal context | Benefits from explicit context |
| Handles ambiguity well | Needs clearer boundaries |
| Can judge "good enough" vs "perfect" | May need guidance on when to stop |
| Natural language tasks work well | Benefits from structured requirements |
| Standard web search tools | Uses `zai-web-search_webSearchPrime` for web research |

**Both agents can:** Use all their tools, make autonomous decisions, research, explore codebase, and complete tasks. The difference is communication style and tool access, not capabilities.

### Treat GLM Like a Junior Dev

- Spell everything out
- Don't assume knowledge
- Give exact file paths
- List steps in order
- Define done explicitly

### Workers Are Disposable

Workers auto-exit when idle. If a worker's summary shows failure or blocking issues, just spawn a new one with improved instructions.

```bash
# Read failed worker's summary
cat .agentwire/worker-1.md

# Spawn new worker with better instructions
agentwire spawn --type opencode-bypass --roles glm-worker
agentwire send --pane 1 "[improved task based on what failed]"
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

**Remember: Max 2 GLM workers due to API limits.** Batch related work into fewer workers.

| Task Size | Workers | Strategy |
|-----------|---------|----------|
| One function | 1 | Single worker |
| One component | 1 | Single worker |
| One feature | 2 | Parallel workers, batch related files |
| Full page | 3 waves | Sequential waves of 2 workers each |

**Example - Building 6 components:**
```
# WRONG - exceeds limit
agentwire spawn x6  # Too many concurrent

# RIGHT - batch into 3 waves of 2
Wave 1: 2 workers (Hero + Features)
Wave 2: 2 workers (Pricing + Footer)
Wave 3: 2 workers (Nav + CTA)
```

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
- Output exit summary when done (see worker role for format)

TASK: Create TimerDisplay component

FILES:
- /home/user/projects/pomodoro/src/components/TimerDisplay.tsx

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

FILE: /home/user/projects/myapp/src/utils/formatTime.ts

Create a function that converts seconds to MM:SS format.
- Input: seconds (number)
- Output: string like '25:00'
- Export as named export

Output exit summary when done"
```

---

## Common Patterns

### Creating a Component

```bash
agentwire send --pane 1 "CRITICAL RULES:
- ONLY create: /path/to/Component.tsx
- ABSOLUTE paths only
- Output exit summary when done

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
- Output exit summary when done

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
- Output exit summary when done

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

**Fix:** Worker roles now include exit summary format. If still missing, add:
```
When done, output your exit summary (see worker role for ─── DONE ─── format)
```

---

## Chrome Testing Protocol

**REQUIRED for all web projects. Don't skip this.**

### After Workers Complete

```bash
# 1. Read worker summaries for status
cat .agentwire/worker-1.md

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
agentwire spawn --type opencode-bypass --roles glm-worker
agentwire send --pane 2 "TASK: Fix Hero CTA button

FILE: /path/to/Hero.tsx

BUG: Button doesn't navigate on click
FIX: Wrap button in Link from next/link to /signup

Output exit summary when done"
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
agentwire spawn --type opencode-bypass --roles glm-worker  # pane 1
agentwire spawn --type opencode-bypass --roles glm-worker  # pane 2
agentwire spawn --type opencode-bypass --roles glm-worker  # pane 3
agentwire spawn --type opencode-bypass --roles glm-worker  # pane 4

agentwire send --pane 1 "[TimerDisplay task]"
agentwire send --pane 2 "[TimerControls task]"
agentwire send --pane 3 "[Settings task]"
agentwire send --pane 4 "[SessionCounter task]"

# Workers auto-exit when done
# Read summaries: cat .agentwire/worker-{1,2,3,4}.md
# Then proceed to Wave 3
```

---

## Recovery Patterns

### Worker Failed or Blocked

Workers auto-exit. Read their summary to understand what went wrong:

```bash
cat .agentwire/worker-1.md
# Check "What Didn't Work" section
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

- [ ] All workers output exit summary (─── DONE ───)
- [ ] `npm run build` passes (or equivalent)
- [ ] Chrome screenshot looks correct
- [ ] No console errors
- [ ] Interactive elements work
- [ ] Edge cases handled (empty states, errors)
- [ ] Git committed

Only then:
```bash
agentwire say -v may --notify agentwire "Feature complete, tested in Chrome"
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
