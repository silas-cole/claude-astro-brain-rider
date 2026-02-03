# Wake Word Detection Fix Plan

## Executive Summary

The current "hey cowboy" wake word detection is **completely non-functional**. The custom ONNX model produces scores of 0.0008-0.0017 (0.08-0.17%) while the detection threshold is 0.5 (50%). The model never triggers.

**Recommended Fix:** Switch to the pre-trained "hey_jarvis" model (now downloaded and working) as an immediate fix, then optionally retrain a custom model later.

---

## Current Setup Analysis

### Configuration
- **Wake word:** "hey_cowboy"
- **Model path:** `models/hey_cowboy.onnx` (201 KB)
- **Threshold:** Not set (defaults to 0.5)
- **Library:** OpenWakeWord v0.6.0

### The Problem
Looking at the logs from `/home/cowboy/claude-astro-brain-rider/brain_rider.log`:

```
Prediction keys: ['hey_cowboy'], values: [np.float32(0.0010493398)]
Prediction keys: ['hey_cowboy'], values: [np.float32(0.0008608401)]
Prediction keys: ['hey_cowboy'], values: [np.float32(0.0016911328)]  # Peak!
```

**The custom model NEVER exceeds 0.002 (0.2%)** - far below the 0.5 threshold.

### Root Cause
The custom `hey_cowboy.onnx` model was trained with insufficient data or poor quality audio. At 201 KB, it's much smaller than the pre-trained `hey_jarvis_v0.1.onnx` (1.27 MB), suggesting it's undertrained.

---

## Recommendation: Use Pre-trained "hey_jarvis"

### Why hey_jarvis?
1. **Proven reliability** - Pre-trained by OpenWakeWord developers
2. **Better model size** - 1.27 MB vs 201 KB (more capacity)
3. **Phonetically similar** - "hey jarvis" works well as a substitute
4. **Already downloaded** - Models are now in the venv resources folder
5. **Cowboy-themed alternative** - Could also consider "hey_mycroft" or "alexa"

### Implementation Steps

#### Step 1: Update config.yaml

```yaml
system:
  wake_word: "hey_jarvis"
  # Remove or comment out custom model path to use built-in:
  # wake_word_model_path: "models/hey_cowboy.onnx"
  wake_word_threshold: 0.5  # Explicitly set threshold
  log_level: "DEBUG"
```

#### Step 2: Apply the change

```bash
cd /home/cowboy/claude-astro-brain-rider

# Backup current config
cp config.yaml config.yaml.bak

# Edit config.yaml - comment out wake_word_model_path, set wake_word to hey_jarvis
# Or use this command:
cat > config.yaml << 'EOF'
system:
  wake_word: "hey_jarvis"
  # wake_word_model_path: "models/hey_cowboy.onnx"  # Disabled - using built-in
  wake_word_threshold: 0.5
  log_level: "DEBUG"

audio:
  input_device_index: null
  output_device_index: null
  sample_rate: 16000
  chunk_size: 1024
  alsa_output_device: "speaker"

stt:
  model_size: "tiny.en"
  compute_type: "int8"

tts:
  english_voice: "en_US-lessac-medium"
  mandarin_voice: "zh_CN-huayan-medium"
  playback_speed: 1.0

llm:
  model: "claude-3-5-haiku-latest"
  max_tokens: 150

hardware:
  oled_left_addr: 0x3C
  oled_right_addr: 0x3D
  led_pin: 18
  led_count: 8
EOF
```

#### Step 3: Restart the service

```bash
sudo systemctl restart brain-rider
sudo journalctl -u brain-rider -f  # Watch logs
```

#### Step 4: Test

Say "Hey Jarvis" clearly and watch for detection in the logs:
```
Wake word DETECTED: hey_jarvis (Score: 0.85 > 0.5)
```

---

## Alternative Options

### Option A: Lower Threshold (NOT RECOMMENDED)

Could lower threshold to 0.001 to catch the weak hey_cowboy scores, but this will cause constant false positives. The model simply doesn't distinguish the wake word from background noise.

### Option B: Retrain Custom "Hey Cowboy" Model

If you really want "hey cowboy" as the wake word:

1. **Use Google Colab Training Notebook**
   - Visit: https://github.com/dscripka/openWakeWord
   - Use the training notebook with better parameters:
     - More training epochs (increase from default)
     - Better negative samples (diverse background noise)
     - More positive samples (different voices, accents)

2. **Record Real Audio Samples**
   - Record 50-100 samples of "hey cowboy" from different people
   - Include variations in pitch, speed, distance from mic
   - Use the USB mic to ensure audio characteristics match

3. **Use Custom Verifier**
   OpenWakeWord has a `train_custom_verifier` function that can fine-tune detection for your voice:
   ```python
   from openwakeword import train_custom_verifier
   # Record 5-10 samples of yourself saying the wake word
   # This creates a personalized model
   ```

### Option C: Picovoice Porcupine (Commercial)

For production-quality wake word detection:

```bash
pip install pvporcupine
```

- **Pros:** Very accurate, low false positives, custom wake words
- **Cons:** Requires API key, commercial license for deployment
- **Free tier:** Limited to built-in keywords (Porcupine, Bumblebee, etc.)

Would require code changes in `wakeword.py` to use Porcupine API.

### Option D: Use Voice Activity Detection (VAD) + Keyword Spotting

Instead of wake word, use:
1. VAD to detect when someone is speaking
2. Run full transcription
3. Look for "hey cowboy" in the transcript

This is more resource-intensive but works with any phrase.

---

## Code Changes (if needed)

The current `wakeword.py` already handles both built-in and custom models correctly. No code changes needed for Option A (hey_jarvis).

For threshold tuning, add to config.yaml:
```yaml
system:
  wake_word_threshold: 0.5  # Adjust 0.3-0.7 based on testing
```

---

## Testing Checklist

After switching to hey_jarvis:

1. [ ] Service starts without errors
2. [ ] Logs show: `Using built-in wake word: hey_jarvis`
3. [ ] Logs show: `Loaded model keys: ['hey_jarvis']`
4. [ ] Saying "Hey Jarvis" triggers detection (score > 0.5)
5. [ ] Normal conversation doesn't trigger false positives
6. [ ] Detection works from 1-2 meters away

---

## Quick Fix Commands

```bash
# SSH to the Pi
ssh cowboy@cowboy-claude.local

# Navigate to project
cd /home/cowboy/claude-astro-brain-rider

# Update config to use hey_jarvis
sed -i 's/wake_word: "hey_cowboy"/wake_word: "hey_jarvis"/' config.yaml
sed -i 's/^  wake_word_model_path:/#  wake_word_model_path:/' config.yaml

# Add explicit threshold
grep -q 'wake_word_threshold' config.yaml || sed -i '/wake_word:/a\  wake_word_threshold: 0.5' config.yaml

# Restart service
sudo systemctl restart brain-rider

# Watch logs
sudo journalctl -u brain-rider -f
```

---

## Summary

| Approach | Effort | Reliability | Wake Word |
|----------|--------|-------------|-----------|
| **hey_jarvis (RECOMMENDED)** | 5 min | High | "Hey Jarvis" |
| Retrain hey_cowboy | 2-4 hours | Medium | "Hey Cowboy" |
| Porcupine | 1 hour | Very High | Custom (paid) |
| VAD + keyword | 2 hours | Medium | Any phrase |

**Immediate action:** Switch to hey_jarvis now, then optionally retrain a custom model later when you have time to collect proper training data.
