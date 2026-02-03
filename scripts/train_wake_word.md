# Training Custom "Hey Claude" Wake Word

## Quick Method (Google Colab - Recommended)

1. **Open the OpenWakeWord Training Notebook**:
   - Visit: https://github.com/dscripka/openWakeWord
   - Look for the Google Colab training notebook link in the README

2. **Train Your Model**:
   - Enter "hey claude" as your wake word
   - Run all cells to generate synthetic training data
   - Wait ~30-60 minutes for training to complete
   - Download the `.onnx` file

3. **Install the Model**:
   ```bash
   # Create models directory
   mkdir -p models/wake_word
   
   # Move your downloaded model
   mv ~/Downloads/hey_claude.onnx models/wake_word/
   ```

4. **Update Configuration**:
   Edit `config/config.yaml`:
   ```yaml
   system:
     wake_word_model_path: "models/wake_word/hey_claude.onnx"
   ```

## Alternative: Use Pre-trained "Hey Jarvis"

OpenWakeWord includes "hey_jarvis" which is phonetically similar to "hey claude":

Edit `src/perception/wakeword.py` line 26:
```python
self.model_names = ["hey_jarvis"]  # Temporary until custom model ready
```

## Testing

After installing your custom model, test with:
```bash
source venv/bin/activate
python3 src/core/main.py
```

Say "Hey Claude" and watch for the wake word detection log.
