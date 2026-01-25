# AI Video Generation Guide

> Runway Gen-4 prompts for AgentWire teaser lifestyle shots

## Overview

We use AI-generated footage for lifestyle/B-roll shots, combined with real screen recordings of the actual product. This gives us professional quality without needing a film crew.

**Tool:** Runway Gen-4.5
**Output:** 5-10 second clips at 720p or 1080p
**Style:** Modern, minimal, tech aesthetic, natural lighting

---

## Shot List & Prompts

### Shot 1: Person on Couch with Tablet (Wide)
**Used in:** Act 1 opener (0:00-0:03)
**Duration needed:** 3-4 seconds

```
Prompt:
A person relaxed on a modern gray couch in a minimalist living room,
holding a tablet computer, natural daylight from large windows,
shallow depth of field, calm and focused expression,
tech startup aesthetic, cinematic lighting, 4K quality

Negative prompt (if supported):
office setting, desk, keyboard, dark room, cluttered background
```

**Camera:** Static or very slow push-in
**Notes:** We'll composite the actual portal UI onto the tablet screen in post

---

### Shot 2: Close-up Hands on Tablet
**Used in:** Act 1 PTT moment (0:03-0:05)
**Duration needed:** 2-3 seconds

```
Prompt:
Extreme close-up of hands holding a modern tablet,
finger pressing on the touchscreen, shallow depth of field,
soft natural lighting, clean minimal aesthetic,
professional tech product video style

Negative prompt:
face visible, cluttered background, dark lighting
```

**Camera:** Static, tight frame on hands and device
**Notes:** Finger should be pressing/holding, not swiping

---

### Shot 3: Person Reacting (Satisfied Nod)
**Used in:** Act 2 after TTS response (0:24-0:26)
**Duration needed:** 2-3 seconds

```
Prompt:
Medium shot of person on couch with tablet, giving a subtle satisfied nod,
slight smile, relaxed posture, modern living room background,
natural daylight, shallow depth of field,
authentic casual moment, not posed

Negative prompt:
exaggerated expression, looking at camera, office setting
```

**Camera:** Static or gentle movement
**Notes:** Should feel like a genuine "that worked" moment

---

### Shot 4: Lifestyle B-Roll - Coffee Moment
**Used in:** Optional cutaway during Act 2
**Duration needed:** 2-3 seconds

```
Prompt:
Person picking up coffee mug from side table while holding tablet,
casual morning routine, modern minimalist interior,
warm natural lighting, cozy tech lifestyle,
shallow depth of field, cinematic

Negative prompt:
office, desk, keyboard, standing
```

**Camera:** Slow motion optional
**Notes:** Reinforces "not at your desk" messaging

---

### Shot 5: Device on Table (Establishing)
**Used in:** Optional opener alternative
**Duration needed:** 2-3 seconds

```
Prompt:
Tablet laying on a wooden coffee table, modern living room,
morning light streaming through window, minimal aesthetic,
slight steam rising from coffee cup nearby,
calm atmosphere, tech product photography style

Negative prompt:
office desk, cluttered, dark room
```

**Camera:** Static or slow dolly
**Notes:** Could use as alternative opening before person picks it up

---

### Shot 6: Walking with Device
**Used in:** Optional B-roll
**Duration needed:** 3-4 seconds

```
Prompt:
Person walking through modern home hallway holding tablet,
casual clothing, natural movement, soft lighting,
following shot from behind,
lifestyle tech commercial aesthetic

Negative prompt:
running, office corridor, formal clothing
```

**Camera:** Following/tracking shot
**Notes:** Shows mobility - "code from anywhere"

---

## Runway Gen-4 Settings

| Setting | Recommended Value |
|---------|-------------------|
| Aspect Ratio | 16:9 |
| Duration | 5 seconds (extend if needed) |
| Resolution | 720p for drafts, 1080p for final |
| Motion | Low-Medium (we want subtle, not dynamic) |
| Style | Cinematic / Film |

---

## Generation Workflow

### Phase 1: Test Generations
1. Generate each shot at 720p, 5 seconds
2. Review for quality, consistency, usability
3. Note which prompts need adjustment
4. Re-generate problem shots with tweaked prompts

### Phase 2: Final Generations
1. Generate hero versions at 1080p
2. Generate 2-3 variations of each shot (options for editing)
3. Export all clips

### Phase 3: Compositing
1. Import AI clips into editor (DaVinci Resolve, Premiere, Final Cut)
2. Import real screen recordings
3. Composite tablet screens where needed (corner pin tracking)
4. Color grade to match
5. Add music and sound design

---

## Real Footage Needed (Can't AI Generate)

| Shot | How to Capture |
|------|----------------|
| Portal UI - full flow | Screen recording (OBS) |
| Claude working | Screen recording |
| TTS audio playing | Screen recording + actual audio |
| Safety block | Screen recording |
| Multi-session view | Screen recording |
| pip install animation | Screen recording or After Effects |

---

## Compositing the Tablet Screen

To make AI-generated "person holding tablet" shots show actual AgentWire UI:

1. **Track the tablet screen** - Use corner pin tracking in your editor
2. **Replace with screen recording** - Key out the blank screen, replace with portal footage
3. **Match lighting** - Adjust exposure/color of screen to match scene
4. **Add reflections** - Subtle screen reflections make it realistic

**Tools:**
- DaVinci Resolve (free) - Has good tracking
- After Effects - Best for complex composites
- Final Cut Pro - Simple tracking built-in

---

## Prompt Tips for Runway

1. **Be specific about lighting** - "natural daylight" vs "studio lighting" matters
2. **Describe the emotion** - "calm," "focused," "satisfied" guides the generation
3. **Include camera direction** - "static shot," "slow push-in," "shallow depth of field"
4. **Use negative prompts** - Exclude what you don't want
5. **Reference style** - "tech product video," "Apple commercial aesthetic," "cinematic"

---

## File Organization

```
video-assets/
├── ai-generated/
│   ├── shot1-couch-wide-v1.mp4
│   ├── shot1-couch-wide-v2.mp4
│   ├── shot2-hands-closeup-v1.mp4
│   └── ...
├── screen-recordings/
│   ├── portal-full-flow.mp4
│   ├── claude-working.mp4
│   ├── safety-block.mp4
│   └── ...
├── audio/
│   ├── tts-response-1.wav
│   ├── voice-command-1.wav
│   └── music-track.mp3
└── exports/
    ├── teaser-60s-v1.mp4
    ├── teaser-30s-v1.mp4
    └── teaser-vertical-v1.mp4
```

---

## Cost Estimate

| Item | Runway Cost |
|------|-------------|
| Test generations (20-30 clips) | ~$15-20 |
| Final generations (10-15 clips) | ~$10-15 |
| Re-generations/variations | ~$10 |
| **Total estimated** | **~$35-45** |

Standard plan ($15/mo) should cover initial generation. Pro plan ($35/mo) for more credits if needed.
