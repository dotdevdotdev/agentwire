# Backend Development Workflow with OpenCode

Complete guide for backend development using OpenCode with AgentWire.

## Setup

### 1. Configure Project

```yaml
# ~/projects/my-backend-api/.agentwire.yml
type: "standard"
roles:
  - backend-developer
voice: "dotdev"
```

### 2. Create Backend Developer Role

```bash
cat > ~/.agentwire/roles/backend-developer.md << 'EOF'
# Backend Developer

You are an expert backend developer specializing in API design, databases, and server-side logic.

## Guidelines

- Design RESTful APIs with proper HTTP methods
- Implement proper error handling and logging
- Use database migrations for schema changes
- Write unit and integration tests
- Follow security best practices (input validation, authentication)
- Document API endpoints
- Optimize database queries
- Implement proper caching strategies

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
# Create backend development session
agentwire new -s backend-api

# Or specify role explicitly
agentwire new -s backend-api --roles backend-developer
```

### Step 2: Start Portal

```bash
# Start the portal for voice interaction
agentwire portal start

# Open browser: https://localhost:8765
```

### Step 3: Voice-First Development

Use push-to-talk in the browser to interact:

**"Create a REST API for user management"**

OpenCode will:
1. Design API endpoints
2. Create project structure
3. Implement routes
4. Add database models
5. Implement authentication
6. Add validation
7. Write tests

**"Add PostgreSQL database with migrations"**

OpenCode will:
1. Install database dependencies
2. Configure database connection
3. Create migration files
4. Set up ORM/models
5. Add environment variables

### Step 4: Parallel Work with Workers

```bash
# Spawn worker for database tasks
agentwire spawn --roles worker

# Spawn another worker for testing
agentwire spawn --roles worker
```

**Orchestrator commands via voice:**

**"Worker 1, create database migrations for new fields"**

**"Worker 2, write API tests for authentication endpoints"**

### Step 5: Testing and Deployment

**"Run the API server and test endpoints"**

OpenCode will:
1. Start development server
2. Run tests
3. Provide curl examples
4. Verify functionality

**"Deploy to staging environment"**

OpenCode will:
1. Run deployment scripts
2. Verify deployment
3. Run smoke tests
4. Check health endpoint

## Common Tasks

### Create New API Endpoint

**Voice command:** "Create API endpoint for user registration"

OpenCode will:
1. Design endpoint structure
2. Create route handler
3. Implement request validation
4. Add database operations
5. Handle errors
6. Add authentication middleware
7. Write tests

### Database Operations

**Voice command:** "Add a migration to add email verification field to users table"

OpenCode will:
1. Create migration file
2. Write SQL changes
3. Add rollback migration
4. Update ORM model
5. Create index if needed

### Authentication & Authorization

**Voice command:** "Implement JWT authentication for protected routes"

OpenCode will:
1. Set up JWT library
2. Implement login endpoint
3. Create middleware
4. Add token refresh logic
5. Handle token expiration
6. Write security tests

### Error Handling

**Voice command:** "Add comprehensive error handling to all API endpoints"

OpenCode will:
1. Create error classes
2. Implement error middleware
3. Add proper HTTP status codes
4. Log errors appropriately
5. Return user-friendly messages

## Advanced Workflows

### Microservices Architecture

```bash
# Create session for user service
agentwire new -s user-service

# Create session for payment service
agentwire new -s payment-service
```

**Voice command (user-service):** "Create user management API with profile endpoints"

**Voice command (payment-service):** "Create payment processing API with Stripe integration"

### API Documentation

**Voice command:** "Generate OpenAPI documentation for all endpoints"

OpenCode will:
1. Analyze route definitions
2. Generate OpenAPI spec
3. Add request/response schemas
4. Document authentication
5. Set up Swagger UI

### Database Optimization

**Voice command:** "Optimize database queries for performance"

OpenCode will:
1. Analyze slow queries
2. Add appropriate indexes
3. Implement query optimization
4. Add caching layer
5. Monitor performance

### CI/CD Pipeline

**Voice command:** "Set up GitHub Actions for automated testing and deployment"

OpenCode will:
1. Create workflow files
2. Set up test jobs
3. Configure deployment jobs
4. Add environment variables
5. Set up secrets

## Troubleshooting

### Issue: Database Connection Errors

**Voice command:** "Debug database connection issues"

OpenCode will:
1. Check connection string
2. Verify credentials
3. Test connectivity
4. Check firewall rules
5. Review logs

### Issue: API Performance Issues

**Voice command:** "Analyze and fix slow API endpoints"

OpenCode will:
1. Profile API endpoints
2. Identify bottlenecks
3. Optimize queries
4. Add caching
5. Implement pagination

### Issue: Authentication Failures

**Voice command:** "Debug JWT authentication failures"

OpenCode will:
1. Check token generation
2. Verify token validation
3. Review middleware
4. Test authentication flow
5. Fix security issues

## Best Practices

### 1. API Design

- Use proper HTTP methods (GET, POST, PUT, DELETE)
- Implement versioning (/api/v1/)
- Use consistent naming conventions
- Return appropriate status codes
- Implement pagination for lists

### 2. Database Operations

- Always use migrations
- Add indexes for frequently queried fields
- Use transactions for multi-step operations
- Implement proper connection pooling
- Add database backups

### 3. Security

- Validate all input
- Sanitize output
- Use parameterized queries
- Implement rate limiting
- Add CSRF protection
- Keep dependencies updated

### 4. Testing

- Write unit tests for business logic
- Write integration tests for API endpoints
- Use test fixtures
- Mock external services
- Achieve good test coverage

### 5. Error Handling

- Log all errors with context
- Return user-friendly messages
- Don't expose sensitive information
- Implement retry logic for transient failures
- Add monitoring and alerts

## Example Project Structure

After following this workflow, your project might look like:

```
my-backend-api/
├── src/
│   ├── routes/
│   │   ├── users.ts
│   │   ├── auth.ts
│   │   └── payments.ts
│   ├── models/
│   │   ├── User.ts
│   │   └── Payment.ts
│   ├── middleware/
│   │   ├── auth.ts
│   │   └── errorHandler.ts
│   ├── services/
│   │   ├── userService.ts
│   │   └── paymentService.ts
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   └── 002_add_email_verification.sql
│   └── app.ts
├── tests/
│   ├── unit/
│   │   └── userService.test.ts
│   ├── integration/
│   │   └── auth.test.ts
│   └── fixtures/
│       └── users.json
├── .agentwire.yml
├── package.json
├── tsconfig.json
└── openapi.json
```

## Session Management

```bash
# List all sessions
agentwire list

# Attach to specific session
tmux attach -t backend-api

# Kill session when done
agentwire kill -s backend-api

# Fork session for feature development
agentwire fork -s backend-api -b feature-webhooks
```

## Integration with Frontend

When working with a frontend team:

**Voice command:** "Update API documentation with new endpoint details"

OpenCode will:
1. Update OpenAPI spec
2. Document request/response
3. Add example calls
4. Update Swagger UI

The frontend team can use the updated documentation to integrate.

## Monitoring and Observability

**Voice command:** "Add monitoring and logging to the application"

OpenCode will:
1. Set up logging library
2. Add structured logging
3. Configure log levels
4. Set up metrics collection
5. Add health check endpoints
6. Implement performance monitoring

## Next Steps

- [Session Types Reference](../SESSION_TYPES.md) - Understanding session types
- [OpenCode Role Guide](../OPENCODE_ROLES.md) - Creating custom roles
- [Frontend Development Workflow](frontend-workflow.md) - Frontend development guide
- [Multi-Agent Workflow](multi-agent-workflow.md) - Coordinated workflows
