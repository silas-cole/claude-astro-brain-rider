# Unihiker K10 Integration Design

**Brain Rider Voice/Camera Input Station**

*Design Document v1.0 - February 2026*

---

## Overview

Transform the DFRobot Unihiker K10 into a dedicated **voice/camera input station** for the Brain Rider system:

- **K10 handles**: Wake word detection, audio capture, camera input
- **Pi 5 handles**: STT, TTS output, Astro robot control
- **Moltbot handles**: The "brain" - all reasoning and response generation

### Why K10?

| Advantage | Explanation |
|-----------|-------------|
| Dedicated input device | Separates mic from speaker, eliminating feedback issues |
| Built-in display | Shows listening status, visual feedback |
| Portable | Can be placed closer to the user |
| Low power | RK3308 is efficient, runs on USB power |
| Camera | Visual context for queries |

---

## Hardware Specs

### Unihiker K10

```
┌─────────────────────────────────────────┐
│          UNIHIKER K10                   │
├─────────────────────────────────────────┤
│  CPU:      RK3308 ARM64 4-core 1.2GHz   │
│  RAM:      512MB DDR3                   │
│  Storage:  16GB eMMC                    │
│  OS:       Debian 10 (Buster)           │
│  Python:   3.7+ pre-installed           │
├─────────────────────────────────────────┤
│  AUDIO                                  │
│  • Capacitive silicon microphone        │
│  • Passive buzzer (alerts only)         │
├─────────────────────────────────────────┤
│  VISUAL                                 │
│  • 2.8" touchscreen (240x320)           │
│  • Camera (K10 only, not M10)           │
│  • Blue LED indicator                   │
├─────────────────────────────────────────┤
│  CONNECTIVITY                           │
│  • WiFi 2.4GHz                          │
│  • Bluetooth 4.0                        │
│  • USB Type-C (power + data)            │
│  • I2C, UART, SPI, ADC, PWM             │
├─────────────────────────────────────────┤
│  SENSORS                                │
│  • 6-axis IMU                           │
│  • Light sensor                         │
│  • Buttons: Home, A, B                  │
└─────────────────────────────────────────┘
```

### Network Access

| Connection | IP Address | Notes |
|------------|-----------|-------|
| USB to PC | `10.1.2.3` | Fixed when connected via USB |
| WiFi | DHCP | Join same network as Pi |
| SSH | Port 22 | User: `root`, Pass: `dfrobot` |

---

## Recommended Architecture: Hybrid (Option B)

K10 does wake word detection locally, streams audio to Pi for STT.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          HYBRID ARCHITECTURE                            │
│               K10 does wake word, streams audio to Pi                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌────────────────────────────────────────────────────────────┐        │
│   │                     UNIHIKER K10                           │        │
│   │                                                            │        │
│   │  ┌─────────────────┐    ┌─────────────────┐               │        │
│   │  │  Wake Word      │    │  Visual Status  │               │        │
│   │  │  Detection      │    │  (Touchscreen)  │               │        │
│   │  │  (OpenWakeWord) │    │  🔴 Idle        │               │        │
│   │  └────────┬────────┘    │  🟡 Listening   │               │        │
│   │           │             │  🟢 Processing  │               │        │
│   │           │ trigger     └─────────────────┘               │        │
│   │           ▼                                               │        │
│   │  ┌─────────────────┐                                      │        │
│   │  │  Audio Capture  │──┐                                   │        │
│   │  │  + VAD Chunking │  │                                   │        │
│   │  └─────────────────┘  │                                   │        │
│   │                       │ audio bytes                       │        │
│   │  ┌─────────────────┐  │                                   │        │
│   │  │  Camera Snap    │──┼─────────────────┐                 │        │
│   │  │  (optional)     │  │                 │                 │        │
│   │  └─────────────────┘  │                 │                 │        │
│   │                       │                 │                 │        │
│   └───────────────────────┼─────────────────┼─────────────────┘        │
│                           │                 │                          │
│                           │ WebSocket       │ HTTP POST                │
│                           │ audio stream    │ image                    │
│                           ▼                 ▼                          │
│   ┌──────────────────────────────────────────────────────────┐         │
│   │                    PI 5 + MOLTBOT                        │         │
│   │                                                          │         │
│   │   ┌───────────────┐    ┌───────────────┐                 │         │
│   │   │ Audio Receiver│───►│ STT (Whisper) │                 │         │
│   │   │ WebSocket     │    │ faster-whisper│                 │         │
│   │   └───────────────┘    └───────┬───────┘                 │         │
│   │                                │ text                    │         │
│   │                                ▼                         │         │
│   │   ┌────────────────────────────────────────────┐         │         │
│   │   │              MOLTBOT AGENT                 │         │         │
│   │   │  • Process user input                      │         │         │
│   │   │  • Generate response                       │         │         │
│   │   │  • Trigger TTS                             │         │         │
│   │   │  • Send Astro commands                     │         │         │
│   │   └────────────────────────────────────────────┘         │         │
│   │                                                          │         │
│   │   ┌───────────────┐    ┌───────────────┐                 │         │
│   │   │  Piper TTS    │───►│  USB Speaker  │                 │         │
│   │   └───────────────┘    └───────────────┘                 │         │
│   └──────────────────────────────────────────────────────────┘         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Option B?

| Factor | Assessment |
|--------|------------|
| **RAM** | 512MB is sufficient for OpenWakeWord (~50-100MB) but risky for Vosk STT (~300MB) |
| **Latency** | Wake word on-device = instant. Audio streaming adds ~100-200ms (acceptable) |
| **Reliability** | Fewer moving parts on K10 = fewer things to break |
| **Extensibility** | Visual feedback on screen, camera integration, motion detection possible |

---

## Software Requirements

### K10 Dependencies

```bash
# System packages
apt update
apt install -y python3-pip portaudio19-dev ffmpeg alsa-utils

# Python packages
pip3 install \
    openwakeword \
    sounddevice \
    numpy \
    websocket-client \
    requests \
    Pillow
```

### Wake Word Comparison

| Engine | RAM Usage | Free | Custom Words |
|--------|-----------|------|--------------|
| **OpenWakeWord** | ~50-100 MB | ✅ | ✅ Train own |
| Porcupine | ~50 MB | ⚠️ Limited | ✅ Console |
| Vosk-based | ~300 MB | ✅ | ⚠️ Complex |

**Recommendation**: OpenWakeWord - open source, trainable, proven on Pi 3.

---

## Communication Protocol

### WebSocket: Audio Stream

**Endpoint**: `ws://<pi-ip>:8765/audio`

#### K10 → Pi Messages

```json
// Wake word triggered
{"type": "wake", "timestamp": 1706745600.123, "wake_word": "hey_jarvis", "confidence": 0.87}

// Audio chunk
{"type": "audio", "format": "pcm_s16le", "sample_rate": 16000, "data": "<base64>"}

// End of utterance
{"type": "end_utterance", "duration_ms": 2340}

// Camera snapshot (optional)
{"type": "image", "format": "jpeg", "data": "<base64>"}
```

#### Pi → K10 Messages

```json
// Acknowledge wake
{"type": "ack_wake", "status": "listening"}

// STT result
{"type": "transcription", "text": "what time is it"}

// Status updates
{"type": "status", "state": "processing|speaking|idle"}
```

---

## Setup Instructions

### Step 1: K10 Initial Setup

```bash
# SSH into K10 (via USB)
ssh root@10.1.2.3
# Password: dfrobot

# Set hostname
hostnamectl set-hostname brain-rider-input

# Configure WiFi
nmcli device wifi connect "YOUR_SSID" password "YOUR_PASSWORD"

# Get WiFi IP
ip addr show wlan0 | grep inet
```

### Step 2: Install Dependencies

```bash
# Audio dependencies
apt install -y portaudio19-dev python3-pyaudio ffmpeg alsa-utils

# Test microphone
arecord -l  # List devices
arecord -d 3 -f S16_LE -r 16000 test.wav
aplay test.wav

# Python packages
pip3 install openwakeword sounddevice numpy websocket-client
```

### Step 3: Download Wake Word Models

```bash
mkdir -p /root/brain-rider/models
python3 -c "import openwakeword; openwakeword.utils.download_models()"
```

### Step 4: Create Service

```bash
cat > /etc/systemd/system/brain-rider-input.service << 'EOF'
[Unit]
Description=Brain Rider Input Station
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /root/brain-rider/src/main.py
WorkingDirectory=/root/brain-rider
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable brain-rider-input
```

---

## Code: K10 Client (Simplified)

**File**: `/root/brain-rider/src/main.py`

```python
#!/usr/bin/env python3
"""Brain Rider Input Station - K10 Client"""

import time
import json
import base64
import logging
import queue

import numpy as np
import sounddevice as sd
import websocket
from openwakeword.model import Model as WakeWordModel

try:
    from unihiker import GUI
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

CONFIG = {
    "pi_host": "cowboy-claude.local",
    "ws_port": 8765,
    "sample_rate": 16000,
    "chunk_ms": 80,
    "wake_words": ["hey_jarvis"],
    "wake_threshold": 0.5,
    "silence_threshold": 0.02,
    "silence_ms": 1500,
    "max_record_sec": 10,
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("k10")


class StatusDisplay:
    STATES = {
        "idle": ("#333", "Say 'Hey Cowboy'"),
        "listening": ("#FA0", "Listening..."),
        "processing": ("#0A0", "Processing..."),
        "speaking": ("#06C", "Speaking..."),
    }
    
    def __init__(self):
        self.gui = GUI() if HAS_GUI else None
        self._text = None
        if self.gui:
            self.gui.fill_rect(0, 0, 240, 320, "#000")
            self._text = self.gui.draw_text("Say 'Hey Cowboy'", 120, 160, 
                                             font_size=16, origin="center")
    
    def set_state(self, state):
        if not self.gui:
            logger.info(f"State: {state}")
            return
        color, text = self.STATES.get(state, self.STATES["idle"])
        self.gui.fill_rect(0, 0, 240, 320, color)
        if self._text:
            self._text.config(text=text)


class AudioCapture:
    def __init__(self, cfg):
        self.sr = cfg["sample_rate"]
        self.chunk = int(self.sr * cfg["chunk_ms"] / 1000)
        self.silence_thresh = cfg["silence_threshold"]
        self.silence_chunks = int(cfg["silence_ms"] / cfg["chunk_ms"])
        self.max_chunks = int(cfg["max_record_sec"] * 1000 / cfg["chunk_ms"])
        self.queue = queue.Queue()
        
    def start(self):
        def cb(data, frames, t, status):
            self.queue.put(data.copy())
        self.stream = sd.InputStream(
            samplerate=self.sr, channels=1, dtype=np.int16,
            blocksize=self.chunk, callback=cb
        )
        self.stream.start()
    
    def get_chunk(self, timeout=1.0):
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def record_until_silence(self):
        chunks = []
        silence = 0
        while len(chunks) < self.max_chunks:
            c = self.get_chunk(0.5)
            if c is None:
                continue
            chunks.append(c)
            rms = np.sqrt(np.mean(c.astype(float)**2)) / 32768
            if rms < self.silence_thresh:
                silence += 1
                if silence >= self.silence_chunks:
                    break
            else:
                silence = 0
        return np.concatenate(chunks).tobytes()


class WakeDetector:
    def __init__(self, cfg):
        self.thresh = cfg["wake_threshold"]
        self.model = WakeWordModel(wakeword_models=cfg["wake_words"])
    
    def check(self, chunk):
        preds = self.model.predict(chunk)
        for word, score in preds.items():
            if score > self.thresh:
                return (word, score)
        return None


class PiConnection:
    def __init__(self, cfg):
        self.url = f"ws://{cfg['pi_host']}:{cfg['ws_port']}/audio"
        self.ws = None
        
    def connect(self):
        try:
            self.ws = websocket.create_connection(self.url, timeout=5)
            return True
        except:
            return False
    
    def send(self, msg):
        if self.ws:
            self.ws.send(json.dumps(msg))
    
    def recv(self, timeout=1.0):
        if not self.ws:
            return None
        try:
            self.ws.settimeout(timeout)
            return json.loads(self.ws.recv())
        except:
            return None


def main():
    display = StatusDisplay()
    audio = AudioCapture(CONFIG)
    wake = WakeDetector(CONFIG)
    conn = PiConnection(CONFIG)
    
    display.set_state("idle")
    
    while not conn.connect():
        logger.warning("Retrying Pi connection...")
        time.sleep(5)
    
    audio.start()
    logger.info("Ready")
    
    while True:
        chunk = audio.get_chunk()
        if chunk is None:
            continue
            
        det = wake.check(chunk)
        if det:
            word, conf = det
            logger.info(f"Wake: {word} ({conf:.2f})")
            display.set_state("listening")
            
            conn.send({"type": "wake", "wake_word": word, "confidence": conf})
            
            start = time.time()
            audio_bytes = audio.record_until_silence()
            dur = int((time.time() - start) * 1000)
            
            display.set_state("processing")
            conn.send({
                "type": "audio",
                "format": "pcm_s16le",
                "sample_rate": CONFIG["sample_rate"],
                "data": base64.b64encode(audio_bytes).decode()
            })
            conn.send({"type": "end_utterance", "duration_ms": dur})
            
            # Wait for response
            while True:
                msg = conn.recv(5.0)
                if not msg:
                    break
                if msg.get("type") == "status":
                    state = msg.get("state", "idle")
                    if state == "speaking":
                        display.set_state("speaking")
                    elif state == "idle":
                        break
            
            display.set_state("idle")


if __name__ == "__main__":
    main()
```

---

## Code: Pi Audio Receiver

**File**: `/home/cowboy/claude-astro-brain-rider/src/communication/audio_receiver.py`

```python
#!/usr/bin/env python3
"""Audio Receiver - Pi 5 WebSocket Server"""

import asyncio
import json
import base64
import logging

import websockets
import numpy as np

# Import existing services
import sys
sys.path.insert(0, '/home/cowboy/claude-astro-brain-rider')
from src.perception.stt import STTService
from src.expression.tts import TTSService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("receiver")


class AudioReceiver:
    def __init__(self, config):
        self.host = "0.0.0.0"
        self.port = 8765
        self.stt = STTService(config)
        self.tts = TTSService(config)
        self.buffer = bytearray()
    
    async def handle(self, ws):
        logger.info(f"K10 connected: {ws.remote_address}")
        try:
            async for msg in ws:
                await self.process(ws, json.loads(msg))
        except websockets.ConnectionClosed:
            logger.info("K10 disconnected")
    
    async def process(self, ws, msg):
        t = msg.get("type")
        
        if t == "wake":
            self.buffer = bytearray()
            await ws.send(json.dumps({"type": "ack_wake", "status": "listening"}))
            
        elif t == "audio":
            self.buffer.extend(base64.b64decode(msg["data"]))
            
        elif t == "end_utterance":
            if len(self.buffer) < 3200:
                await self.send_status(ws, "idle")
                return
            
            audio = np.frombuffer(self.buffer, dtype=np.int16)
            text = await self.transcribe(audio)
            
            if text:
                await ws.send(json.dumps({"type": "transcription", "text": text}))
                await self.respond(ws, text)
            
            self.buffer = bytearray()
            await self.send_status(ws, "idle")
    
    async def transcribe(self, audio):
        loop = asyncio.get_event_loop()
        def stt():
            segs, _ = self.stt.model.transcribe(
                audio.astype(np.float32) / 32768.0, language="en"
            )
            return " ".join(s.text for s in segs).strip()
        return await loop.run_in_executor(None, stt)
    
    async def respond(self, ws, text):
        await self.send_status(ws, "processing")
        
        # TODO: Route through Moltbot API
        # For now, use local fallback
        from src.cognition.llm_client import LLMClient
        llm = LLMClient()
        response = llm.generate_response(text)
        
        await self.send_status(ws, "speaking")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.tts.speak(response))
    
    async def send_status(self, ws, state):
        await ws.send(json.dumps({"type": "status", "state": state}))
    
    async def run(self):
        async with websockets.serve(self.handle, self.host, self.port):
            logger.info(f"Listening on ws://{self.host}:{self.port}")
            await asyncio.Future()


if __name__ == "__main__":
    import yaml
    with open("/home/cowboy/claude-astro-brain-rider/config/config.yaml") as f:
        config = yaml.safe_load(f)
    
    server = AudioReceiver(config)
    asyncio.run(server.run())
```

---

## Future Enhancements

1. **Camera Integration**: Snap photo on wake word, send as context
2. **Display UI**: Show transcription, response text on K10 screen
3. **Custom Wake Word**: Train "hey cowboy" via Google Colab
4. **Multi-room**: Multiple K10 units reporting to single Pi
5. **Gesture Control**: Use IMU for motion-triggered actions

---

## Related Files

- `ARCHITECTURE.md` - Brain Rider system overview
- `WAKEWORD_PLAN.md` - Wake word training options
- `config/config.yaml` - Current configuration

---

*Created: February 2026*
*Author: Silas (sub-agent research + main session synthesis)*
