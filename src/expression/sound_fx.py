import logging
import os
import subprocess
import glob
from typing import List, Dict, Optional
import random

logger = logging.getLogger(__name__)

class SoundFXService:
    def __init__(self, config: dict):
        self.config = config
        self.sound_dir = os.path.join(os.getcwd(), "assets", "sounds")
        self.audio_config = config.get('audio', {})
        self.alsa_device = self.audio_config.get('alsa_output_device', 'plughw:3,0')
        
        # Ensure directory exists
        if not os.path.exists(self.sound_dir):
            os.makedirs(self.sound_dir)
            logger.info(f"Created sound directory: {self.sound_dir}")
            
        self.sounds: Dict[str, str] = {}
        self.refresh_library()

    def refresh_library(self):
        """Scans the assets/sounds directory for supported audio files."""
        self.sounds = {}
        # Look for .wav files
        wav_files = glob.glob(os.path.join(self.sound_dir, "*.wav"))
        for f in wav_files:
            name = os.path.splitext(os.path.basename(f))[0]
            self.sounds[name] = f
            
        logger.info(f"Loaded {len(self.sounds)} sound effects: {list(self.sounds.keys())}")

    def get_available_sounds(self) -> List[str]:
        """Returns a list of available sound names."""
        return list(self.sounds.keys())

    def play(self, sound_name: str, wait: bool = False):
        """
        Play a sound effect.
        
        Args:
            sound_name: Name of the sound file (without extension).
            wait: If True, block until sound finishes playing.
        """
        if sound_name not in self.sounds:
            logger.warning(f"Sound '{sound_name}' not found in library.")
            return

        file_path = self.sounds[sound_name]
        logger.info(f"Playing sound: {sound_name}")
        
        try:
            cmd = ["aplay", "-D", self.alsa_device, file_path]
            
            if wait:
                subprocess.run(cmd, check=False)
            else:
                subprocess.Popen(cmd)
                
        except Exception as e:
            logger.error(f"Error playing sound '{sound_name}': {e}")

    def play_random(self):
        """Plays a random sound from the library."""
        if not self.sounds:
            return
        name = random.choice(list(self.sounds.keys()))
        self.play(name)
