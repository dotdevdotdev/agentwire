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
Wide angle shot. A person relaxed on a modern gray couch in a minimalist
living room, holding a tablet computer, natural daylight from large windows,
shallow depth of field, calm and focused expression, tech startup aesthetic,
cinematic lighting, 4K quality. The camera remains steady with minimal movement.
```

**Notes:** We'll composite the actual portal UI onto the tablet screen in post

---

### Shot 2: Close-up Hands on Tablet
**Used in:** Act 1 PTT moment (0:03-0:05)
**Duration needed:** 2-3 seconds

```
Prompt:
Extreme close-up shot, macro lens. Hands holding a modern tablet,
finger pressing and holding on the touchscreen, shallow depth of field,
soft natural lighting, clean minimal aesthetic, professional tech product
video style. The camera remains perfectly still, locked off on a tripod.
```

**Notes:** Finger should be pressing/holding, not swiping

---

### Shot 3: Person Reacting (Satisfied Nod)
**Used in:** Act 2 after TTS response (0:24-0:26)
**Duration needed:** 2-3 seconds

```
Prompt:
Medium shot, 50mm lens. Person on couch with tablet giving a subtle satisfied
nod, slight smile, relaxed posture, modern living room background, natural
daylight, shallow depth of field, authentic casual moment, not posed, not
looking at camera. The camera remains steady with minimal organic movement.
```

**Notes:** Should feel like a genuine "that worked" moment

---

### Shot 4: Lifestyle B-Roll - Coffee Moment
**Used in:** Optional cutaway during Act 2
**Duration needed:** 2-3 seconds

```
Prompt:
Medium close-up shot, 85mm lens. Person picking up coffee mug from side table
while holding tablet in other hand, casual morning routine, modern minimalist
interior, warm natural lighting, cozy tech lifestyle, shallow depth of field,
cinematic. The camera moves forward slowly with smooth organic motion to push
in slightly closer to the scene.
```

**Notes:** Reinforces "not at your desk" messaging

---

### Shot 5: Device on Table (Establishing)
**Used in:** Optional opener alternative
**Duration needed:** 2-3 seconds

```
Prompt:
Wide angle establishing shot, 35mm lens. Tablet laying on a wooden coffee
table, modern living room, morning light streaming through window, minimal
aesthetic, slight steam rising from coffee cup nearby, calm atmosphere, tech
product photography style. The camera performs a slow gentle dolly movement
from left to right, gliding smoothly past the scene.
```

**Notes:** Could use as alternative opening before person picks it up

---

### Shot 6: Walking with Device
**Used in:** Optional B-roll
**Duration needed:** 3-4 seconds

```
Prompt:
Wide angle shot, 35mm lens. Modern home hallway with soft natural lighting.
Person walks casually through frame from left to right holding a tablet,
casual clothing, relaxed pace. The camera remains completely static as
the subject passes through the scene.
```

**Notes:** Shows mobility - "code from anywhere". Static camera with moving subject is more reliable than tracking shots.

---

## Camera Motion Language

Runway Gen-4.5 responds to natural camera direction in prompts. Use descriptive language:

| Motion Type | Prompt Language |
|-------------|-----------------|
| **Static** | "The camera remains steady with minimal movement" or "locked off on a tripod" |
| **Push in** | "The camera moves forward with smooth organic motion to push in closer" |
| **Dolly** | "The camera performs a slow gentle dolly movement from left to right" |
| **Tracking** | "The camera follows the subject with smooth steadicam motion" |
| **Pull back** | "The camera slowly pulls back to reveal the wider scene" |
| **Crane up** | "The camera rises smoothly upward in a crane motion" |

**Lens language also helps:**
- "Wide angle lens" / "35mm lens" - broader field of view
- "50mm lens" - natural perspective
- "85mm lens" / "telephoto" - compressed, shallow DOF
- "Macro lens" - extreme close-up detail

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

1. **Start with shot type and lens** - "Wide angle shot, 35mm lens" or "Medium close-up, 85mm lens"
2. **Be specific about lighting** - "natural daylight" vs "studio lighting" matters
3. **Describe the emotion** - "calm," "focused," "satisfied" guides the generation
4. **End with camera motion** - "The camera remains steady" or "The camera pushes in slowly"
5. **Use descriptive motion language** - Full sentences describing what the camera does
6. **Reference style** - "tech product video," "Apple commercial aesthetic," "cinematic"

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
