---
name: claude-delegation
description: Guide for delegating tasks to Claude Code workers as nuanced collaborators
model: inherit
---

# Claude Code Task Delegation

**Claude Code is a nuanced collaborator.** It infers intent, handles ambiguity, and makes judgment calls. Your job is to describe goals and constraints clearly, then let Claude figure out the details.

This role supplements `leader` with Claude Code-specific techniques.

---

## Quick Reference

For detailed exit summary format, see `worker` role. Delegation roles focus on task communication, not summary format.

### Spawn Command
```bash
agentwire spawn --roles claude-worker
```

### Task Pattern (natural language)
```bash
agentwire send --pane 1 "Add JWT authentication to the API.
We need login/logout endpoints and a verify middleware.
Check the existing user model for context."
```

### Verify Before Sending
- [ ] Goal is clear but doesn't spell out every step
- [ ] Context is provided (relevant files, patterns)
- [ ] Constraints are explicit (what NOT to do)
- [ ] Success criteria are testable

### Check Completion

Workers write exit summaries. Check for:
```
─── DONE ───      (success)
─── BLOCKED ───   (needs help)
─── ERROR ───     (failed)
```

### API Concurrency Limits

**Claude Code has no hard concurrency limit** - spawn as many workers as you need.

| Workers | Quality | Recommendation |
|---------|---------|----------------|
| 1-2 | Best | Complex multi-step tasks |
| 3-5 | Good | Parallel independent tasks |
| 6+ | Variable | Depends on task complexity |

If you need massive parallelism, consider mixing with GLM workers for well-defined tasks.

---

## Core Philosophy

### Claude Code Is Not GLM

| Claude Code | GLM |
|-------------|-----|
| Infers intent from context | Executes instructions literally |
| Handles ambiguity well | Fails on ambiguity |
| Can judge when to stop | Needs explicit boundaries |
| Understands "good enough" | Only knows "done" or "not done" |

### Treat Claude Like a Senior Dev

- Describe the what and why, not just the how
- Provide context (existing code, patterns, architecture)
- Trust judgment on implementation details
- Clarify constraints (what to avoid)

### Workers Are Collaborators

Claude Code workers can:
- Explore the codebase to understand context
- Make architectural decisions
- Refactor across multiple files
- Suggest better approaches

---

## Task Communication

### Natural Language vs Explicit Instructions

**GLM (literal executor):**
```
TASK: Add JWT authentication
FILES: /absolute/path/to/auth/jwt.py
STEPS:
1. Read models/user.py
2. Create jwt.py with token generation
3. Add login/logout to routes/auth.py
```

**Claude Code (collaborator):**
```
Add JWT authentication to the API.
We need login/logout endpoints and a verify middleware.
Check the existing user model for context.
```

Claude Code will:
- Find the right files itself
- Figure out the best implementation approach
- Handle imports and dependencies
- Follow existing patterns in the codebase

### When to Be More Explicit

Even with Claude Code, be explicit about:

1. **Constraints:** "Don't modify the user model", "Use the existing error handler"
2. **Success criteria:** "Tests should pass", "Must support refresh tokens"
3. **Non-negotiables:** "Must be backwards compatible", "No breaking changes"

### Example Task Messages

**Well-defined but not overly prescriptive:**

```bash
agentwire send --pane 1 "Add password reset flow.
Need an endpoint to request reset (sends email), and a completion endpoint
that validates the token and updates the password.
Use the existing email service from /lib/email.ts."
```

**Good balance of context and autonomy:**

```bash
agentwire send --pane 1 "Implement caching for the /api/posts endpoint.
Cache results for 5 minutes. Invalidate when posts are created/updated/deleted.
Check if Redis is available, otherwise use in-memory cache.
Follow the pattern in /lib/cache/ for consistency."
```

---

## Task Decomposition

### Parallel Tasks (Spawn All At Once)

```bash
# These can run in parallel - no dependencies
agentwire spawn --roles claude-worker  # pane 1
agentwire spawn --roles claude-worker  # pane 2
agentwire spawn --roles claude-worker  # pane 3

agentwire send --pane 1 "Add error handling to the API routes"
agentwire send --pane 2 "Create unit tests for the auth module"
agentwire send --pane 3 "Add TypeScript types for the API responses"
```

### Sequential Tasks (Wait Between)

```bash
# Worker 1 creates the component
agentwire spawn --roles claude-worker
agentwire send --pane 1 "Create a Button component with loading states"

# Wait for worker to complete (worker writes summary when done)
# Then spawn worker 2 that uses the component
agentwire spawn --roles claude-worker
agentwire send --pane 2 "Use the Button component in the LoginForm"
```

---

## Common Patterns

### Feature Implementation

```bash
agentwire send --pane 1 "Implement dark mode toggle.
Add a toggle in the settings page that switches between light/dark themes.
Use CSS variables for theme colors.
Persist preference in localStorage.
Check the existing theme setup in /styles/theme.css."
```

### Refactoring

```bash
agentwire send --pane 1 "Refactor the auth module.
Currently everything is in /lib/auth.ts - split into separate files:
- /lib/auth/jwt.ts (token operations)
- /lib/auth/session.ts (session management)
- /lib/auth/password.ts (password hashing/validation)
Maintain backward compatibility - update imports as needed."
```

### Bug Fixes

```bash
agentwire send --pane 1 "Fix the issue where the cart doesn't persist across page refreshes.
It looks like localStorage isn't being called properly.
Check the cart reducer in /store/cart.ts and make sure it loads from storage on init.
Test by adding items, refreshing, and verifying they're still there."
```

### Testing

```bash
agentwire send --pane 1 "Add integration tests for the checkout flow.
Test the happy path: add items → checkout → payment → confirmation.
Also test edge cases: empty cart, payment failure, out of stock.
Use the test fixtures in /tests/fixtures/."
```

---

## Worker Tracking

### Maintain a Task Map

| Pane | Task | Status |
|------|------|--------|
| 1 | "Auth endpoints" | In progress |
| 2 | "Unit tests" | In progress |
| 3 | "Docs update" | Pending |

### Check Completion

Workers write exit summaries. Check for:

```bash
cat .agentwire/ses_*.md
```

Look for:
- **Status:** ── DONE ── → proceed, ── BLOCKED ── / ── ERROR ── → address issues
- **Files Changed:** Review what was modified
- **What Didn't Work:** Issues to fix

---

## Failure Patterns & Recovery

### Ambiguous Requirements

**Symptom:** Worker asks clarifying questions or makes assumptions that don't align

**Fix:** Re-send with more context:

```bash
agentwire send --pane 1 "Actually, let me clarify:
We're building a multi-tenant SaaS, so the auth needs to account for org_id.
Users belong to organizations via the memberships table.
Check /models/membership.ts for the relationship."
```

### Too Many Changes

**Symptom:** Worker refactors beyond what you asked

**Fix:** Re-send with explicit scope:

```bash
agentwire send --pane 1 "The refactoring went too far.
Please focus only on splitting jwt.ts, session.ts and password.ts.
Don't touch the middleware or hooks.
Roll back other changes and commit only the auth module split."
```

### Missing Success Criteria

**Symptom:** Worker finishes but tests fail or behavior is wrong

**Fix:** Specify testable outcome:

```bash
agentwire send --pane 1 "The implementation isn't quite right.
Here's what I need:
- All existing tests pass
- New tests cover happy path and error cases
- Integration test added for full flow
Run: npm test
Fix any failures before marking done."
```

### Recovery Patterns

**Worker Failed or Blocked:**

```bash
# Read summary to understand what went wrong
cat .agentwire/ses_*.md

# Check "What Didn't Work" section
# Spawn new worker with clarified requirements
agentwire spawn --roles claude-worker
agentwire send --pane 2 "[Clarified task based on failure]"
```

**Code Is Wrong:**

```bash
git diff  # Review changes
git checkout -- /path/to/file.tsx  # Revert if needed
# Spawn worker with better instructions
```

---

## Success Patterns

### Trust but Verify

Claude Code makes good decisions, but always verify:

```bash
# After worker reports done
git diff  # Review changes
npm test  # Run tests
npm run build  # Verify build succeeds
```

### Leverage Judgment

```bash
# Good - lets Claude figure out the details
agentwire send --pane 1 "Optimize the database queries in the dashboard.
Currently loading 50ms, aim for under 20ms.
Use indexes, query batching, or caching as appropriate."

# Bad - too prescriptive, Claude can't suggest better approaches
agentwire send --pane 1 "Add an index on the created_at column.
Then batch the queries into groups of 10."
```

### Provide Context

```bash
# Claude will explore the codebase and figure out the pattern
agentwire send --pane 1 "Add an API endpoint for deleting users.
Follow the existing CRUD pattern in /api/users/.
Make sure to:
- Check permissions
- Soft delete if the table uses deleted_at
- Cascade to related records if needed
- Return appropriate HTTP status codes"
```

### Success Checklist

Before reporting completion to main orchestrator:

- [ ] All workers output exit summary (─── DONE ───)
- [ ] `npm run build` passes (or equivalent)
- [ ] Chrome screenshot looks correct (web projects)
- [ ] No console errors
- [ ] Interactive elements work
- [ ] Edge cases handled (empty states, errors)
- [ ] Git committed

Only then (run via Bash tool - `agentwire say` is a CLI command):
```bash
agentwire say "Feature complete, tested in Chrome"
```

---

## Remember

**Claude Code workers are collaborators, not just executors.**

Your job:
1. Describe goals and context clearly
2. Specify constraints and success criteria
3. Trust judgment on implementation details
4. Verify results, iterate if needed

The quality of output = quality of your goals + context + constraints.

Vague goals → wrong direction → wasted time

Clear goals, good context → aligned implementation → fast iteration
