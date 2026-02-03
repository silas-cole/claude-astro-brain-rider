# Brain Rider Architecture

## Current State (Jan 2026)

### What Works
- **TTS Output**: Piper TTS → USB Speaker (card 3) ✅
- **Moltbot Integration**: Text commands via Telegram ✅
- **Astro Control**: Voice commands via TTS ("Astro, [command]") ✅

### What Needs Work
- **Wake Word**: "hey_cowboy" model unreliable
- **Voice Input**: USB mic conflicts with speaker, silence detection issues
- **Dual Personality**: Brain Rider cowboy vs Silas Cole (Moltbot) - needs unification

## Proposed Architecture

### Voice I/O Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      USER INPUT                              │
├─────────────────────────────────────────────────────────────┤
│  Option A: Telegram text message                            │
│  Option B: Telegram voice message (transcribed by Moltbot)  │
│  Option C: Wake word "hey cowboy" (deprecated, unreliable)  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      MOLTBOT                                 │
│  - Main session handles text input                          │
│  - Silas Cole personality                                   │
│  - Processes commands, generates response                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   BRAIN RIDER (Pi 5)                         │
│  - silas-voice skill: TTS output via Piper                  │
│  - Astro commands: "Astro, [command]" via TTS               │
│  - Hardware: OLED eyes, RGB LEDs (future)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   AMAZON ASTRO                               │
│  - Responds to voice commands via Alexa                     │
│  - Movement, navigation, entertainment                      │
└─────────────────────────────────────────────────────────────┘
```

### Key Changes

1. **Moltbot becomes the brain** - All processing happens through Moltbot (me, Silas)
2. **Brain Rider becomes the body** - TTS output, hardware control only
3. **No duplicate LLM calls** - One personality, one processing path
4. **Voice input via Telegram** - More reliable than wake word

### File Structure

```
/home/cowboy/
├── clawd/                          # Moltbot workspace (Silas)
│   ├── SOUL.md                     # Silas personality
│   ├── skills/
│   │   ├── silas-voice/            # TTS skill
│   │   │   └── scripts/speak.sh
│   │   └── brain-rider/            # Control skill
│   │       └── SKILL.md
│   └── ...
│
└── claude-astro-brain-rider/       # Hardware daemon
    ├── src/
    │   ├── expression/tts.py       # Piper TTS (used by skill)
    │   └── hardware/               # Eyes, LEDs (future)
    ├── scripts/
    │   └── moltbot_*.py            # Integration scripts
    └── brain-rider.service         # Systemd service
```

## Voice Commands Quick Reference

### Speak through Pi
```bash
/home/cowboy/clawd/skills/silas-voice/scripts/speak.sh "Hello there"
```

### Control Astro
```bash
# Movement
/home/cowboy/clawd/skills/silas-voice/scripts/speak.sh "Astro, come here"
/home/cowboy/clawd/skills/silas-voice/scripts/speak.sh "Astro, go home"
/home/cowboy/clawd/skills/silas-voice/scripts/speak.sh "Astro, follow me"
/home/cowboy/clawd/skills/silas-voice/scripts/speak.sh "Astro, stop"

# Navigation
/home/cowboy/clawd/skills/silas-voice/scripts/speak.sh "Astro, go to the kitchen"

# Entertainment
/home/cowboy/clawd/skills/silas-voice/scripts/speak.sh "Astro, dance"
/home/cowboy/clawd/skills/silas-voice/scripts/speak.sh "Astro, act like a horse"
```

## Future Enhancements

1. **Hardware eyes/LEDs**: Enable OLED eyes and RGB brain LEDs
2. **Push-to-talk button**: Physical button on Pi to trigger listening
3. **Telegram voice messages**: Full voice-to-voice conversation loop
4. **Local wake word (optional)**: If needed, retrain with more samples

## Service Management

```bash
# Check status
systemctl status brain-rider

# Restart
sudo systemctl restart brain-rider

# Logs
journalctl -u brain-rider -f
```
