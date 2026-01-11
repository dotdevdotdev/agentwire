# CLI Documentation Review

> **Status: RESOLVED** - All missing parameters have been added to CLI-REFERENCE.md and cli-diagram.md.

Comprehensive comparison of actual code, CLI help output, and documentation.

**Legend:**
- ✅ Documented correctly
- ❌ Discrepancy (documented incorrectly)
- ⚠️ Missing from docs (exists in code but not documented)
- 📝 Note

---

## Resolution

All 45+ missing parameters identified below have been added to:
- `docs/CLI-REFERENCE.md` - Full command reference with examples
- `docs/cli-diagram.md` - Parameter reference tables and flow diagrams

---

## Command: `init`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `--quick` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `--quick` flag exists in code/help but not documented in CLI-REFERENCE.md

---

## Command: `portal start`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `--config` | ✅ | ✅ | ⚠️ **Missing** |
| `--port` | ✅ | ✅ | ⚠️ **Missing** |
| `--host` | ✅ | ✅ | ⚠️ **Missing** |
| `--no-tts` | ✅ | ✅ | ⚠️ **Missing** |
| `--no-stt` | ✅ | ✅ | ⚠️ **Missing** |
| `--dev` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** All portal start options are undocumented

---

## Command: `portal serve`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `--config` | ✅ | ✅ | ⚠️ **Missing** |
| `--port` | ✅ | ✅ | ⚠️ **Missing** |
| `--host` | ✅ | ✅ | ⚠️ **Missing** |
| `--no-tts` | ✅ | ✅ | ⚠️ **Missing** |
| `--no-stt` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** All portal serve options are undocumented

---

## Command: `portal stop`

✅ No parameters - matches documentation

---

## Command: `portal status`

✅ No parameters - matches documentation

---

## Command: `tts start`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `--port` | ✅ | ✅ | ⚠️ **Missing** |
| `--host` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `--port` and `--host` options are undocumented

---

## Command: `tts serve`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `--port` | ✅ | ✅ | ⚠️ **Missing** |
| `--host` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `--port` and `--host` options are undocumented

---

## Command: `tts stop`

✅ No parameters - matches documentation

---

## Command: `tts status`

✅ No parameters - matches documentation

---

## Command: `say`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `text` (positional) | ✅ | ✅ | ✅ |
| `-v, --voice` | ✅ | ✅ | ✅ |
| `-r, --room` | ✅ | ✅ | ✅ |
| `--exaggeration` | ✅ | ✅ | ⚠️ **Missing** |
| `--cfg` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `--exaggeration` and `--cfg` voice tuning options are undocumented

---

## Command: `send`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `-s, --session` | ✅ | ✅ | ✅ |
| `prompt` (positional) | ✅ | ✅ | ✅ |
| `--json` | ✅ | ✅ | ✅ |

✅ All parameters documented correctly

---

## Command: `send-keys`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `-s, --session` | ✅ | ✅ | ✅ |
| `keys` (positional) | ✅ | ✅ | ✅ |

✅ All parameters documented correctly (but no `--json` flag exists, unlike other commands)

📝 **Note:** Unlike most session commands, `send-keys` does not have a `--json` flag

---

## Command: `list`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `--json` | ✅ | ✅ | ✅ |
| `--local` | ✅ | ✅ | ✅ |

✅ All parameters documented correctly

---

## Command: `new`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `-s, --session` | ✅ | ✅ | ✅ |
| `-p, --path` | ✅ | ✅ | ✅ |
| `-t, --template` | ✅ | ✅ | ✅ |
| `-f, --force` | ✅ | ✅ | ✅ |
| `--no-bypass` | ✅ | ✅ | ✅ |
| `--restricted` | ✅ | ✅ | ✅ |
| `--roles` | ✅ | ✅ | ✅ |
| `--json` | ✅ | ✅ | ✅ |

✅ All parameters documented correctly

---

## Command: `output`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `-s, --session` | ✅ | ✅ | ✅ |
| `-n, --lines` | ✅ | ✅ | ✅ |
| `--json` | ✅ | ✅ | ✅ |

✅ All parameters documented correctly

---

## Command: `kill`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `-s, --session` | ✅ | ✅ | ✅ |
| `--json` | ✅ | ✅ | ✅ |

✅ All parameters documented correctly

---

## Command: `recreate`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `-s, --session` | ✅ | ✅ | ✅ |
| `--no-bypass` | ✅ | ✅ | ⚠️ **Missing** |
| `--restricted` | ✅ | ✅ | ⚠️ **Missing** |
| `--json` | ✅ | ✅ | ✅ |

**Discrepancy:** `--no-bypass` and `--restricted` options are undocumented

---

## Command: `fork`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `-s, --source` | ✅ | ✅ | ✅ |
| `-t, --target` | ✅ | ✅ | ✅ |
| `--no-bypass` | ✅ | ✅ | ⚠️ **Missing** |
| `--restricted` | ✅ | ✅ | ⚠️ **Missing** |
| `--json` | ✅ | ✅ | ✅ |

**Discrepancy:** `--no-bypass` and `--restricted` options are undocumented

---

## Command: `dev`

✅ No parameters - matches documentation

---

## Command: `listen`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `--session, -s` | ✅ | ✅ | ⚠️ **Missing** (on parent command) |
| `--no-prompt` | ✅ | ✅ | ⚠️ **Missing** |
| `start` subcommand | ✅ | ✅ | ✅ |
| `stop` subcommand | ✅ | ✅ | ✅ |
| `cancel` subcommand | ✅ | ✅ | ✅ |

**Discrepancy:** Parent-level `--session` and `--no-prompt` flags are undocumented

📝 **Note:** Docs show `listen stop -s <session>` but the `-s` flag is actually on the parent `listen` command, not the `stop` subcommand

---

## Command: `listen stop`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `--session, -s` | ✅ | ✅ | ✅ (sort of) |
| `--no-prompt` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `--no-prompt` on stop subcommand is undocumented

---

## Command: `voiceclone`

| Subcommand | Code | Help | CLI-REFERENCE.md |
|------------|------|------|------------------|
| `start` | ✅ | ✅ | ✅ |
| `stop <name>` | ✅ | ✅ | ✅ |
| `cancel` | ✅ | ✅ | ✅ |
| `list` | ✅ | ✅ | ✅ |
| `delete <name>` | ✅ | ✅ | ✅ |

✅ All subcommands documented correctly

---

## Command: `machine list`

✅ No parameters - matches documentation

---

## Command: `machine add`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `machine_id` (positional) | ✅ | ✅ | ⚠️ **Missing** (shown as `<id>`) |
| `--host` | ✅ | ✅ | ⚠️ **Missing** |
| `--user` | ✅ | ✅ | ⚠️ **Missing** |
| `--projects-dir` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** All options for `machine add` are undocumented - docs only show `machine add <id> [options]` without explaining options

---

## Command: `machine remove`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `machine_id` (positional) | ✅ | ✅ | ✅ |

✅ Documented correctly

---

## Command: `template list`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `--json` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `--json` flag is undocumented

---

## Command: `template show`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `name` (positional) | ✅ | ✅ | ✅ |
| `--json` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `--json` flag is undocumented

---

## Command: `template create`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `name` (positional) | ✅ | ✅ | ✅ |
| `--description` | ✅ | ✅ | ⚠️ **Missing** |
| `--voice` | ✅ | ✅ | ⚠️ **Missing** |
| `--role` | ✅ | ✅ | ⚠️ **Missing** |
| `--project` | ✅ | ✅ | ⚠️ **Missing** |
| `--prompt` | ✅ | ✅ | ⚠️ **Missing** |
| `--no-bypass` | ✅ | ✅ | ⚠️ **Missing** |
| `--restricted` | ✅ | ✅ | ⚠️ **Missing** |
| `-f, --force` | ✅ | ✅ | ⚠️ **Missing** |
| `--json` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** All options for `template create` are undocumented - only the positional `name` is implied

---

## Command: `template delete`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `name` (positional) | ✅ | ✅ | ✅ |
| `-f, --force` | ✅ | ✅ | ⚠️ **Missing** |
| `--json` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `-f, --force` and `--json` flags are undocumented

---

## Command: `template install-samples`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `-f, --force` | ✅ | ✅ | ⚠️ **Missing** |
| `--json` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `-f, --force` and `--json` flags are undocumented

---

## Command: `skills install`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `-f, --force` | ✅ | ✅ | ⚠️ **Missing** |
| `--copy` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `-f, --force` and `--copy` flags are undocumented

---

## Command: `skills status`

✅ No parameters - matches documentation

---

## Command: `skills uninstall`

✅ No parameters - matches documentation

---

## Command: `safety check`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `command` (positional) | ✅ | ✅ | ✅ |
| `-v, --verbose` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `-v, --verbose` flag is undocumented

---

## Command: `safety status`

✅ No parameters - matches documentation

---

## Command: `safety logs`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `--tail, -n` | ✅ | ✅ | ✅ (shown as `--tail 20`) |
| `--session, -s` | ✅ | ✅ | ⚠️ **Missing** |
| `--today` | ✅ | ✅ | ⚠️ **Missing** |
| `--pattern, -p` | ✅ | ✅ | ⚠️ **Missing** |

**Discrepancy:** `--session`, `--today`, and `--pattern` flags are undocumented

---

## Command: `safety install`

✅ No parameters - matches documentation

---

## Command: `network status`

✅ No parameters - matches documentation

---

## Command: `tunnels up`

✅ No parameters - matches documentation

---

## Command: `tunnels down`

✅ No parameters - matches documentation

---

## Command: `tunnels status`

✅ No parameters - matches documentation

---

## Command: `tunnels check`

✅ No parameters - matches documentation

---

## Command: `doctor`

| Parameter | Code | Help | CLI-REFERENCE.md |
|-----------|------|------|------------------|
| `--dry-run` | ✅ | ✅ | ✅ |
| `-y, --yes` | ✅ | ✅ | ✅ |

✅ All parameters documented correctly

---

## Command: `generate-certs`

✅ No parameters - matches documentation

---

## Command: `rebuild`

✅ No parameters - matches documentation

---

## Command: `uninstall`

✅ No parameters - matches documentation

---

# Summary

## Fully Documented Commands (✅)
- `send`
- `list`
- `new`
- `output`
- `kill`
- `dev`
- `voiceclone` (all subcommands)
- `machine remove`
- `skills status`
- `skills uninstall`
- `safety status`
- `safety install`
- `network status`
- `tunnels` (all subcommands)
- `doctor`
- `generate-certs`
- `rebuild`
- `uninstall`
- `portal stop`
- `portal status`
- `tts stop`
- `tts status`

## Commands with Missing Parameters (⚠️)

| Command | Missing Parameters |
|---------|-------------------|
| `init` | `--quick` |
| `portal start` | `--config`, `--port`, `--host`, `--no-tts`, `--no-stt`, `--dev` |
| `portal serve` | `--config`, `--port`, `--host`, `--no-tts`, `--no-stt` |
| `tts start` | `--port`, `--host` |
| `tts serve` | `--port`, `--host` |
| `say` | `--exaggeration`, `--cfg` |
| `recreate` | `--no-bypass`, `--restricted` |
| `fork` | `--no-bypass`, `--restricted` |
| `listen` | `--session` (parent), `--no-prompt` |
| `listen stop` | `--no-prompt` |
| `machine add` | `--host`, `--user`, `--projects-dir` |
| `template list` | `--json` |
| `template show` | `--json` |
| `template create` | `--description`, `--voice`, `--role`, `--project`, `--prompt`, `--no-bypass`, `--restricted`, `-f`, `--json` |
| `template delete` | `-f`, `--json` |
| `template install-samples` | `-f`, `--json` |
| `skills install` | `-f`, `--copy` |
| `safety check` | `-v, --verbose` |
| `safety logs` | `--session`, `--today`, `--pattern` |

## Total Counts

- **Commands reviewed:** 45
- **Fully documented:** 22
- **Partially documented:** 23
- **Missing parameters total:** ~45 individual flags/options

---

# Cross-Reference: cli-diagram.md

The cli-diagram.md file was created in this session. It accurately reflects:
- ✅ Command groupings (session, voice, infrastructure, config, development)
- ✅ Session name parsing logic (local, worktree, remote patterns)
- ✅ Voice routing logic (browser vs local playback)
- ✅ Config file locations and purposes

**Not covered in cli-diagram.md** (intentionally simplified):
- Individual parameter flags for each command
- JSON output format details
- Template creation options
- Safety pattern matching details

The diagram focuses on architecture and data flow rather than exhaustive parameter documentation.

---

# Recommendations

1. **High Priority:** Document portal/tts server options (`--port`, `--host`, `--config`, `--dev`)
2. **Medium Priority:** Document template create options (9 missing flags)
3. **Medium Priority:** Document machine add options
4. **Low Priority:** Add `--json` flags to template/safety commands (consistency)
5. **Low Priority:** Document voice tuning options (`--exaggeration`, `--cfg`)
