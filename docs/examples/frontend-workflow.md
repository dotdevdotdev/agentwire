# Frontend Development Workflow with OpenCode

Complete guide for frontend development using OpenCode with AgentWire.

## Setup

### 1. Configure Project

```yaml
# ~/projects/my-frontend-app/.agentwire.yml
type: "standard"
roles:
  - frontend-developer
voice: "dotdev"
```

### 2. Create Frontend Developer Role

```bash
cat > ~/.agentwire/roles/frontend-developer.md << 'EOF'
# Frontend Developer

You are an expert frontend developer specializing in React, TypeScript, and modern web development.

## Guidelines

- Always use TypeScript for type safety
- Follow React best practices and patterns
- Write clean, component-based code
- Test changes in browser before committing
- Use modern CSS (flexbox, grid, custom properties)
- Optimize for performance (lazy loading, code splitting)

## Tools
Bash
Edit
Write
Grep

## Disallowed Tools
AskUserQuestion

## Model
claude-3-5-sonnet-20241022
EOF
```

## Workflow

### Step 1: Create Session

```bash
# Create frontend development session
agentwire new -s frontend-app

# Or specify role explicitly
agentwire new -s frontend-app --roles frontend-developer
```

### Step 2: Start Portal

```bash
# Start the portal for voice interaction
agentwire portal start

# Open browser: https://localhost:8765
```

### Step 3: Voice-First Development

Use push-to-talk in the browser to interact:

**"Create a new React component for a user profile card"**

OpenCode will:
1. Generate the component
2. Create necessary files
3. Add TypeScript types
4. Implement best practices

**"Add responsive styling using Tailwind CSS"**

OpenCode will:
1. Install Tailwind dependencies
2. Configure Tailwind
3. Add responsive classes

### Step 4: Parallel Work with Workers

```bash
# Spawn worker for CSS tasks
agentwire spawn --roles worker

# Spawn another worker for testing
agentwire spawn --roles worker
```

**Orchestrator commands via voice:**

**"Worker 1, update the CSS to use flexbox layout"**

**"Worker 2, write unit tests for the profile component"**

### Step 5: Testing and Deployment

**"Run the development server and test the component"**

OpenCode will:
1. Start dev server
2. Open browser
3. Provide testing guidance

**"Build for production and check for issues"**

OpenCode will:
1. Run production build
2. Check bundle size
3. Report any errors

## Common Tasks

### Create New Component

**Voice command:** "Create a reusable Button component with variants"

OpenCode will:
1. Create `src/components/Button.tsx`
2. Add TypeScript interfaces
3. Implement variants (primary, secondary, ghost)
4. Add Storybook stories

### Add New Feature

**Voice command:** "Add user authentication with login form"

OpenCode will:
1. Set up authentication context
2. Create login form component
3. Add form validation
4. Integrate with backend API
5. Handle loading/error states

### Fix Bug

**Voice command:** "Fix the bug where the mobile menu doesn't close"

OpenCode will:
1. Analyze the issue
2. Identify root cause
3. Implement fix
4. Test on mobile viewport
5. Add regression test

### Code Refactoring

**Voice command:** "Refactor the API client to use axios interceptors"

OpenCode will:
1. Analyze current implementation
2. Design new architecture
3. Implement interceptors
4. Update all API calls
5. Test functionality

## Advanced Workflows

### Feature Branch Development

```bash
# Create session for new feature
agentwire new -s frontend-app/feature-user-dashboard

# This creates a worktree on feature-user-dashboard branch
# Main session continues on main branch
```

**Voice command:** "Implement user dashboard with charts"

OpenCode will:
1. Design dashboard layout
2. Integrate charting library
3. Fetch data from API
4. Create responsive layout
5. Add animations

### Code Review

```bash
# Fork session for code review
agentwire fork -s frontend-app -b code-review
```

**Voice command:** "Review this pull request and suggest improvements"

OpenCode will:
1. Analyze code changes
2. Check for best practices
3. Suggest improvements
4. Identify potential bugs
5. Review TypeScript types

### Performance Optimization

**Voice command:** "Optimize the app for performance"

OpenCode will:
1. Analyze bundle size
2. Identify large dependencies
3. Implement code splitting
4. Add lazy loading
5. Optimize images
6. Implement caching strategy

## Troubleshooting

### Issue: TypeScript Errors

**Voice command:** "Fix all TypeScript errors in the codebase"

OpenCode will:
1. Run TypeScript compiler
2. Identify all errors
3. Fix errors systematically
4. Verify fixes

### Issue: Build Fails

**Voice command:** "Debug why the production build is failing"

OpenCode will:
1. Run build command
2. Analyze error messages
3. Identify root cause
4. Implement fix
5. Test build again

### Issue: Tests Failing

**Voice command:** "Fix all failing tests"

OpenCode will:
1. Run test suite
2. Analyze failures
3. Fix broken tests
4. Ensure all tests pass

## Best Practices

### 1. Use Voice for Complex Tasks

Voice commands are best for:
- High-level requirements
- Architecture decisions
- Refactoring tasks
- Bug fixes
- Feature implementations

### 2. Use Text for Quick Commands

CLI commands are best for:
- Quick edits
- Running tests
- Checking status
- Session management

### 3. Delegate to Workers

Use workers for:
- Parallel task execution
- Focused development
- Testing
- Documentation

### 4. Use Worktrees for Parallel Features

Worktrees enable:
- Multiple features in parallel
- Isolated development
- Easy branch switching
- Reduced context switching

## Example Project Structure

After following this workflow, your project might look like:

```
my-frontend-app/
├── src/
│   ├── components/
│   │   ├── Button.tsx
│   │   ├── UserProfile.tsx
│   │   └── index.ts
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   └── Settings.tsx
│   ├── api/
│   │   └── client.ts
│   └── App.tsx
├── tests/
│   ├── components/
│   │   └── Button.test.tsx
│   └── api/
│       └── client.test.ts
├── .agentwire.yml
├── package.json
└── tsconfig.json
```

## Session Management

```bash
# List all sessions
agentwire list

# Attach to specific session
tmux attach -t frontend-app

# Kill session when done
agentwire kill -s frontend-app
```

## Next Steps

- [Session Types Reference](../SESSION_TYPES.md) - Understanding session types
- [OpenCode Role Guide](../OPENCODE_ROLES.md) - Creating custom roles
- [Backend Development Workflow](backend-workflow.md) - Backend development guide
- [Multi-Agent Workflow](multi-agent-workflow.md) - Coordinated workflows
