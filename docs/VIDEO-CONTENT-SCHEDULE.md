# AgentWire Video Content Schedule

> Video playlist for 1.0.0 launch and ongoing content

## Video Length Guidelines

Based on 2025-2026 best practices for developer tool content:

| Type | Length | Purpose |
|------|--------|---------|
| **Teaser** | 60-90s | Social media, first impression |
| **Feature Spotlight** | 3-5 min | Single feature deep enough to understand |
| **Getting Started** | 8-12 min | Complete onboarding journey |
| **Deep Dive** | 15-20 min | Advanced users, architecture |

**Key principle:** "The wrong length is any video that's one second longer than it needs to be."

---

## Launch Playlist (Priority Order)

### 1. 🎬 Launch Teaser (RECORD FIRST)
**Length:** 60-90 seconds
**Purpose:** Social media, Hacker News, Twitter/X, Reddit
**Priority:** 🔴 Must have for launch

**Script outline:**
```
0:00-0:10  Hook: You on couch with tablet, speaking to Claude
0:10-0:25  Quick cuts: voice command → Claude working → voice response
0:25-0:45  Multi-session view, worker spawning, parallel execution
0:45-0:55  Safety hook blocking dangerous command
0:55-1:00  "pip install agentwire-dev" + GitHub URL
1:00-1:05  Logo
```

**Key shots needed:**
- [ ] Tablet/phone showing portal (real device, not screen recording)
- [ ] Split screen: you speaking ↔ Claude responding
- [ ] Desktop control center with multiple sessions
- [ ] TTS audio actually playing from device

---

### 2. 🎬 Getting Started Tutorial
**Length:** 8-10 minutes
**Purpose:** Main YouTube video, documentation reference
**Priority:** 🔴 Must have for launch

**Chapters:**
```
0:00  Intro - What is AgentWire?
0:30  Prerequisites check (Python, tmux, Claude Code)
1:30  Installation (pip install agentwire-dev)
2:30  First run (agentwire init)
3:30  Generate SSL certs & open portal
4:30  Create first session
5:30  Push-to-talk demo
6:30  TTS response demo
7:30  Multi-device access (phone connecting)
8:30  Next steps & resources
```

---

### 3. 🎬 Voice Workflow Demo
**Length:** 3-4 minutes
**Purpose:** Show the core value prop in action
**Priority:** 🟡 High (can launch without, but want soon)

**Script outline:**
```
0:00-0:15  "What if you could code from your couch?"
0:15-1:00  Real task: "Add a dark mode toggle to settings"
1:00-2:00  Claude working, asking clarifying question via voice
2:00-2:30  You respond via voice, Claude continues
2:30-3:00  Task complete, Claude announces via TTS
3:00-3:30  Recap: no keyboard touched
```

---

## Post-Launch Playlist

### 4. 🎬 Multi-Agent Workflows
**Length:** 5-7 minutes
**Purpose:** Show orchestrator + worker pattern
**Priority:** 🟡 Week 1-2 after launch

**Content:**
- Voice orchestrator spawning workers
- Parallel task execution
- Workers reporting back via voice
- Real example: building a feature with 3 workers

---

### 5. 🎬 Safety Hooks Deep Dive
**Length:** 4-5 minutes
**Purpose:** Build trust, show safety features
**Priority:** 🟡 Week 1-2 after launch

**Content:**
- Why safety matters with autonomous agents
- Demo: trying dangerous commands, seeing blocks
- Customizing patterns
- Audit logs walkthrough

---

### 6. 🎬 Git Worktrees for Parallel Development
**Length:** 5-6 minutes
**Purpose:** Power user feature
**Priority:** 🟢 Week 2-4 after launch

**Content:**
- Problem: one agent, one branch
- Solution: worktree sessions
- Demo: 3 agents working same repo, different branches
- Merging results

---

### 7. 🎬 Remote Machine Setup
**Length:** 6-8 minutes
**Purpose:** Advanced setup guide
**Priority:** 🟢 Week 2-4 after launch

**Content:**
- Adding remote machines
- SSH tunnel setup
- Running sessions on GPU servers
- TTS server on remote machine

---

### 8. 🎬 TTS Setup Guide (RunPod)
**Length:** 5-7 minutes
**Purpose:** TTS backend setup
**Priority:** 🟢 Week 2-4 after launch

**Content:**
- RunPod account setup
- Deploying the TTS endpoint
- Configuring AgentWire
- Voice cloning basics

---

### 9. 🎬 OpenCode Integration
**Length:** 4-5 minutes
**Purpose:** Show it's not Claude-only
**Priority:** 🟢 Month 1

**Content:**
- OpenCode as alternative to Claude Code
- Same workflow, different agent
- Configuration differences

---

## Shorts/Clips (Repurpose from longer videos)

| Clip | Source | Length |
|------|--------|--------|
| "Voice command magic moment" | Launch teaser | 15-30s |
| "Safety hook in action" | Safety deep dive | 30-45s |
| "Spawn a worker" | Multi-agent video | 30-45s |
| "Code from your couch" | Voice workflow | 30-45s |

---

## Recording Checklist

### Equipment
- [ ] OBS or ScreenFlow for screen recording
- [ ] Clean audio (USB mic or good headset)
- [ ] Phone/tablet for portal shots
- [ ] Good lighting for any face cam

### Before Recording
- [ ] Clean desktop (hide personal bookmarks, notifications off)
- [ ] Fresh terminal with nice theme
- [ ] Test TTS is working
- [ ] Have real tasks ready (not fake demos)

### Post-Production
- [ ] Add chapters to YouTube
- [ ] Create thumbnail (consistent style)
- [ ] Write description with timestamps
- [ ] Add end screen with playlist links

---

## Thumbnail Style Guide

**Consistent elements:**
- AgentWire logo in corner
- Dark background (matches product)
- One key visual (phone, terminal, voice wave)
- Bold text overlay (3-4 words max)
- Green accent color (#2ea043)

---

## Distribution Plan

| Platform | Content | Timing |
|----------|---------|--------|
| YouTube | All videos | Primary home |
| Twitter/X | Teaser + clips | Launch day + weekly |
| Reddit (r/LocalLLaMA, r/ClaudeAI) | Teaser + Getting Started | Launch day |
| Hacker News | Teaser link | Launch day (Show HN) |
| Dev.to | Written + embedded video | Week 1 |
| LinkedIn | Professional angle clips | Week 1-2 |

---

## Timeline

| Week | Videos to Complete |
|------|-------------------|
| **Pre-launch** | 1. Teaser (required) |
| **Launch week** | 2. Getting Started |
| **Week 1** | 3. Voice Workflow Demo |
| **Week 2** | 4. Multi-Agent, 5. Safety Hooks |
| **Week 3-4** | 6. Worktrees, 7. Remote Machines |
| **Month 1** | 8. TTS Setup, 9. OpenCode |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Teaser views (week 1) | 1,000+ |
| Getting Started completion rate | 50%+ |
| Click-through to GitHub | 5%+ |
| pip installs from video refs | Track via UTM |
