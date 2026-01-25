# Multi-Agent Workflow with OpenCode

Complete guide for orchestrating multiple AI agents working together using AgentWire and OpenCode.

## Overview

Multi-agent workflows enable parallel development, specialized tasks, and coordinated effort across multiple AI coding agents.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentWire Portal                         │
│                    (User Interface)                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Voice Commands
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Orchestrator Session (Pane 0)                   │
│         Coordinates work, delegates tasks                    │
│              Type: standard / opencode-bypass                │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Delegates to
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Worker 1        │ │ Worker 2        │ │ Worker 3        │
│ (Pane 1)        │ │ (Pane 2)        │ │ (Pane 3)        │
│ Frontend Dev    │ │ Backend Dev     │ │ Testing         │
│ Type: worker    │ │ Type: worker    │ │ Type: worker    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Setup

### 1. Configure Orchestrator

```yaml
# ~/projects/myapp/.agentwire.yml
type: "standard"
roles:
  - orchestrator
voice: "default"
```

### 2. Create Orchestrator Role

```bash
cat > ~/.agentwire/roles/orchestrator.md << 'EOF'
# Orchestrator

You are the main orchestrator for a multi-agent development team.

## Responsibilities

- Coordinate work across multiple worker agents
- Delegate tasks to specialized workers
- Review and integrate work from workers
- Maintain overall project vision
- Communicate with user via voice
- Make architectural decisions

## Worker Management

When delegating tasks:
1. Specify which worker should handle the task
2. Provide clear requirements
3. Set expectations for output
4. Follow up on progress

## Available Workers

- Worker 1: Frontend development
- Worker 2: Backend development
- Worker 3: Testing and QA

## Communication

- Use voice to communicate with user
- Use send commands to delegate to workers
- Review worker outputs regularly
- Summarize progress to user

## Tools
Bash
Edit
Write
Grep

## Model
claude-3-5-sonnet-20241022
EOF
```

### 3. Create Worker Roles

```bash
# Frontend worker
cat > ~/.agentwire/roles/frontend-worker.md << 'EOF'
# Frontend Worker

You are a frontend development specialist working on focused tasks.

## Guidelines

- Execute tasks delegated by orchestrator
- Focus on UI/UX implementation
- Test all changes before reporting back
- No voice input, no questions to user
- Report completion to orchestrator

## Tools
Bash
Edit
Write

## Disallowed Tools
AskUserQuestion
EOF

# Backend worker
cat > ~/.agentwire/roles/backend-worker.md << 'EOF'
# Backend Worker

You are a backend development specialist working on focused tasks.

## Guidelines

- Execute tasks delegated by orchestrator
- Focus on API and database work
- Implement proper error handling
- No voice input, no questions to user
- Report completion to orchestrator

## Tools
Bash
Edit
Write

## Disallowed Tools
AskUserQuestion
EOF

# Testing worker
cat > ~/.agentwire/roles/testing-worker.md << 'EOF'
# Testing Worker

You are a testing and QA specialist working on focused tasks.

## Guidelines

- Execute tests delegated by orchestrator
- Identify and report bugs
- Write comprehensive tests
- No voice input, no questions to user
- Report test results to orchestrator

## Tools
Bash
Edit
Write
Grep

## Disallowed Tools
AskUserQuestion
EOF
```

## Workflow

### Step 1: Create Orchestrator Session

```bash
# Create main orchestrator session
agentwire new -s myapp

# Orchestrator uses type "standard" (maps to opencode-bypass)
```

### Step 2: Spawn Workers

```bash
# Spawn frontend worker (pane 1)
agentwire spawn --roles frontend-worker

# Spawn backend worker (pane 2)
agentwire spawn --roles backend-worker

# Spawn testing worker (pane 3)
agentwire spawn --roles testing-worker
```

Session structure:
- **Pane 0:** Orchestrator (coordinates work)
- **Pane 1:** Frontend Worker (UI implementation)
- **Pane 2:** Backend Worker (API/database)
- **Pane 3:** Testing Worker (QA/testing)

### Step 3: Start Portal

```bash
# Start portal for voice interaction
agentwire portal start

# Open browser: https://localhost:8765
```

### Step 4: Coordinated Development

Use voice commands to interact with orchestrator:

**User:** "Create a user authentication system"

**Orchestrator (voice response):**
"I'll coordinate the team. Worker 1 will create the login form, Worker 2 will implement the backend API, and Worker 3 will write tests."

**Orchestrator (actions):**
1. Sends task to Worker 1: "Create login form with email and password fields"
2. Sends task to Worker 2: "Implement authentication API with JWT tokens"
3. Sends task to Worker 3: "Write tests for authentication endpoints"

Workers work in parallel. Orchestrator monitors progress.

### Step 5: Review and Integration

When workers complete tasks:

**User:** "Review the authentication system"

**Orchestrator:**
Reviews all worker outputs, checks for consistency, integrates frontend and backend, runs comprehensive tests.

**Orchestrator (voice response):**
"Authentication system complete. Login form connected to API, all tests passing. Ready for user testing."

## Common Patterns

### Pattern 1: Feature Development

**User:** "Implement a user dashboard"

**Orchestrator delegates:**
- Worker 1: Design and implement dashboard UI
- Worker 2: Create API endpoints for dashboard data
- Worker 3: Write integration tests

Workers work in parallel. Orchestrator integrates.

### Pattern 2: Bug Fix

**User:** "Fix the bug where payments fail on mobile"

**Orchestrator analysis:**
1. Identifies frontend issue (payment form)
2. Identifies backend issue (API endpoint)

**Orchestrator delegates:**
- Worker 1: Fix payment form for mobile
- Worker 2: Debug and fix API endpoint
- Worker 3: Verify fix with tests

### Pattern 3: Performance Optimization

**User:** "Optimize the application for performance"

**Orchestrator delegates:**
- Worker 1: Optimize frontend assets, implement lazy loading
- Worker 2: Optimize database queries, add caching
- Worker 3: Benchmark and measure improvements

### Pattern 4: Security Hardening

**User:** "Audit and improve security"

**Orchestrator delegates:**
- Worker 1: Add input validation to forms
- Worker 2: Implement rate limiting, secure API
- Worker 3: Run security scans, write security tests

## Communication Protocols

### Orchestrator → Worker

```bash
# From orchestrator pane, send to worker
agentwire send --pane 1 "Implement login form with email and password fields"
agentwire send --pane 2 "Create POST /auth/login endpoint with JWT"
agentwire send --pane 3 "Write tests for authentication API"
```

### Worker → Orchestrator

Workers report completion by sending to pane 0:

```bash
# From worker pane, report back to orchestrator
agentwire send --pane 0 "Login form complete with validation"
```

### Orchestrator → User

Orchestrator uses voice to communicate with user:

```bash
# In orchestrator session
agentwire say "Frontend worker completed the login form. Backend worker is implementing the API."
```

## Advanced Scenarios

### Scenario 1: Parallel Feature Development

Multiple features developed simultaneously:

**User:** "Implement user profiles and notifications"

**Orchestrator:**
- Worker 1: User profile UI
- Worker 2: Profile API endpoints
- Worker 3: Notification system UI
- Worker 4: Notification API and background jobs

Four workers working in parallel.

### Scenario 2: Testing Pipeline

Continuous testing during development:

**User:** "Develop and test a new payment feature"

**Orchestrator:**
- Worker 1: Implement payment feature
- Worker 2: Write unit tests
- Worker 3: Run tests continuously
- Worker 4: Manual QA testing

Feedback loop: Test failures → Worker 1 fixes → Tests re-run

### Scenario 3: Code Review

Multi-agent code review:

**User:** "Review and improve the codebase"

**Orchestrator:**
- Worker 1: Review frontend code
- Worker 2: Review backend code
- Worker 3: Check for security issues
- Worker 4: Check for performance issues

Orchestrator consolidates findings and implements improvements.

### Scenario 4: Refactoring

Coordinated refactoring:

**User:** "Refactor the API to use new architecture"

**Orchestrator:**
- Worker 1: Refactor API endpoints
- Worker 2: Update database layer
- Worker 3: Update frontend API calls
- Worker 4: Update tests

Coordinated changes across entire codebase.

## Managing Workers

### Monitor Worker Progress

```bash
# Check all pane outputs
agentwire output -s myapp --pane 1  # Frontend worker
agentwire output -s myapp --pane 2  # Backend worker
agentwire output -s myapp --pane 3  # Testing worker
```

### Jump to Specific Worker

```bash
# Focus on worker 2 (backend)
agentwire jump --pane 2
```

### Kill Specific Worker

```bash
# Kill worker 1 (frontend)
agentwire kill --pane 1

# Wait for graceful shutdown
sleep 1

# Spawn new worker if needed
agentwire spawn --roles frontend-worker
```

### Resize Window for Workers

```bash
# Resize window to fit all workers
agentwire resize -s myapp
```

## Best Practices

### 1. Clear Task Delegation

**Bad:** "Fix the bugs"

**Good:** "Worker 1, fix the login form validation bug where email format isn't checked"

### 2. Parallel Work

Assign independent tasks to different workers:

**Good:**
- Worker 1: Implement user registration UI
- Worker 2: Create registration API endpoint
- Worker 3: Write registration tests

### 3. Regular Check-ins

Orchestrator should check worker progress:

```bash
# Orchestrator checks worker status
agentwire send --pane 1 "Status?"
agentwire send --pane 2 "Status?"
agentwire send --pane 3 "Status?"
```

### 4. Integration Point

Orchestrator integrates worker outputs:

**Voice response:** "Worker 1 completed the UI, Worker 2 completed the API. I'm now integrating them and running tests."

### 5. Error Handling

When worker fails:

**Orchestrator action:**
1. Review worker error output
2. Diagnose issue
3. Send clear fix instructions to worker
4. Monitor re-execution

## Troubleshooting

### Issue: Worker Not Responding

**Solution:**
```bash
# Check worker status
agentwire output --pane 1

# If stuck, kill and restart
agentwire kill --pane 1
sleep 1
agentwire spawn --roles frontend-worker
```

### Issue: Worker Makes Too Many Questions

**Solution:**
Worker roles should have `AskUserQuestion` in disallowed tools. Verify:

```bash
agentwire roles show frontend-worker
```

### Issue: Integration Conflicts

**Solution:**
Orchestrator should review both workers' outputs before integration:

```bash
# Review frontend worker output
agentwire output --pane 1

# Review backend worker output
agentwire output --pane 2

# Orchestrator integrates
agentwire send "Integrating frontend and backend changes..."
```

## Performance Tips

### 1. Optimize Task Size

Break large tasks into smaller, parallelizable subtasks:

**Large:** "Implement the entire e-commerce system"

**Better:**
- Worker 1: Product catalog
- Worker 2: Shopping cart
- Worker 3: Checkout process
- Worker 4: Order history

### 2. Minimize Context Switching

Keep workers focused on related tasks:

**Good:** Worker 1 focuses on all frontend components

**Bad:** Worker 1 switches between frontend and backend

### 3. Use Worktrees for Features

Create separate sessions for major features:

```bash
# Feature A
agentwire new -s feature-a/branch-1

# Feature B
agentwire new -s feature-b/branch-2
```

Each with its own set of workers.

## Example Session Log

```
[User, voice]: "Create a blog system with posts and comments"

[Orchestrator, voice]: "I'll coordinate the team. Worker 1 will create the blog UI, Worker 2 will implement the blog API, Worker 3 will write tests."

[Orchestrator → Worker 1]: "Create blog listing page with post cards and pagination"

[Orchestrator → Worker 2]: "Implement CRUD API for blog posts (GET, POST, PUT, DELETE)"

[Orchestrator → Worker 3]: "Write unit tests for blog API endpoints"

[Worker 1 → Orchestrator]: "Blog listing page complete with post cards and pagination"

[Worker 2 → Orchestrator]: "Blog API endpoints implemented with full CRUD operations"

[Worker 3 → Orchestrator]: "All API tests passing (12/12)"

[Orchestrator, voice]: "Blog system complete! UI connected to API, all tests passing. Ready for next feature."

[User, voice]: "Add comment system to blog posts"

[Orchestrator, voice]: "Worker 1 will add comment forms, Worker 2 will add comment API, Worker 3 will write comment tests."

... and so on
```

## Next Steps

- [Session Types Reference](../SESSION_TYPES.md) - Understanding session types
- [OpenCode Role Guide](../OPENCODE_ROLES.md) - Creating custom roles
- [Frontend Development Workflow](frontend-workflow.md) - Frontend-specific guide
- [Backend Development Workflow](backend-workflow.md) - Backend-specific guide
