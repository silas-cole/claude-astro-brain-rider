#!/bin/bash
set -e

echo "=== Piper TTS Voice Models Download ==="
echo ""

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MODELS_DIR="$PROJECT_ROOT/models/piper"

# Create models directory if it doesn't exist
mkdir -p "$MODELS_DIR"

echo "Step 1: Creating models directory at $MODELS_DIR"
echo "✓ Directory ready"
echo ""

# Base URL for Piper voices on Hugging Face
BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main"

# English voice: en_US-lessac-medium
EN_VOICE="en_US-lessac-medium"
EN_PATH="en/en_US/lessac/medium"
EN_ONNX="$MODELS_DIR/${EN_VOICE}.onnx"
EN_JSON="$MODELS_DIR/${EN_VOICE}.onnx.json"

# Mandarin voice: zh_CN-huayan-medium
ZH_VOICE="zh_CN-huayan-medium"
ZH_PATH="zh/zh_CN/huayan/medium"
ZH_ONNX="$MODELS_DIR/${ZH_VOICE}.onnx"
ZH_JSON="$MODELS_DIR/${ZH_VOICE}.onnx.json"

# Function to download file if it doesn't exist
download_if_missing() {
    local url=$1
    local dest=$2
    local name=$3
    
    if [ -f "$dest" ]; then
        echo "  ✓ $name already exists, skipping"
    else
        echo "  Downloading $name..."
        wget -q --show-progress -O "$dest" "$url"
        echo "  ✓ Downloaded $name"
    fi
}

# Download English voice model
echo "Step 2: Downloading English voice model ($EN_VOICE)"
download_if_missing "$BASE_URL/$EN_PATH/${EN_VOICE}.onnx" "$EN_ONNX" "English model"
download_if_missing "$BASE_URL/$EN_PATH/${EN_VOICE}.onnx.json" "$EN_JSON" "English config"
echo ""

# Download Mandarin voice model
echo "Step 3: Downloading Mandarin voice model ($ZH_VOICE)"
download_if_missing "$BASE_URL/$ZH_PATH/${ZH_VOICE}.onnx" "$ZH_ONNX" "Mandarin model"
download_if_missing "$BASE_URL/$ZH_PATH/${ZH_VOICE}.onnx.json" "$ZH_JSON" "Mandarin config"
echo ""

# Verify downloads
echo "Step 4: Verifying downloaded files..."
MISSING=0

for file in "$EN_ONNX" "$EN_JSON" "$ZH_ONNX" "$ZH_JSON"; do
    if [ ! -f "$file" ]; then
        echo "  ✗ Missing: $(basename "$file")"
        MISSING=$((MISSING + 1))
    else
        SIZE=$(du -h "$file" | cut -f1)
        echo "  ✓ $(basename "$file") ($SIZE)"
    fi
done

echo ""

if [ $MISSING -eq 0 ]; then
    echo "=== Download Complete ==="
    echo "All Piper voice models are ready in $MODELS_DIR"
    echo ""
    echo "Models available:"
    echo "  - English (Lessac): en_US-lessac-medium"
    echo "  - Mandarin (Huayan): zh_CN-huayan-medium"
    exit 0
else
    echo "=== Download Incomplete ==="
    echo "ERROR: $MISSING file(s) missing. Please check your internet connection and try again."
    exit 1
fi
