/**
 * AgentWire Notification Plugin for OpenCode
 *
 * Notifies orchestrator when session goes idle.
 * Workers queue notifications with summary file path, then auto-exit.
 * Orchestrators notify parent session directly.
 */

import type { Plugin } from "@opencode-ai/plugin"
import { execSync, spawn } from "child_process"
import { readFileSync, appendFileSync, existsSync, writeFileSync } from "fs"
import { basename, join } from "path"
import { homedir } from "os"

interface AgentWireConfig {
  session?: string
  parent?: string
  voice?: string
  roles?: string[]
}

interface SessionIdleEvent {
  type: "session.idle"
  properties: {
    sessionID: string
  }
}

function parseAgentWireYml(cwd: string): AgentWireConfig {
  const configPath = join(cwd, ".agentwire.yml")
  if (!existsSync(configPath)) {
    return {}
  }

  try {
    const content = readFileSync(configPath, "utf-8")
    const config: AgentWireConfig = {}

    for (const line of content.split("\n")) {
      const sessionMatch = line.match(/^session:\s*["']?([^"'\n]+)["']?/)
      if (sessionMatch) config.session = sessionMatch[1].trim()

      const parentMatch = line.match(/^parent:\s*["']?([^"'\n]+)["']?/)
      if (parentMatch) config.parent = parentMatch[1].trim()

      const voiceMatch = line.match(/^voice:\s*["']?([^"'\n]+)["']?/)
      if (voiceMatch) config.voice = voiceMatch[1].trim()

      if (line.match(/^-\s*chatbot/)) {
        config.roles = config.roles || []
        config.roles.push("chatbot")
      }
    }

    return config
  } catch {
    return {}
  }
}

function getPaneIndex(): number | null {
  const tmuxPane = process.env.TMUX_PANE
  if (!tmuxPane) return null

  try {
    const output = execSync(`tmux display -t "${tmuxPane}" -p '#{pane_index}'`, {
      encoding: "utf-8",
      timeout: 1000,
    })
    return parseInt(output.trim(), 10)
  } catch {
    return null
  }
}

function getTmuxSessionName(): string | null {
  const tmuxPane = process.env.TMUX_PANE
  if (!tmuxPane) return null

  try {
    const output = execSync(`tmux display -t "${tmuxPane}" -p '#{session_name}'`, {
      encoding: "utf-8",
      timeout: 1000,
    })
    return output.trim()
  } catch {
    return null
  }
}

function isQueueProcessorRunning(session: string): boolean {
  const pidFile = join(homedir(), ".agentwire", "queues", `${session}.pid`)
  if (!existsSync(pidFile)) return false

  try {
    const pid = readFileSync(pidFile, "utf-8").trim()
    // Check if process is running
    process.kill(parseInt(pid, 10), 0)
    return true
  } catch {
    return false
  }
}

function queueNotification(session: string, message: string): void {
  const queueDir = join(homedir(), ".agentwire", "queues")
  const queueFile = join(queueDir, `${session}.jsonl`)

  // Append to queue
  const entry = JSON.stringify({ timestamp: Date.now(), message }) + "\n"
  appendFileSync(queueFile, entry)

  // Start queue processor if not running
  if (!isQueueProcessorRunning(session)) {
    const processor = spawn(
      join(homedir(), ".agentwire", "queue-processor.sh"),
      [session],
      { detached: true, stdio: "ignore" }
    )
    processor.unref()
  }
}

export const AgentWireNotifyPlugin: Plugin = async () => {
  return {
    event: async ({ event }) => {
      if (event.type !== "session.idle") {
        return
      }

      const idleEvent = event as unknown as SessionIdleEvent
      const sessionID = idleEvent.properties.sessionID

      const cwd = process.cwd()
      const config = parseAgentWireYml(cwd)

      // Skip chatbot sessions
      if (config.roles?.includes("chatbot")) {
        return
      }

      const sessionName = config.session || basename(cwd)
      const paneIndex = getPaneIndex()
      const isWorker = paneIndex !== null && paneIndex > 0
      const tmuxSession = getTmuxSessionName()

      // For workers: implement two-pass idle system
      if (isWorker && tmuxSession) {
        const summaryPath = join(cwd, `.agentwire`, `${sessionID}.md`)
        const summaryExists = existsSync(summaryPath)

        // Delay to let OpenCode settle
        setTimeout(() => {
          if (!summaryExists) {
            // First idle: No summary file yet, instruct agent to create one
            const instruction = `Please write an exit summary to ${summaryPath} with these sections:
# Worker Summary

## Task
[What you were asked to do]

## Status
Complete | Blocked | Failed

## What I Did
[Actions taken]

## Files Changed
List files you modified or created with brief descriptions

## What Worked
[Successes]

## What Didn't Work
[Issues and why]

## Notes for Orchestrator
[Context for follow-up]`

            try {
              // Send instruction to the pane
              const send = spawn(
                "/Users/dotdev/.local/bin/agentwire",
                ["send", "--pane", String(paneIndex), instruction],
                { detached: true, stdio: "ignore" }
              )
              send.unref()
            } catch {
              // Ignore errors
            }
          } else {
            // Second idle: Summary file exists, read it and notify parent
            try {
              const summaryContent = readFileSync(summaryPath, "utf-8")
              const message = `[WORKER SUMMARY pane ${paneIndex}]\n\n${summaryContent}`

              // Queue the notification
              queueNotification(tmuxSession, message)

              // Kill pane after queuing (kill command has its own 3s wait)
              setTimeout(() => {
                try {
                  const kill = spawn(
                    "/Users/dotdev/.local/bin/agentwire",
                    ["kill", "--pane", String(paneIndex)],
                    { detached: true, stdio: "ignore" }
                  )
                  kill.unref()
                } catch {
                  // Ignore errors
                }
              }, 1000)
            } catch {
              // If we can't read the summary, just kill the pane
              try {
                const kill = spawn(
                  "/Users/dotdev/.local/bin/agentwire",
                  ["kill", "--pane", String(paneIndex)],
                  { detached: true, stdio: "ignore" }
                )
                kill.unref()
              } catch {
                // Ignore errors
              }
            }
          }
        }, 2000) // Wait 2s for OpenCode to settle
      } else if (config.parent) {
        // Orchestrator: direct notification to parent (less frequent)
        const message = `${sessionName} is idle`
        try {
          const child = spawn(
            "/Users/dotdev/.local/bin/agentwire",
            ["alert", "-q", "--to", config.parent, message],
            { detached: true, stdio: "ignore" }
          )
          child.unref()
        } catch {
          // Ignore errors
        }
      }
    },
  }
}

export default AgentWireNotifyPlugin
