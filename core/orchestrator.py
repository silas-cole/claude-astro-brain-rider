
import logging
import threading
import time
import numpy as np
from enum import Enum, auto

from perception.audio import AudioService
from perception.wakeword import WakeWordDetector
from perception.stt import STTService
from expression.tts import TTSService
from cognition.llm import LLMService

from hardware.eyes import EyesHAL, EyeExpression
from hardware.leds import LEDHAL, LEDPattern

logger = logging.getLogger(__name__)

class State(Enum):
    LISTENING = auto()
    PROCESSING_AUDIO = auto()
    THINKING = auto()
    SPEAKING = auto()

class Orchestrator:
    def __init__(self, config: dict):
        self.config = config
        self.state = State.LISTENING
        
        # Initialize Services
        self.audio_service = AudioService(config)
        self.wakeword_detector = WakeWordDetector(config)
        self.stt_service = STTService(config)
        self.tts_service = TTSService(config)
        self.llm_service = LLMService(config)
        
        # Initialize Hardware
        self.eyes = EyesHAL(config)
        self.leds = LEDHAL(config)
        
        # Buffer for audio used for STT after wake word
        self.speech_buffer = []
        self.is_recording = False
        self.silence_counter = 0
        self.is_speaking = False  # Flag to prevent wake word detection during TTS
        
        # UI State
        self.latest_user_text = ""
        self.latest_system_text = ""
        self.last_interaction_time = 0


        # Lock for thread-safe state access
        self._state_lock = threading.Lock()

    def start(self):
        logger.info("Orchestrator starting...")
        self.eyes.set_expression(EyeExpression.NEUTRAL)
        self.leds.set_pattern(LEDPattern.IDLE_PULSE, (0, 255, 0)) # Green pulse

        # Wait for USB audio devices to be ready at startup
        time.sleep(1.0)

        # Speak greeting first, before starting audio stream (avoids USB conflict)
        self.tts_service.speak("Howdy partner. I'm ready to ride.", "en")
        time.sleep(0.5)  # Let USB settle
        self.audio_service.start_stream(callback=self._audio_callback)

    def _audio_callback(self, audio_data: bytes):
        """
        Called by AudioService when new chunk is available.
        This runs in a separate thread, so be careful with state.
        """
        with self._state_lock:
            if self.state == State.LISTENING:
                # Skip wake word detection if we're currently speaking
                if self.is_speaking:
                    return

                # Check for wake word
                if self.wakeword_detector.detect(audio_data):
                    logger.info("Wake Word Detected!")
                    self.state = State.PROCESSING_AUDIO
                    self.is_recording = True
                    self.view_state_change(State.PROCESSING_AUDIO)
                    self.speech_buffer = []

            elif self.state == State.PROCESSING_AUDIO:
                # Accumulate Audio
                audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
                energy = np.mean(np.abs(audio_int16))
                THRESHOLD = 500

                self.speech_buffer.append(audio_int16)

                if energy < THRESHOLD:
                    self.silence_counter += 1
                else:
                    self.silence_counter = 0

                if self.silence_counter > 12:  # ~0.8 seconds silence (was 20/~1.3s)
                    logger.info("End of speech detected.")
                    self.is_recording = False
                    self.state = State.THINKING
                    self.view_state_change(State.THINKING)
                    # Process command outside the lock to avoid blocking audio
                    threading.Thread(target=self._process_command, daemon=True).start()

    def view_state_change(self, new_state: State):
        """
        Updates hardware based on state.
        """
        if new_state == State.LISTENING:
            self.eyes.set_expression(EyeExpression.NEUTRAL)
            self.leds.set_pattern(LEDPattern.IDLE_PULSE, (0, 255, 0))
        elif new_state == State.PROCESSING_AUDIO:
            self.eyes.set_expression(EyeExpression.LOOK_RIGHT) # Listening
            self.leds.set_pattern(LEDPattern.LISTENING_SOLID, (0, 0, 255))
        elif new_state == State.THINKING:
            self.eyes.set_expression(EyeExpression.THINKING)
            self.leds.set_pattern(LEDPattern.THINKING_SPIN, (255, 0, 255))
        elif new_state == State.SPEAKING:
            self.eyes.set_expression(EyeExpression.HAPPY)
            self.leds.set_pattern(LEDPattern.SPEAKING_WAVE, (255, 255, 0))

    def tick(self):
        # Poll for remote commands (file-based IPC)
        # Note: Must use absolute path in home dir because systemd PrivateTmp=true isolates /tmp
        
        # Debug heartbeat
        if not hasattr(self, 'tick_count'): self.tick_count = 0
        self.tick_count += 1
        if self.tick_count % 50 == 0:
            logger.info("Heartbeat: Orchestrator tick")

        cmd_file = "/home/cowboy/claude-astro-brain-rider/command.txt"

        if os.path.exists(cmd_file):
            try:
                with open(cmd_file, "r") as f:
                    text = f.read().strip()
                os.remove(cmd_file)
                if text:
                    logger.info(f"Remote command received: {text}")
                    # Process in background thread
                    threading.Thread(target=self._process_text, args=(text,), daemon=True).start()
            except Exception as e:
                logger.error(f"Error reading remote command: {e}")

    def _process_command(self):
        """
        Process the captured speech.
        """
        logger.info("Processing command...")

        # Copy buffer under lock, then process outside lock
        with self._state_lock:
            if not self.speech_buffer:
                self.state = State.LISTENING
                self.view_state_change(State.LISTENING)
                return
            speech_buffer_copy = list(self.speech_buffer)

        full_audio = np.concatenate(speech_buffer_copy)
        full_audio_float = full_audio.astype(np.float32) / 32768.0

        text = self.stt_service.transcribe(full_audio_float)

        if text:
            self._process_text(text)
        else:
            logger.info("No speech recognized.")
            with self._state_lock:
                self.state = State.LISTENING
                self.view_state_change(State.LISTENING)
                self.silence_counter = 0

    def _process_text(self, text: str):
        """
        Process text input (from STT or remote command) through LLM and TTS.
        """
        logger.info(f"User said: {text}")
        self.latest_user_text = text
        self.last_interaction_time = time.time()

        # Ask Claude
        response_data = self.llm_service.process(text)

        with self._state_lock:
            self.state = State.SPEAKING
            self.view_state_change(State.SPEAKING)
            self.is_speaking = True

        # Stop audio input to avoid USB conflicts with speaker
        self.audio_service.stop_stream()
        time.sleep(0.1)  # Let USB settle

        english_resp = response_data.get("english_response")
        astro_cmd = response_data.get("astro_command")
        
        self.latest_system_text = english_resp if english_resp else "Exec: " + str(astro_cmd)

        # Play English response (blocking)
        if english_resp:
            self.tts_service.speak(english_resp, "en")

        # If there's an Astro command, speak it after a brief pause
        if astro_cmd:
            time.sleep(0.3)  # Brief pause between cowboy response and Astro command
            self.tts_service.speak(astro_cmd, "en")

        # Wait for audio to clear, then restart audio stream
        time.sleep(0.1)  # Reduced from 0.3 for faster turnaround
        self.audio_service.start_stream(callback=self._audio_callback)

        # Reset wake word detector to clear any buffered audio from TTS
        self.wakeword_detector.reset()

        with self._state_lock:
            self.is_speaking = False
            self.state = State.LISTENING
            self.view_state_change(State.LISTENING)
            self.silence_counter = 0
        
    def stop(self):
        self.audio_service.stop_stream()
