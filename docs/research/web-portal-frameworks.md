# Web Portal Frameworks Research

> Research on web-based terminal emulators, AI chat interfaces, and voice-enabled web UIs for AgentWire's portal.

## Terminal Emulators for the Web

### xterm.js - The Industry Standard

**GitHub:** 19.7k stars | **Language:** TypeScript (96.6%)

[xterm.js](https://github.com/xtermjs/xterm.js) is the dominant choice for web-based terminal emulation. It powers VS Code's integrated terminal, Azure Cloud Shell, JupyterLab, GitHub Codespaces, and Replit.

**Key Features:**
- Full terminal compatibility (bash, vim, tmux, curses-based apps)
- GPU-accelerated rendering via WebGL2
- Unicode/CJK/emoji support with IME handling
- Zero external dependencies
- Screen reader accessibility
- Rich addon ecosystem

**Tech Stack:** TypeScript, Canvas/WebGL2 rendering, webpack

**Why it's the standard:** Battle-tested at massive scale (VS Code alone), active development, comprehensive API, and the fact that every major web-based terminal tool builds on it.

### Terminal Sharing Tools Built on xterm.js

| Tool | Stars | Language | Key Feature |
|------|-------|----------|-------------|
| [ttyd](https://github.com/tsl0922/ttyd) | 10.7k | C (56%), TypeScript (27%) | Fastest, built on libuv + libwebsockets |
| [GoTTY](https://github.com/yudai/gotty) | 18k+ | Go | Simple CLI, shares any command over web |
| [WeTTY](https://github.com/butlerx/wetty) | 5.1k | TypeScript (65%) | SSH gateway, Node.js based |
| [tmate](https://tmate.io/) | N/A | C (tmux fork) | Instant terminal sharing, read-only views |

**ttyd** is particularly relevant for AgentWire:
- C backend with libwebsockets (extremely fast)
- xterm.js frontend with WebGL acceleration
- SSL support, basic auth, reverse proxy compatible
- ZMODEM file transfer support
- Cross-platform (macOS, Linux, Windows)

### tmux-Specific Web Interfaces

| Project | Tech Stack | Notes |
|---------|------------|-------|
| [WebTMUX](https://github.com/nonoxz/webtmux) | Express + Socket.io + xterm.js | Full tmux session interaction |
| [webmux](https://github.com/nooesc/webmux) | Rust + Vue.js | High-performance, PWA support, mobile-optimized |
| [tmate](https://tmate.io/) | C (tmux fork) | Streams individual pane outputs, not entire window |

**webmux** stands out with:
- Rust backend for performance
- Vue.js + Tailwind frontend
- PWA with iOS safe area support
- Pure WebSocket communication (no REST)
- Session isolation

---

## AI Chat Interfaces

### Comparison Matrix

| Project | Stars | Frontend | Backend | Key Differentiator |
|---------|-------|----------|---------|-------------------|
| [Open WebUI](https://github.com/open-webui/open-webui) | 121k | Svelte (31%) | Python (32%) | Most feature-complete, enterprise-ready |
| [LobeChat](https://github.com/lobehub/lobe-chat) | 70k | Next.js/React | TypeScript (98.5%) | Best UX, MCP plugin ecosystem |
| [LibreChat](https://github.com/danny-avila/LibreChat) | 33k | React | TypeScript (70%) | Multi-provider, MCP support, code execution |
| [Chatbot UI](https://github.com/mckaywrigley/chatbot-ui) | 33k | Next.js | TypeScript (96%) | Cleanest codebase, Supabase backend |

### Open WebUI

The most comprehensive self-hosted AI chat platform.

**Tech Stack:**
- Frontend: Svelte (30.7%), JavaScript (29%)
- Backend: Python (32.4%)
- Database: SQLite/PostgreSQL
- Vector DB: 9 options (ChromaDB, PGVector, Qdrant, Milvus, etc.)

**Key Features:**
- Offline-first design
- RAG with multiple vector DB backends
- Voice/video calls with multiple STT/TTS providers
- LDAP/AD + SCIM 2.0 for enterprise
- Pipelines framework for custom logic
- Horizontal scaling with Redis

**Best for:** Teams needing enterprise features, RAG capabilities, and maximum flexibility.

### LobeChat

Best-in-class user experience with modern architecture.

**Tech Stack:**
- Next.js 14 with App Router
- TypeScript (98.5%)
- Zustand for state management
- Ant Design + custom lobe-ui components
- i18next for internationalization
- PostgreSQL for server-side deployment

**Key Features:**
- MCP plugin marketplace (one-click install)
- Knowledge base with file upload
- TTS/STT support
- Artifacts (live SVG/HTML preview)
- Branching conversations
- Desktop app + PWA

**Architecture Highlights:**
- Edge Runtime API for AI conversations
- Plugin Market with agent integration
- Code splitting + caching for performance
- Clean component separation (app/, components/, features/, store/)

**Best for:** Projects prioritizing UX and modern React patterns.

### LibreChat

True ChatGPT alternative with advanced features.

**Tech Stack:**
- TypeScript (70%), JavaScript (29%)
- Node.js/Express backend
- React frontend
- MongoDB + Redis
- Docker-first deployment

**Key Features:**
- 15+ AI provider integrations
- Code Interpreter (Python, Node, Go, C++, Java, PHP, Rust, Fortran)
- MCP support for tool integration
- Web search with reranking
- Custom agent building
- Generative UI (React, HTML, Mermaid artifacts)

**Best for:** Power users needing code execution and multi-provider support.

### Chatbot UI

Cleanest, most approachable codebase.

**Tech Stack:**
- Next.js + React
- TypeScript (96%)
- Supabase (PostgreSQL + Auth)
- Tailwind CSS

**Key Features:**
- Simple, focused feature set
- Easy Vercel deployment
- Local Ollama support
- Clean database schema

**Best for:** Starting point for custom chat UIs, learning reference.

---

## Voice-Enabled Web Interfaces

### Web Speech API

Built-in browser API for speech recognition and synthesis.

**Speech Recognition (STT):**
- Only works in Chrome/Chromium (sends audio to Google servers)
- Push-to-talk pattern: `start()` on keydown, `stop()` on keyup
- No offline support for recognition
- Free but limited control

**Speech Synthesis (TTS):**
- Works offline
- Uses system voices
- Cross-browser support

**Limitations:**
- Chrome-only for recognition
- Server-dependent (Google)
- No fine control over models

### Cloud STT APIs

| Provider | Latency | Accuracy | Best For |
|----------|---------|----------|----------|
| **Deepgram Nova-3** | <300ms | 90%+ | Real-time streaming, production |
| **OpenAI Whisper** | Higher | Highest | Batch processing, research |
| **AssemblyAI** | Medium | High | Noisy environments |
| **Google Cloud STT** | Low | High | Google ecosystem |

**Deepgram Nova-3** (Feb 2025):
- 54% lower WER vs competitors for streaming
- Native real-time streaming (not chunked like Whisper)
- Under 300ms latency in production
- Cost-effective for variable workloads

**OpenAI Whisper:**
- Open-source option (self-host)
- 680k hours of training data
- 5 model sizes (39M to 1.5B params)
- Best accuracy but higher latency
- 30-second chunk processing

### React Voice Libraries

| Library | Purpose | Notes |
|---------|---------|-------|
| [react-speech-recognition](https://www.npmjs.com/package/react-speech-recognition) | Web Speech API wrapper | Push-to-talk support, simple hook API |
| [@humeai/voice-react](https://www.npmjs.com/package/@humeai/voice-react) | Empathic voice interface | Emotion detection |
| [realtime-voice-ai](https://github.com/mhuzaifi0604/Realtime-VoiceChat) | OpenAI Realtime API | 4 pre-built UI variants |

**react-speech-recognition** is ideal for push-to-talk:
```typescript
// Hook-based API
const { transcript, listening, resetTranscript } = useSpeechRecognition()

// Push-to-talk pattern
onKeyDown={() => SpeechRecognition.startListening({ continuous: true })}
onKeyUp={() => SpeechRecognition.stopListening()}
```

---

## Real-Time Communication Patterns

### WebSocket vs Socket.io

| Aspect | Native WebSocket | Socket.io |
|--------|------------------|-----------|
| **Performance** | Faster (no overhead) | Slight overhead |
| **Reconnection** | Manual implementation | Built-in |
| **Fallbacks** | None | HTTP long-polling |
| **Rooms/Namespaces** | Manual | Built-in |
| **Browser Support** | Modern browsers | All browsers |

**Recommendation:** For terminal streaming, native WebSocket is preferred (ttyd, webmux both use it). Socket.io adds unnecessary overhead when you don't need fallbacks.

### WebSocket Best Practices for Terminal Streaming

**Connection Management:**
- Implement ping/pong heartbeats (ttyd uses 5-second intervals)
- Define idle timeouts to free resources
- Store session state externally for recovery
- Plan failover for server crashes

**Security:**
- Always use `wss://` (TLS)
- Authenticate during handshake (JWT, API keys)
- Validate all input from clients

**Performance:**
- Use binary encoding when possible (Protocol Buffers, MessagePack)
- Implement backpressure for slow clients
- Consider horizontal scaling with Redis pub/sub

**Architecture:**
```
Client (xterm.js)
    ↓ WebSocket
Load Balancer (sticky sessions)
    ↓
WebSocket Server (Node.js/Rust/C)
    ↓ PTY
tmux session
```

---

## Recommendations for AgentWire

### Terminal Component

**Use xterm.js directly** rather than wrapping ttyd/wetty:
- Already the standard (powers VS Code, etc.)
- TypeScript with excellent types
- WebGL acceleration built-in
- Direct control over styling and behavior

**Implementation approach:**
```typescript
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'

const terminal = new Terminal({
  rendererType: 'webgl', // GPU acceleration
  fontSize: 14,
  theme: { background: '#1a1a1a' }
})
```

### Chat Interface

**Borrow patterns from LobeChat:**
- Next.js App Router architecture
- Zustand for state (lightweight, simple)
- Component structure: `features/` for domain logic, `components/` for UI
- TypeScript throughout

**Key patterns to adopt:**
- Message streaming with loading states
- Conversation branching (optional)
- Code block rendering with syntax highlighting
- Copy/retry/edit actions on messages

### Voice Interface

**Hybrid approach:**
1. **Browser STT (dev/fallback):** react-speech-recognition for zero-config local dev
2. **Production STT:** Deepgram Nova-3 for low latency and accuracy
3. **TTS:** Keep existing backend routing (browser if connected, local speakers if not)

**Push-to-talk UI:**
- Spacebar or dedicated button
- Visual feedback (waveform, recording indicator)
- Transcript preview before sending

### Real-Time Architecture

**WebSocket-native approach:**
```
React Frontend
├── xterm.js (terminal)
├── Chat UI (messages)
└── Voice controls
    ↓ Single WebSocket connection
FastAPI/Node Backend
├── Terminal multiplexer (tmux)
├── LLM streaming
└── Voice routing
```

**Single connection benefits:**
- Simpler client code
- Unified auth/session handling
- Reduced overhead

### Tech Stack Summary

| Layer | Recommendation | Why |
|-------|---------------|-----|
| **Terminal** | xterm.js | Industry standard, GPU rendering |
| **Frontend** | Next.js + React | LobeChat patterns, TypeScript |
| **State** | Zustand | Simple, lightweight |
| **Styling** | Tailwind + shadcn/ui | Consistent with AgentWire |
| **WebSocket** | Native WS (not Socket.io) | Performance, control |
| **Voice STT** | Deepgram Nova-3 | Low latency streaming |
| **Voice TTS** | Existing backend | Already implemented |

---

## Sources

### Terminal Emulators
- [xterm.js GitHub](https://github.com/xtermjs/xterm.js)
- [ttyd GitHub](https://github.com/tsl0922/ttyd)
- [WeTTY GitHub](https://github.com/butlerx/wetty)
- [webmux GitHub](https://github.com/nooesc/webmux)
- [tmate](https://tmate.io/)

### AI Chat Interfaces
- [Open WebUI GitHub](https://github.com/open-webui/open-webui)
- [LobeChat GitHub](https://github.com/lobehub/lobe-chat)
- [LibreChat GitHub](https://github.com/danny-avila/LibreChat)
- [Chatbot UI GitHub](https://github.com/mckaywrigley/chatbot-ui)
- [5 Best Open Source Chat UIs for LLMs in 2025](https://poornaprakashsr.medium.com/5-best-open-source-chat-uis-for-llms-in-2025-11282403b18f)

### Voice & Speech
- [Web Speech API - MDN](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)
- [Whisper vs Deepgram 2025](https://deepgram.com/learn/whisper-vs-deepgram)
- [Best Speech-to-Text APIs 2025](https://deepgram.com/learn/best-speech-to-text-apis)
- [react-speech-recognition npm](https://www.npmjs.com/package/react-speech-recognition)

### WebSocket Architecture
- [WebSocket Architecture Best Practices - Ably](https://ably.com/topic/websocket-architecture-best-practices)
- [Socket.io vs WebSocket Guide 2025](https://velt.dev/blog/socketio-vs-websocket-guide-developers)
