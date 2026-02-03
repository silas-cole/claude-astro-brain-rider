#!/bin/bash
# Raspberry Pi Setup Script for Claude Astro Brain Rider
# Run this on the Pi as the cowboy user after initial deployment

set -e

echo "=== Claude Astro Brain Rider - Pi Setup ==="
echo ""

# Verify we're running as cowboy user
if [ "$USER" != "cowboy" ]; then
  echo "⚠️  This script should be run as the cowboy user"
  echo "   Current user: $USER"
  echo "   Please run: ssh cowboy@cowboy-claude.local"
  exit 1
fi

# Update system
echo "[1/8] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install system dependencies
echo "[2/8] Installing system dependencies..."
sudo apt install -y \
    python3-venv \
    python3-pip \
    python3-dev \
    portaudio19-dev \
    libsndfile1 \
    ffmpeg \
    git \
    alsa-utils \
    sox

# Disable PipeWire (conflicts with ALSA/PyAudio)
echo "[3/8] Disabling PipeWire to prevent audio conflicts..."
systemctl --user stop pipewire pipewire-pulse wireplumber
systemctl --user stop pipewire.socket pipewire-pulse.socket
systemctl --user disable pipewire pipewire-pulse wireplumber
systemctl --user disable pipewire.socket pipewire-pulse.socket
systemctl --user mask pipewire pipewire-pulse wireplumber
systemctl --user mask pipewire.socket pipewire-pulse.socket

# Test audio devices
echo "[3.5/8] Checking audio devices..."
echo "Recording devices:"
arecord -l
echo ""
echo "Playback devices:"
aplay -l

# Create virtual environment
echo "[4/8] Setting up Python virtual environment..."
cd ~/claude-astro-brain-rider
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "[5/8] Installing Python packages (this takes a while)..."
pip install --upgrade pip
pip install -r requirements.txt

# Download Piper voice models
echo "[6/8] Downloading Piper TTS voice models..."
./scripts/download_piper_models.sh

# Enable I2C and SPI
echo "[7/8] Enabling I2C and SPI interfaces..."
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0

# Install systemd service
echo "[8/8] Installing systemd service..."
sudo cp systemd/brain-rider.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable brain-rider
echo "✅ Systemd service installed and enabled"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "IMPORTANT: Create .env file with your API key:"
echo "   echo 'ANTHROPIC_API_KEY=your-key-here' > ~/claude-astro-brain-rider/.env"
echo ""
echo "Next steps:"
echo "1. Start the service:"
echo "   sudo systemctl start brain-rider"
echo ""
echo "2. Check status:"
echo "   sudo systemctl status brain-rider"
echo ""
echo "3. View logs:"
echo "   sudo journalctl -u brain-rider -f"
echo ""
echo "Say 'Hey Cowboy' followed by a command!"

