#!/bin/bash
# Audio Diagnostic Script for Brain Rider
# Run this on the Raspberry Pi to test mic and speaker

echo "========================================"
echo "   Brain Rider Audio Diagnostics"
echo "========================================"
echo ""

# Check user groups
echo "1. Checking user groups..."
echo "   Current user: $(whoami)"
echo "   Groups: $(groups)"
REQUIRED_GROUPS="audio i2c gpio spi"
for grp in $REQUIRED_GROUPS; do
    if groups | grep -q "\b$grp\b"; then
        echo "   ✓ In '$grp' group"
    else
        echo "   ✗ NOT in '$grp' group - run: sudo usermod -aG $grp $(whoami)"
    fi
done
echo ""

# Check USB devices
echo "2. USB devices connected:"
lsusb | grep -i audio || lsusb | grep -iE "(sound|mic|speaker)" || echo "   (No audio-specific USB devices found by name)"
lsusb
echo ""

# Check ALSA playback devices
echo "3. ALSA playback devices (speakers):"
aplay -l 2>/dev/null || echo "   ERROR: aplay not found or no devices"
echo ""

# Check ALSA recording devices
echo "4. ALSA recording devices (microphones):"
arecord -l 2>/dev/null || echo "   ERROR: arecord not found or no devices"
echo ""

# Check for persistent device names
echo "5. Checking for persistent USB audio names..."
if aplay -L 2>/dev/null | grep -q "UsbSpeaker"; then
    echo "   ✓ UsbSpeaker device found"
    aplay -L | grep -A1 "UsbSpeaker"
else
    echo "   ✗ UsbSpeaker not found - run setup_udev_audio.sh"
fi
echo ""

if arecord -L 2>/dev/null | grep -q "UsbMic"; then
    echo "   ✓ UsbMic device found"
    arecord -L | grep -A1 "UsbMic"
else
    echo "   ✗ UsbMic not found - run setup_udev_audio.sh"
fi
echo ""

# Check udev rules
echo "6. Checking udev rules..."
if [ -f /etc/udev/rules.d/99-usb-audio.rules ]; then
    echo "   ✓ /etc/udev/rules.d/99-usb-audio.rules exists:"
    cat /etc/udev/rules.d/99-usb-audio.rules | head -10
else
    echo "   ✗ No udev rules file found"
fi
echo ""

# Check PulseAudio / PipeWire status
echo "7. Audio daemon status:"
if command -v pulseaudio &> /dev/null; then
    if pulseaudio --check 2>/dev/null; then
        echo "   PulseAudio: Running"
    else
        echo "   PulseAudio: Not running"
    fi
fi
if command -v pipewire &> /dev/null; then
    if systemctl --user is-active pipewire &>/dev/null; then
        echo "   PipeWire: Running"
    else
        echo "   PipeWire: Not running (or not as user service)"
    fi
fi
echo ""

# Test speaker output
echo "8. Testing speaker output..."
echo "   Playing test tone for 2 seconds..."
SPEAKER_DEV=""
if aplay -L 2>/dev/null | grep -q "plughw:CARD=UsbSpeaker"; then
    SPEAKER_DEV="plughw:CARD=UsbSpeaker,DEV=0"
else
    # Try to find any USB speaker
    SPEAKER_CARD=$(aplay -l 2>/dev/null | grep -i usb | head -1 | sed -n 's/card \([0-9]*\).*/\1/p')
    if [ -n "$SPEAKER_CARD" ]; then
        SPEAKER_DEV="plughw:$SPEAKER_CARD,0"
    fi
fi

if [ -n "$SPEAKER_DEV" ]; then
    echo "   Using device: $SPEAKER_DEV"
    # Generate a test tone using speaker-test or sox
    if command -v speaker-test &> /dev/null; then
        timeout 2 speaker-test -D "$SPEAKER_DEV" -t sine -f 440 -l 1 2>/dev/null && echo "   ✓ Speaker test completed" || echo "   ✗ Speaker test failed"
    else
        echo "   speaker-test not available, trying aplay..."
        # Generate tone with sox if available
        if command -v sox &> /dev/null; then
            sox -n -r 44100 -c 1 -t wav - synth 2 sine 440 2>/dev/null | aplay -D "$SPEAKER_DEV" 2>/dev/null && echo "   ✓ Speaker test completed" || echo "   ✗ Speaker test failed"
        else
            echo "   ✗ Neither speaker-test nor sox available"
        fi
    fi
else
    echo "   ✗ No USB speaker device found"
fi
echo ""

# Test microphone input
echo "9. Testing microphone input (5 seconds)..."
MIC_DEV=""
if arecord -L 2>/dev/null | grep -q "plughw:CARD=UsbMic"; then
    MIC_DEV="plughw:CARD=UsbMic,DEV=0"
else
    # Try to find any USB mic
    MIC_CARD=$(arecord -l 2>/dev/null | grep -i usb | head -1 | sed -n 's/card \([0-9]*\).*/\1/p')
    if [ -n "$MIC_CARD" ]; then
        MIC_DEV="plughw:$MIC_CARD,0"
    fi
fi

if [ -n "$MIC_DEV" ]; then
    echo "   Using device: $MIC_DEV"
    echo "   Recording 3 seconds of audio..."
    TEST_FILE="/tmp/mic_test_$$.wav"
    timeout 4 arecord -D "$MIC_DEV" -f S16_LE -r 44100 -c 1 -d 3 "$TEST_FILE" 2>/dev/null
    if [ -f "$TEST_FILE" ]; then
        SIZE=$(stat -c%s "$TEST_FILE" 2>/dev/null || stat -f%z "$TEST_FILE" 2>/dev/null)
        echo "   ✓ Recorded file: $TEST_FILE ($SIZE bytes)"

        # Check audio levels
        if command -v sox &> /dev/null; then
            echo "   Audio stats:"
            sox "$TEST_FILE" -n stat 2>&1 | grep -E "(Maximum|RMS|Mean)" | head -5
        fi

        echo ""
        echo "   To play back the recording, run:"
        echo "   aplay -D $SPEAKER_DEV $TEST_FILE"
    else
        echo "   ✗ Recording failed"
    fi
else
    echo "   ✗ No USB microphone device found"
fi
echo ""

# Python audio test
echo "10. Testing Python audio (PyAudio)..."
cd "$(dirname "$0")/.." 2>/dev/null || true
if [ -f "venv/bin/python" ]; then
    ./venv/bin/python -c "
import pyaudio
pa = pyaudio.PyAudio()
print('   PyAudio initialized successfully')
print('   Input devices:')
for i in range(pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f\"     [{i}] {info['name']} ({info['maxInputChannels']}ch, {int(info['defaultSampleRate'])}Hz)\")
print('   Output devices:')
for i in range(pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    if info['maxOutputChannels'] > 0:
        print(f\"     [{i}] {info['name']} ({info['maxOutputChannels']}ch, {int(info['defaultSampleRate'])}Hz)\")
pa.terminate()
" 2>&1 || echo "   ✗ PyAudio test failed"
else
    echo "   ✗ Virtual environment not found at venv/"
fi
echo ""

echo "========================================"
echo "   Diagnostics Complete"
echo "========================================"
echo ""
echo "Common fixes:"
echo "  - If USB devices not found: check physical connections, try different USB ports"
echo "  - If not in audio group: sudo usermod -aG audio $USER && logout/login"
echo "  - If no persistent names: sudo ./scripts/setup_udev_audio.sh"
echo "  - If mic too quiet: check alsamixer levels (run: alsamixer)"
echo ""
