# Conversation Archaeology

**One-line summary:** Mine past session transcripts to build a growing knowledge base about your codebase, patterns, and preferences that future sessions can query.

## Problem It Solves

Every new session starts from scratch. Workers re-explore the same codebase, orchestrators re-explain the same architectural patterns, and hard-won knowledge about quirks, gotchas, and preferences is lost to scrollback. This is especially wasteful when:

- A worker asks "how does auth work?" for the 10th time
- An orchestrator explains the same naming conventions repeatedly
- Debugging knowledge from last week's session would solve today's problem
- Project-specific patterns (like "always use X instead of Y") get forgotten

The system has access to months of valuable conversations but treats each session as if it's the first.

## Proposed Solution

**Conversation Archaeology** - A background system that:

1. **Indexes completed sessions** - After a session ends (or on-demand), extract structured knowledge:
   - Code patterns discovered ("the API uses snake_case, frontend uses camelCase")
   - Gotchas encountered ("the tests require POSTGRES_URL even in mocks")
   - Architectural decisions ("we chose Zustand over Redux because...")
   - User preferences learned ("always commit with conventional commits")
   - File purpose mappings ("auth.ts handles JWT, auth-client.ts handles cookies")

2. **Stores knowledge per-project** - Each project gets a `.agentwire/knowledge.yaml` (or SQLite) that grows over time:
   ```yaml
   patterns:
     naming: "API uses snake_case, React uses camelCase"
     testing: "Run pytest with --no-cov flag for speed"
   gotchas:
     - "The ESLint config requires Node 18+"
     - "Don't use relative imports in the CLI module"
   decisions:
     state_management: "Zustand - simpler than Redux for this scale"
   file_index:
     src/auth.ts: "JWT token generation and validation"
     src/hooks/useAuth.ts: "React auth context and hooks"
   ```

3. **Injects relevant context** - When sessions start or workers spawn:
   - Query the knowledge base for relevant entries
   - Inject as compressed context (not full history, just learnings)
   - Workers get project knowledge without burning tokens on exploration

4. **Voice-queryable** - "What did we decide about caching?" or "What's the gotcha with the deploy script?" returns knowledge base entries.

## Implementation Considerations

### Extraction Phase

```bash
# Manual trigger
agentwire archaeology extract -s session-name

# Auto-run on session end (configurable)
agentwire archaeology watch --auto
```

Use a small model (Haiku) to extract structured knowledge from session transcripts. Prompt focuses on:
- Patterns/conventions observed
- Problems solved and their solutions
- Explicit decisions made
- File/component purposes discovered

### Storage

Simple YAML for human readability and git-friendliness:
```
.agentwire/
  knowledge.yaml      # Extracted knowledge
  archaeology.log     # Which sessions were processed
```

Or SQLite for larger projects with full-text search:
```
.agentwire/knowledge.db
```

### Injection

Add to role system - a `knowledge-aware` role fragment that:
1. Reads `.agentwire/knowledge.yaml` on session start
2. Compresses relevant entries into ~500 token summary
3. Prepends to system prompt

```yaml
# .agentwire.yml
roles:
  - leader
  - knowledge-aware  # Adds project knowledge injection
```

### Voice Integration

New voice commands:
- "What do we know about [topic]?" - Searches knowledge base
- "Remember that [fact]" - Adds manual entry
- "Forget about [topic]" - Removes entries (for outdated knowledge)

## Potential Challenges

1. **Knowledge Staleness** - Code changes but extracted knowledge doesn't update automatically
   - Mitigation: Timestamp entries, periodic re-validation, allow manual pruning
   - Consider: Link entries to file paths, invalidate when files change significantly

2. **Extraction Quality** - LLM might extract noise or miss important patterns
   - Mitigation: Human review of extractions, confidence scoring, manual additions
   - Start conservative: only extract high-confidence patterns

3. **Token Budget** - Injecting too much knowledge defeats the purpose
   - Mitigation: Relevance ranking, dynamic compression, context-aware selection
   - Cap at 500-1000 tokens of knowledge injection

4. **Privacy** - Extracted knowledge might contain sensitive info
   - Mitigation: `.gitignore` the knowledge file by default, optional encryption
   - Allow excluding specific sessions from archaeology

5. **Cold Start** - New projects have no knowledge yet
   - Mitigation: Bootstrap from README/CLAUDE.md parsing
   - First few sessions build the foundation naturally

## Success Metrics

- Reduced "exploration turns" in worker sessions
- Faster time-to-first-edit for new sessions
- Fewer repeated questions across sessions
- User satisfaction with "it remembers" moments

## Related Ideas

- Could integrate with Session Replay for "show me when we learned this"
- Knowledge entries could have confidence scores that decay over time
- Cross-project knowledge for shared patterns ("I always use Zod for validation")
