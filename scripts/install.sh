#!/bin/bash
# Claude Astro Brain Rider - Raspberry Pi Installation Script
# Run this script on a fresh Raspberry Pi 5 with Raspberry Pi OS

set -e

echo "=== Claude Astro Brain Rider Installation ==="
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "Warning: This script is designed for Raspberry Pi. Continuing anyway..."
fi

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
USER_NAME="${SUDO_USER:-$USER}"
USER_HOME=$(eval echo "~$USER_NAME")

echo "Project directory: $PROJECT_DIR"
echo "Installing for user: $USER_NAME"
echo ""

# Check for sudo
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo ./install.sh"
    exit 1
fi

echo "=== Installing System Dependencies ==="
apt-get update
apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    portaudio19-dev \
    libsndfile1 \
    sox \
    alsa-utils \
    i2c-tools

# Install Piper TTS
echo ""
echo "=== Installing Piper TTS ==="
if ! command -v piper &> /dev/null; then
    # Download pre-built piper binary for ARM64
    PIPER_VERSION="2023.11.14-2"
    PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_linux_aarch64.tar.gz"

    echo "Downloading Piper TTS..."
    wget -q -O /tmp/piper.tar.gz "$PIPER_URL"
    tar -xzf /tmp/piper.tar.gz -C /usr/local/bin/
    chmod +x /usr/local/bin/piper
    rm /tmp/piper.tar.gz
    echo "Piper installed to /usr/local/bin/piper"
else
    echo "Piper already installed"
fi

# Enable I2C and SPI
echo ""
echo "=== Enabling I2C and SPI ==="
raspi-config nonint do_i2c 0
raspi-config nonint do_spi 0
echo "I2C and SPI enabled"

# Add user to required groups
echo ""
echo "=== Configuring User Groups ==="
usermod -aG audio,i2c,gpio,spi "$USER_NAME"
echo "User $USER_NAME added to audio, i2c, gpio, spi groups"

# Create virtual environment
echo ""
echo "=== Setting Up Python Virtual Environment ==="
cd "$PROJECT_DIR"

if [ -d "venv" ]; then
    echo "Removing existing virtual environment..."
    rm -rf venv
fi

sudo -u "$USER_NAME" python3 -m venv venv
sudo -u "$USER_NAME" ./venv/bin/pip install --upgrade pip wheel setuptools

# Install Python dependencies
echo ""
echo "=== Installing Python Dependencies ==="
sudo -u "$USER_NAME" ./venv/bin/pip install -r requirements.txt
sudo -u "$USER_NAME" ./venv/bin/pip install openwakeword --no-deps

# Create .env file if it doesn't exist
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo ""
    echo "=== Creating .env file ==="
    cat > "$PROJECT_DIR/.env" << 'EOF'
# Claude API Key (required)
ANTHROPIC_API_KEY=your_api_key_here
EOF
    chown "$USER_NAME:$USER_NAME" "$PROJECT_DIR/.env"
    chmod 600 "$PROJECT_DIR/.env"
    echo "Created .env file - please edit and add your ANTHROPIC_API_KEY"
fi

# Install systemd service
echo ""
echo "=== Installing Systemd Service ==="
cat > /etc/systemd/system/brain-rider.service << EOF
[Unit]
Description=Claude Astro Brain Rider
After=network.target sound.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONPATH=$PROJECT_DIR/src
ExecStart=$PROJECT_DIR/venv/bin/python src/core/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable brain-rider
echo "Systemd service installed and enabled"

# Configure ALSA for USB audio
# We do NOT create /etc/asound.conf anymore as it can hide input devices from PortAudio.
# Instead, we rely on PortAudio's ability to enumerate hardware directly.
echo ""
echo "=== ALSA Configuration ==="
echo "Skipping /etc/asound.conf creation to allow auto-detection of split input/output devices."

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your ANTHROPIC_API_KEY:"
echo "   nano $PROJECT_DIR/.env"
echo ""
echo "2. Reboot to apply group membership changes:"
echo "   sudo reboot"
echo ""
echo "3. After reboot, start the service:"
echo "   sudo systemctl start brain-rider"
echo ""
echo "4. Check status:"
echo "   sudo systemctl status brain-rider"
echo "   journalctl -u brain-rider -f"
echo ""
echo "5. To run manually for testing:"
echo "   cd $PROJECT_DIR"
echo "   source venv/bin/activate"
echo "   python src/core/main.py"
echo ""
