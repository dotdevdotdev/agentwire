# Context Compression Protocol: Efficient Knowledge Transfer Between Agents

> A formal protocol for compressing and transferring context between orchestrators, workers, and sessions without token waste.

## Problem

Every time an orchestrator spawns a worker, it faces a context dilemma:

```
Orchestrator context: 50,000 tokens
├── User's original request
├── Codebase exploration (file reads, searches)
├── Architectural decisions made
├── Failed approaches tried
├── Current plan and reasoning
└── Conversation history

Worker receives: 200 tokens
└── "Add JWT auth to the login endpoint"
```

The worker lacks crucial context:
- Why JWT over sessions? (Decision was made 20 messages ago)
- What auth patterns exist in the codebase? (Orchestrator already explored this)
- What pitfalls to avoid? (Orchestrator already tried approach X, it failed)

**Result:** Workers waste tokens re-discovering context, make different decisions than the orchestrator intended, or go off-track without the "why" behind requirements.

The opposite problem also exists:
- **Context overload**: Dumping 2000 tokens of context onto a worker that needs 200
- **Stale context**: Passing context that's no longer relevant
- **Wrong abstraction level**: Giving implementation details when worker needs goals, or vice versa

## Why Current Approaches Fail

### Manual Context Summaries

Orchestrators can write summaries, but:
- Inconsistent quality (sometimes too brief, sometimes too verbose)
- Time-consuming (orchestrator spends tokens summarizing)
- No feedback loop (orchestrator doesn't know what the worker actually needed)

### File-Based Context

Writing context to files (`.agentwire/context.md`) helps, but:
- Workers may not read them (no enforcement)
- Static - doesn't adapt to task complexity
- One-size-fits-all format

### Conversation Replay

Passing full conversation history:
- Massive token waste
- Noise drowns signal
- Irrelevant tangents included

## Proposed Solution: Context Compression Protocol (CCP)

A structured protocol for creating, validating, and transferring compressed context between agents.

### Core Concept

Context is compressed into **Context Packets** - structured, task-appropriate summaries with explicit metadata about what's included and what's not.

```yaml
# Context Packet
version: 1
created: 2024-01-15T10:30:00Z
creator: orchestrator-pane-0
target_task: "Add JWT authentication"

# What the worker needs to know
context:
  goal: |
    Add JWT-based authentication to the login endpoint.
    User should receive a token on successful login.

  decisions:
    - choice: "JWT over session tokens"
      reason: "Stateless, works with planned mobile app"
      made_by: user

    - choice: "RS256 signing algorithm"
      reason: "Can verify without shared secret"
      made_by: orchestrator

  constraints:
    - "Must use existing User model from models/user.py"
    - "Token expiry: 24 hours (user preference)"
    - "Do NOT modify the registration flow"

  codebase:
    relevant_files:
      - path: "models/user.py"
        summary: "User model with email, password_hash, created_at"
      - path: "routes/auth.py"
        summary: "Currently has /register endpoint, need to add /login"
    patterns:
      - "Error responses use {error: string, code: number} format"
      - "All routes use async/await"

  failed_attempts:
    - approach: "Using PyJWT library"
      reason_failed: "Not in requirements.txt, use python-jose instead"

  not_included:
    - "Full conversation history"
    - "Unrelated codebase exploration"
    - "UI/frontend considerations (separate task)"

# Validation
checksum: "sha256:abc123..."
token_count: 450
```

### Protocol Layers

**Layer 1: Goal Context** (always included, ~50-100 tokens)
- What to accomplish
- Success criteria
- Hard constraints

**Layer 2: Decision Context** (included for non-trivial tasks, ~100-200 tokens)
- Key decisions already made
- Reasoning behind choices
- Who made each decision (user vs agent)

**Layer 3: Codebase Context** (included for implementation tasks, ~100-300 tokens)
- Relevant files with summaries
- Patterns to follow
- Anti-patterns to avoid

**Layer 4: History Context** (included for complex/risky tasks, ~100-200 tokens)
- Failed approaches
- Pivots and why
- Open questions

### Compression Strategies

**1. Relevance Filtering**
Only include context relevant to the specific task:
```python
def filter_context(full_context: Context, task: str) -> Context:
    """Keep only context relevant to this task."""
    relevant = []
    for item in full_context:
        if semantic_similarity(item, task) > 0.7:
            relevant.append(item)
    return relevant
```

**2. Hierarchical Summarization**
Progressive compression based on distance from current task:
```
Recent decisions → Full detail
Older decisions → One-line summary
Ancient context → Omit or single word tag
```

**3. Pattern Extraction**
Instead of listing 10 similar files:
```yaml
# Before (verbose)
relevant_files:
  - routes/users.py: "async handlers, error format..."
  - routes/products.py: "async handlers, error format..."
  - routes/orders.py: "async handlers, error format..."

# After (pattern)
patterns:
  - "Route handlers are async, use {error, code} format"
examples:
  - routes/users.py  # Worker can read one for reference
```

**4. Decision Deduplication**
Merge related decisions:
```yaml
# Before
decisions:
  - "Use JWT"
  - "Use RS256"
  - "24h expiry"
  - "Store in httpOnly cookie"

# After
decisions:
  - choice: "JWT auth with RS256, 24h expiry, httpOnly cookie storage"
    reason: "Stateless + secure + user-specified expiry"
```

### Worker Acknowledgment

Workers can signal what context they needed but didn't have:

```yaml
# Worker feedback (written to .agentwire/feedback-{pane}.md)
context_gaps:
  - "Needed: existing error handling patterns"
  - "Needed: testing approach (unit vs integration)"

context_unused:
  - "Received: failed_attempts (didn't reference)"
```

This feedback helps orchestrators improve future context packets.

### Orchestrator Learning

Orchestrators track context effectiveness:

```python
class ContextEfficiencyTracker:
    def record_task(self, context_sent: int, worker_success: bool, gaps: list):
        """Track what context led to successful outcomes."""
        # Over time, learn:
        # - Minimum viable context per task type
        # - What context is usually unused
        # - What gaps cause failures
```

## Implementation

### Context Packet Generator

```python
@dataclass
class ContextPacket:
    version: int = 1
    created: datetime = field(default_factory=datetime.now)
    creator: str = ""
    target_task: str = ""

    goal: str = ""
    decisions: list[Decision] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    codebase: CodebaseContext | None = None
    failed_attempts: list[FailedAttempt] = field(default_factory=list)
    not_included: list[str] = field(default_factory=list)

    def to_yaml(self) -> str:
        """Serialize to YAML for file storage."""

    def to_prompt(self) -> str:
        """Format as markdown for worker prompt."""

    @property
    def token_count(self) -> int:
        """Estimate tokens in this packet."""


def generate_context_packet(
    task: str,
    conversation: list[Message],
    codebase_cache: dict[str, str],
    depth: Literal["minimal", "standard", "deep"] = "standard"
) -> ContextPacket:
    """Generate a compressed context packet for a task."""

    packet = ContextPacket(target_task=task)

    # Layer 1: Goal (always)
    packet.goal = extract_goal(task, conversation)
    packet.constraints = extract_constraints(conversation)

    if depth in ("standard", "deep"):
        # Layer 2: Decisions
        packet.decisions = extract_decisions(conversation)

        # Layer 3: Codebase
        relevant_files = find_relevant_files(task, codebase_cache)
        packet.codebase = summarize_codebase_context(relevant_files)

    if depth == "deep":
        # Layer 4: History
        packet.failed_attempts = extract_failures(conversation)

    # What we explicitly excluded
    packet.not_included = describe_exclusions(conversation, packet)

    return packet
```

### File Protocol

Context packets are stored as files for worker consumption:

```
.agentwire/
├── context/
│   ├── pane-1.yaml  # Context for worker in pane 1
│   ├── pane-2.yaml  # Context for worker in pane 2
│   └── shared.yaml  # Shared context (codebase patterns, etc.)
└── feedback/
    ├── pane-1.md    # Feedback from worker 1
    └── pane-2.md    # Feedback from worker 2
```

### CLI Integration

```bash
# Generate context packet for a task
agentwire context generate "Add JWT auth" --depth standard

# View context that would be sent to a worker
agentwire context preview --pane 1

# Analyze context efficiency (historical)
agentwire context stats
# Output:
# Average context size: 380 tokens
# Worker success rate: 87%
# Top context gaps: testing approach (23%), error handling (18%)

# Clear context after task completion
agentwire context clear --pane 1
```

### MCP Tools

```python
@mcp.tool()
def context_generate(
    task: str,
    depth: str = "standard",
    pane: int | None = None
) -> str:
    """Generate a context packet for a worker task.

    Args:
        task: The task description
        depth: minimal | standard | deep
        pane: Target pane (writes to .agentwire/context/pane-{N}.yaml)

    Returns:
        The generated context packet as YAML
    """

@mcp.tool()
def context_read(pane: int | None = None) -> str:
    """Read context packet for current worker.

    Workers call this to get their context packet.
    """

@mcp.tool()
def context_feedback(
    gaps: list[str] | None = None,
    unused: list[str] | None = None
) -> str:
    """Report context gaps or unused context.

    Workers call this to help orchestrators improve.
    """
```

### Role Updates

**Orchestrator role addition:**
```markdown
## Context Handoff

Before spawning workers, generate context packets:

1. Identify task complexity (simple/standard/complex)
2. Generate appropriate context depth:
   - Simple: goal + constraints only
   - Standard: + decisions + codebase patterns
   - Complex: + failed attempts + history

3. Write context packet:
   `agentwire_context_generate(task="...", depth="standard", pane=1)`

4. Include read instruction in worker task:
   "Read your context packet first: .agentwire/context/pane-1.yaml"
```

**Worker role addition:**
```markdown
## Context Protocol

At task start:
1. Read your context packet: `.agentwire/context/pane-{N}.yaml`
2. Note decisions already made (don't re-decide)
3. Follow noted constraints exactly

At task end, report gaps:
- What context would have helped?
- What context was provided but unused?

Write to: `.agentwire/feedback/pane-{N}.md`
```

## Configuration

```yaml
# In ~/.agentwire/config.yaml
context:
  # Default compression depth
  default_depth: "standard"  # minimal | standard | deep

  # Token budgets per depth
  budgets:
    minimal: 100
    standard: 400
    deep: 800

  # Auto-generate context for workers
  auto_generate: true

  # Track efficiency over time
  track_efficiency: true

  # Cleanup context files after task completion
  auto_cleanup: true
```

## Example Flow

```
Orchestrator:
1. Explores codebase (1000 tokens of reads)
2. Makes decisions with user (500 tokens of discussion)
3. Plans approach (300 tokens)
4. Total context: 1800 tokens

Spawning worker:
1. agentwire_context_generate(task="Add JWT auth", depth="standard", pane=1)
2. Generates 350 token context packet with:
   - Goal: Add JWT to login endpoint
   - Decisions: RS256, 24h expiry, use python-jose
   - Codebase: User model summary, auth.py location
   - Constraints: Don't touch registration

3. Spawns worker with: "Read .agentwire/context/pane-1.yaml, then implement"

Worker:
1. Reads context packet (350 tokens vs 1800)
2. Knows exactly what to do and why
3. Implements efficiently
4. Reports back: "No context gaps"

Result:
- 1450 tokens saved (80% reduction)
- Worker had right context for the task
- Decisions were preserved, not re-made
```

## Potential Challenges

1. **Summarization quality**: LLM-generated summaries may lose critical nuance
   - Solution: Structured extraction (decisions, constraints) rather than free-form summary
   - Solution: Allow orchestrator to override/edit generated packets

2. **Stale context**: Context generated at spawn time may become stale
   - Solution: Timestamps on context, workers can request refresh
   - Solution: Orchestrator can push context updates

3. **Task complexity estimation**: Hard to know if task needs "minimal" or "deep" context
   - Solution: Start with standard, track failure patterns, adjust
   - Solution: Workers can escalate if context insufficient

4. **Protocol adoption**: Workers (especially GLM) may not follow protocol
   - Solution: Explicit instructions in role definitions
   - Solution: Enforce file read in task template

5. **Context drift**: As sessions continue, context accumulates and becomes harder to compress
   - Solution: Session-level compression (separate from task-level)
   - Solution: Explicit "checkpoint and reset" commands

6. **Cross-session context**: Hard to share context between separate sessions
   - Solution: Shared context files (.agentwire/context/shared.yaml)
   - Solution: Project-level context that persists

## Success Criteria

1. Worker success rate increases (less context misalignment)
2. Token usage per worker task decreases
3. Re-exploration of already-known information decreases
4. Workers report fewer "context gaps"
5. Orchestrators spend less time writing manual summaries

## Future Extensions

### Semantic Context Search

Instead of pre-generating context, workers query for what they need:

```python
@mcp.tool()
def context_query(question: str) -> str:
    """Ask the orchestrator's context for specific information.

    Example: "What authentication approach was decided?"
    Returns: "JWT with RS256, 24h expiry, per user request"
    """
```

### Progressive Context Loading

Start with minimal context, load more on demand:

```
Worker starts with Layer 1 (goal only)
Worker hits decision point → requests Layer 2 (decisions)
Worker needs file info → requests Layer 3 (codebase)
```

### Cross-Session Context Graph

Build a graph of context relationships across sessions:

```
Session A (auth work)
  └── Decision: Use JWT
      └── Referenced by Session B (API work)
          └── Referenced by Session C (mobile work)
```

When Session C needs auth context, traverse graph to find relevant decisions.

### Context Versioning

Track context evolution:

```yaml
context:
  version: 3
  changelog:
    - v1: "Initial: session tokens"
    - v2: "Changed to JWT per user request"
    - v3: "Added RS256 requirement"
```

Workers see not just decisions but how they evolved.
