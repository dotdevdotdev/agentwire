# AgentWire Website Vision

> Prompt for orchestrator session. Iterate until ready for execution.

## What is AgentWire?

Voice interface for AI coding agents. Push-to-talk from any device to tmux sessions running Claude Code or OpenCode. Talk to your code.

## Target Audience

- Developers who use AI coding assistants (Claude Code, Cursor, etc.)
- Power users who want hands-free coding
- Teams managing multiple agent sessions

## Key Messages

1. **Voice-first** - Talk to your AI coding agent naturally
2. **Multi-agent** - Orchestrate multiple agents working in parallel
3. **Any device** - Control from phone, tablet, or desktop
4. **Open source** - Run it yourself, customize it

## Hero Copy

**Headline:** Talk to your code.

**Subhead:** Voice interface for AI coding agents. Push-to-talk from any device to Claude Code, OpenCode, or any terminal session.

**Use cases to highlight:**
- "Refactor while you make coffee"
- "Review PRs from your phone"
- "Orchestrate parallel agents with your voice"

## Site Structure

| Page | Priority | Purpose |
|------|----------|---------|
| Home | High | Hero, How It Works, demo GIF, CTA to Quickstart |
| Quickstart | High | Step-by-step install and first use |
| Features | Medium | Detailed feature breakdown (can be homepage section) |
| Docs | Low | Link to GitHub docs (not embedded) |

## Homepage Sections (in order)

1. **Hero** - Headline, subhead, demo GIF, "Get Started" CTA
2. **How It Works** - 3-step visual flow:
   - Install: `brew install agentwire` or npm
   - Connect: Point to your tmux session
   - Talk: Push-to-talk from any device
3. **Features Grid** - 4-6 key features with icons
4. **Demo GIF** - Simple screen recording of voice interaction (easy to update)
5. **CTA** - Link to Quickstart + GitHub

## Design Direction

- Clean, minimal, developer-focused
- Dark mode default (terminal aesthetic)
- Monospace accents for code/commands
- High contrast for readability
- Simple animations (fade-in on scroll)

## Color Palette

```css
--background: #0a0a0a
--foreground: #e5e5e5
--primary: #22c55e (green - voice/active indicator)
--muted: #27272a
--border: #3f3f46
```

## Tech Stack

- **Next.js** static export (familiar, proven)
- **Tailwind CSS** for styling
- **Deploy to Vercel** (zero config)
- No backend needed

## Demo GIF Approach

Keep it simple and easy to update:
- Screen recording of terminal with voice waveform overlay
- Show: user speaks → agent responds → code changes
- 10-15 seconds max
- Store as `/public/demo.gif`
- Can be swapped out anytime without code changes

## Worker Tasks

| Worker | Scope | Files |
|--------|-------|-------|
| 1. Project Setup | Next.js + Tailwind + layout | `package.json`, `tailwind.config.js`, `app/layout.tsx` |
| 2. Homepage | Hero + How It Works + Features | `app/page.tsx`, `components/Hero.tsx`, `components/HowItWorks.tsx`, `components/Features.tsx` |
| 3. Quickstart | Install guide page | `app/quickstart/page.tsx` |
| 4. Shared Components | Nav, Footer, Button, etc. | `components/Nav.tsx`, `components/Footer.tsx`, `components/ui/*` |

## Success Criteria

- [ ] Site builds and runs locally (`npm run dev`)
- [ ] Homepage renders with all sections
- [ ] Quickstart page has clear install steps
- [ ] Responsive design (mobile-first)
- [ ] Copy is clear and compelling
- [ ] Easy to swap demo GIF
- [ ] Deploys to Vercel without issues
