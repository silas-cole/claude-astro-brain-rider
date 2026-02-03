import os
import sys
import subprocess

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from expression.tts import TTSService

def create_sounds():
    """Generates default spoken sound effects using the TTS engine."""
    
    # Mock config sufficient for TTSService
    config = {
        'tts': {
            'english_voice': 'en_US-lessac-medium'  # Default
        },
        'audio': {
            'alsa_output_device': 'default'
        }
    }
    
    try:
        tts = TTSService(config)
    except Exception as e:
        print(f"Could not initialize TTS Service: {e}")
        return

    sounds = {
        "yeehaw": "Yee haw!",
        "giddyup": "Giddy up!",
        "whip": "Whip crack!",
        "whoa": "Whoa there partner.",
        "laugh": "Ha ha ha!"
    }
    
    sound_dir = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sounds')
    os.makedirs(sound_dir, exist_ok=True)
    
    print(f"Generating sounds in {sound_dir}...")
    
    for name, text in sounds.items():
        filename = os.path.join(sound_dir, f"{name}.wav")
        if os.path.exists(filename):
            print(f"  Skipping {name} (already exists)")
            continue
            
        print(f"  Generating {name}...")
        try:
            # We want to save to file, not play. TTSService mostly plays.
            # But we can access the internal helper or just call piper directly.
            # TTSService doesn't expose a clean "save to file" method that returns the path without playing,
            # except _speak_with_tempfile which deletes it, or synthesize_to_buffer.
            
            # Let's use synthesize_to_buffer and write to file.
            try:
                audio_data = tts.synthesize_to_buffer(text)
                with open(filename, 'wb') as f:
                    f.write(audio_data)
            except AttributeError:
                # If mock mode active or piper missing, try to use 'say' on Mac
                if sys.platform == 'darwin':
                    subprocess.run(["say", "-o", filename, "--data-format=LEI16@22050", text], check=True)
                else:
                    raise

                
            print(f"  Saved {name}.wav")
            
        except Exception as e:
            print(f"  Failed to generate {name}: {e}")

if __name__ == "__main__":
    create_sounds()
