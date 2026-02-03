import logging
import subprocess
import os
import tempfile

logger = logging.getLogger(__name__)


class TTSService:
    def __init__(self, config: dict):
        self.config = config
        tts_config = config.get('tts', {})
        self.en_voice = tts_config.get('english_voice', 'en_US-lessac-medium')
        self.cn_voice = tts_config.get('mandarin_voice', 'zh_CN-huayan-medium')
        self.model_dir = "models/piper"

        # ALSA output device (configurable for different USB audio setups)
        audio_config = config.get('audio', {})
        self.alsa_device = audio_config.get('alsa_output_device', 'plughw:3,0')

        # Set USB speaker to maximum hardware volume
        self._set_speaker_volume()

        # Verify piper is available
        self.mock_mode = False
        try:
            # Set LD_LIBRARY_PATH for Piper's shared libraries
            env = os.environ.copy()
            env['LD_LIBRARY_PATH'] = '/opt/piper/lib:' + env.get('LD_LIBRARY_PATH', '')
            self.piper_env = env
            
            result = subprocess.run(["piper", "--help"], capture_output=True, timeout=5, env=env)
            if result.returncode == 0:
                self.piper_path = "piper"
                logger.info("Piper TTS found and ready")
            else:
                self.piper_path = "piper" # Assume it's in path anyway? No.
                # If return code is non-zero, maybe it's not installed or config error.
                # But here we want to fallback to mock if completely missing.
                raise FileNotFoundError("Piper returned non-zero exit code")
                
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            logger.warning("Piper TTS not found. Using MOCK TTS mode.")
            self.mock_mode = True


    def _set_speaker_volume(self):
        """Set USB speaker to maximum hardware volume."""
        try:
            # Set USB speaker PCM to 85% (125/147) - use card name for persistence
            result = subprocess.run(
                ["amixer", "-c", "UsbSpeaker", "sset", "PCM", "85%"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info("USB speaker volume set to 85%")
            else:
                logger.warning(f"Could not set speaker volume: {result.stderr}")
        except Exception as e:
            logger.warning(f"Failed to set speaker volume: {e}")

    def _get_model_path(self, language: str) -> str:
        """Get the model path for a given language."""
        model_name = self.en_voice if language == "en" else self.cn_voice
        model_path = os.path.join(self.model_dir, f"{model_name}.onnx")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Piper model not found at {model_path}")
        return model_path

    def speak(self, text: str, language: str = "en"):
        """Synthesize and play audio directly (streaming mode)."""
        logger.info(f"Speaking ({language}): {text}")
        if self.mock_mode:
            logger.info(f"MOCK TTS: {text}")
            # Simulate speech time
            import time
            time.sleep(len(text) * 0.05)
            return

        model_path = self._get_model_path(language)

        self._speak_streaming(text, model_path)

    def _speak_streaming(self, text: str, model_path: str):
        """Stream Piper output directly to aplay via sox."""
        # Piper outputs raw 16-bit PCM at 22050Hz mono
        # Sox: gentle compand to avoid clipping, norm to boost volume
        # Use shlex.quote to properly escape the device name for shell
        import shlex
        cmd = (
            f'echo {subprocess.list2cmdline([text])} | '
            f'{self.piper_path} --model {model_path} --output-raw | '
            f'sox -t raw -r 22050 -b 16 -c 1 -e signed-integer - -t wav - '
            f'gain 3 norm -1 | '
            f'aplay -D {shlex.quote(self.alsa_device)} -q -'
        )
        logger.debug(f"TTS streaming command: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=self.piper_env)
        if result.returncode != 0:
            logger.warning(f"Streaming TTS failed, falling back to tempfile: {result.stderr}")
            self._speak_with_tempfile(text, model_path)

    def _speak_with_tempfile(self, text: str, model_path: str):
        """Fallback: generate to temp file then play."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            cmd = [
                self.piper_path,
                "--model", model_path,
                "--output_file", temp_path
            ]
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, env=self.piper_env)
            process.communicate(input=text.encode('utf-8'))
            self._play_wav(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def _play_wav(self, file_path: str):
        """Play a WAV file with volume boost."""
        boosted_path = file_path.replace(".wav", "_boosted.wav")
        try:
            # Gentle gain and normalization to avoid clipping
            subprocess.run(
                ["sox", file_path, boosted_path, 
                 "gain", "3", "norm", "-1"],
                capture_output=True,
                check=True
            )
            play_path = boosted_path
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"sox boost failed, using original: {e}")
            play_path = file_path

        # Retry a few times in case of USB device conflicts
        import time
        for attempt in range(3):
            logger.debug(f"aplay command: aplay -D {self.alsa_device} {play_path}")
            result = subprocess.run(
                ["aplay", "-D", self.alsa_device, play_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                break
            logger.warning(f"aplay attempt {attempt + 1} failed: {result.stderr}")
            time.sleep(0.5)

        # Clean up boosted file
        if play_path != file_path and os.path.exists(boosted_path):
            os.unlink(boosted_path)

    def synthesize_to_buffer(self, text: str, language: str = "en") -> bytes:
        """Synthesize audio to memory buffer (WAV bytes).

        Used for parallel synthesis - synthesize in background while
        another audio is playing.
        """
        logger.info(f"Synthesizing to buffer ({language}): {text}")
        model_path = self._get_model_path(language)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            # Generate WAV file
            cmd = [
                self.piper_path,
                "--model", model_path,
                "--output_file", temp_path
            ]
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            process.communicate(input=text.encode('utf-8'))

            # Boost volume
            boosted_path = temp_path.replace(".wav", "_boosted.wav")
            try:
                subprocess.run(
                    ["sox", temp_path, boosted_path, "gain", "6"],
                    capture_output=True,
                    check=True
                )
                read_path = boosted_path
            except (subprocess.CalledProcessError, FileNotFoundError):
                read_path = temp_path

            # Read into memory
            with open(read_path, 'rb') as f:
                audio_buffer = f.read()

            # Cleanup boosted file if created
            if read_path == boosted_path and os.path.exists(boosted_path):
                os.unlink(boosted_path)

            return audio_buffer
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def play_buffer(self, audio_buffer: bytes):
        """Play audio from memory buffer."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_buffer)
            temp_path = f.name

        try:
            import time
            for attempt in range(3):
                result = subprocess.run(
                    ["aplay", "-D", self.alsa_device, temp_path],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    break
                logger.warning(f"aplay attempt {attempt + 1} failed: {result.stderr}")
                time.sleep(0.5)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
