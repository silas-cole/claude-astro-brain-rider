#!/bin/bash
# User setup script for Claude Astro Brain Rider
# Creates the cowboy user and sets up permissions
# Run this script on the Raspberry Pi as your admin user (e.g., chall)

set -e

echo "=== Claude Astro Brain Rider - User Setup ==="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
  echo "❌ Please run this script as a regular user with sudo privileges, not as root"
  exit 1
fi

# Create cowboy user if it doesn't exist
if id "cowboy" &>/dev/null; then
  echo "✅ User 'cowboy' already exists"
else
  echo "👤 Creating user 'cowboy'..."
  sudo useradd -m -s /bin/bash cowboy
  echo "✅ User 'cowboy' created"
fi

# Add to required groups
echo "🔧 Adding cowboy to required groups (audio, i2c, gpio, spi)..."
sudo usermod -aG audio,i2c,gpio,spi cowboy

# Create project directory
echo "📁 Setting up project directory..."
sudo mkdir -p /home/cowboy/claude-astro-brain-rider
sudo chown -R cowboy:cowboy /home/cowboy/claude-astro-brain-rider

# Set up SSH access for deployment
echo "🔑 Setting up SSH access..."
sudo mkdir -p /home/cowboy/.ssh
sudo chmod 700 /home/cowboy/.ssh
sudo chown cowboy:cowboy /home/cowboy/.ssh


# Copy your SSH authorized_keys to cowboy user
if [ -f "$HOME/.ssh/authorized_keys" ]; then
  sudo cp "$HOME/.ssh/authorized_keys" /home/cowboy/.ssh/authorized_keys
  sudo chown cowboy:cowboy /home/cowboy/.ssh/authorized_keys
  sudo chmod 600 /home/cowboy/.ssh/authorized_keys
  echo "✅ SSH keys copied from $USER to cowboy"
else
  echo "⚠️  No SSH keys found at $HOME/.ssh/authorized_keys"
  echo "   You may need to manually set up SSH access for the cowboy user"
fi

# Allow cowboy to restart its own service without password
echo "🔐 Configuring sudo permissions for service management..."
SUDOERS_FILE="/etc/sudoers.d/cowboy-brain-rider"
sudo tee "$SUDOERS_FILE" > /dev/null << 'EOF'
# Allow cowboy user to manage brain-rider service
cowboy ALL=(ALL) NOPASSWD: /bin/systemctl start brain-rider
cowboy ALL=(ALL) NOPASSWD: /bin/systemctl stop brain-rider
cowboy ALL=(ALL) NOPASSWD: /bin/systemctl restart brain-rider
cowboy ALL=(ALL) NOPASSWD: /bin/systemctl status brain-rider
cowboy ALL=(ALL) NOPASSWD: /bin/journalctl -u brain-rider*
EOF
sudo chmod 440 "$SUDOERS_FILE"
echo "✅ Sudo permissions configured"

echo ""
echo "=== User Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Deploy the code from your Mac:"
echo "   cd ~/Code/hall-and-dan-projects/claude-astro-brain-rider"
echo "   ./scripts/deploy.sh --full"
echo ""
echo "2. SSH to Pi as cowboy and run setup:"
echo "   ssh cowboy@cowboy-claude.local"
echo "   cd ~/claude-astro-brain-rider"
echo "   ./scripts/setup_pi.sh"
echo ""
