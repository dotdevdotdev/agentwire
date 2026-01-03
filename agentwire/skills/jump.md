---
name: jump
description: Provide instructions to manually attach to a tmux session.
---

# /jump

Provide the command to manually attach to a tmux session, handling both local and remote machines.

## Usage

```
/jump <session>
/jump <session>@<machine>
```

## Behavior

1. Parse session name from argument
2. Check for `@machine` suffix to determine if remote
3. If local (no `@`), provide `tmux attach` command
4. If remote (has `@`), provide `ssh -t` + `tmux attach` command
5. Output the ready-to-run command

## Commands Generated

```bash
# Local session
tmux attach -t <session>

# Remote session (requires TTY allocation)
ssh -t <machine> "tmux attach -t <session>"
```

**Note:** The `-t` flag for ssh allocates a pseudo-TTY, which is required for interactive tmux sessions.

## Examples

### Local Session

```
/jump api
```

Output:
```
To attach to 'api', run:

    tmux attach -t api
```

### Remote Session

```
/jump ml@devbox-1
```

Output:
```
To attach to 'ml' on devbox-1, run:

    ssh -t devbox-1 "tmux attach -t ml"
```

## Implementation Notes

- This skill provides manual attachment instructions
- The user runs the command themselves (not automated)
- Useful when the /attach skill fails or for debugging
- Machine names should match SSH config entries in `~/.ssh/config`

## Related Skills

- `/spawn` - Create new sessions
- `/kill` - Terminate sessions
- `/sessions` - List active sessions
