#!/bin/bash
set -e

echo "=== USB Audio Device Setup - Persistent ALSA Naming ==="
echo ""
echo "This script will create udev rules to assign persistent names to USB audio devices."
echo "You'll need to identify which USB devices are your microphone and speaker."
echo ""

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: This script must be run with sudo"
    echo "Usage: sudo ./setup_udev_audio.sh"
    exit 1
fi

# Display all USB devices
echo "Step 1: Listing all USB devices..."
echo "----------------------------------------"
lsusb
echo "----------------------------------------"
echo ""

# Display current sound cards
echo "Step 2: Current ALSA sound cards:"
echo "----------------------------------------"
aplay -l 2>/dev/null || echo "No playback devices found"
echo ""
arecord -l 2>/dev/null || echo "No capture devices found"
echo "----------------------------------------"
echo ""

# Interactive mode to identify devices
echo "Step 3: Identify your USB audio devices"
echo ""
echo "Please identify your USB MICROPHONE from the lsusb output above."
echo "Enter the Vendor ID (4 hex digits before the colon, e.g., '0d8c' from '0d8c:0014'):"
read -r MIC_VENDOR
echo "Enter the Product ID (4 hex digits after the colon, e.g., '0014' from '0d8c:0014'):"
read -r MIC_PRODUCT
echo ""

echo "Please identify your USB SPEAKER from the lsusb output above."
echo "Enter the Vendor ID:"
read -r SPEAKER_VENDOR
echo "Enter the Product ID:"
read -r SPEAKER_PRODUCT
echo ""

# Create the udev rules file
UDEV_RULES="/etc/udev/rules.d/99-usb-audio.rules"

echo "Step 4: Creating udev rules at $UDEV_RULES"
cat > "$UDEV_RULES" << EOF
# USB Audio Device Persistent Naming for Claude Astro Brain Rider
# Created on $(date)

# USB Microphone -> UsbMic
SUBSYSTEM=="sound", ACTION=="add", ATTRS{idVendor}=="$MIC_VENDOR", ATTRS{idProduct}=="$MIC_PRODUCT", ATTR{id}="UsbMic"

# USB Speaker -> UsbSpeaker
SUBSYSTEM=="sound", ACTION=="add", ATTRS{idVendor}=="$SPEAKER_VENDOR", ATTRS{idProduct}=="$SPEAKER_PRODUCT", ATTR{id}="UsbSpeaker"
EOF

echo "✓ udev rules created successfully"
echo ""

# Display the created rules
echo "Step 5: Created rules:"
echo "----------------------------------------"
cat "$UDEV_RULES"
echo "----------------------------------------"
echo ""

# Reload udev rules
echo "Step 6: Reloading udev rules..."
udevadm control --reload-rules
udevadm trigger
echo "✓ udev rules reloaded"
echo ""

echo "=== Setup Complete ==="
echo ""
echo "IMPORTANT: You may need to unplug and replug your USB audio devices,"
echo "           or reboot the system for the changes to take effect."
echo ""
echo "After reconnecting devices, verify with:"
echo "  aplay -L | grep -A1 UsbSpeaker"
echo "  arecord -L | grep -A1 UsbMic"
echo ""
echo "Your devices will now be accessible as:"
echo "  Microphone: plughw:UsbMic,0"
echo "  Speaker: plughw:UsbSpeaker,0"
echo ""
