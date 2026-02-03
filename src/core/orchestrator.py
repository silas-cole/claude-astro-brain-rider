
import logging
import threading
import time
import os
import numpy as np
from enum import Enum, auto

from perception.audio import AudioService
from perception.wakeword import WakeWordDetector
from perception.stt import STTService
from expression.tts import TTSService
from expression.sound_fx import SoundFXService
from expression.sound_fx import SoundFXService
from cognition.llm import LLMService
from cognition.skills_registry import SkillRegistry
from communication.remote_commands import RemoteCommandService
from core.patrol import PatrolManager

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
        self.sound_fx = SoundFXService(config)
        self.skill_registry = SkillRegistry(config)
        self.patrol_manager = PatrolManager()
        
        # Link patrol to registry so LLM can trigger it
        self.skill_registry.start_patrol = self.patrol_manager.start_patrol
        
        self.llm_service = LLMService(config, skill_registry=self.skill_registry)
        
        # Update LLM with available sounds
        available_sounds = self.sound_fx.get_available_sounds()
        self.llm_service.update_available_sounds(available_sounds)
        
        # Initialize Hardware
        # self.eyes = EyesHAL(config)
        # self.leds = LEDHAL(config)
        self.eyes = None
        self.leds = None

        # Remote Command Service
        self.remote_service = RemoteCommandService(config)
        self.remote_service.start(callback=self._process_remote_command)
        
        # Buffer for audio used for STT after wake word
        self.speech_buffer = []
        self.is_recording = False
        self.silence_counter = 0
        self.is_speaking = False  # Flag to prevent wake word detection during TTS
        self.tts_end_time = 0  # Timestamp when TTS finished - for cooldown
        self.TTS_COOLDOWN_SECS = 2.0  # Ignore wake words for 2s after TTS
        
        # UI State
        self.latest_user_text = ""
        self.latest_system_text = ""
        self.last_interaction_time = 0


        # Lock for thread-safe state access
        self._state_lock = threading.Lock()

    def start(self):
        logger.info("Orchestrator starting...")
        if self.eyes: self.eyes.set_expression(EyeExpression.NEUTRAL)
        if self.leds: self.leds.set_pattern(LEDPattern.IDLE_PULSE, (0, 255, 0)) # Green pulse

        # Wait for USB audio devices to be ready at startup
        time.sleep(1.0)

        # Play startup sound
        self.sound_fx.play("yeehaw", wait=True)
        time.sleep(0.5)

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
                
                # Cooldown after TTS to prevent self-triggering on residual audio
                time_since_tts = time.time() - self.tts_end_time
                if time_since_tts < self.TTS_COOLDOWN_SECS:
                    # Only log occasionally to avoid spam
                    if not hasattr(self, '_cooldown_logged') or time.time() - self._cooldown_logged > 1.0:
                        logger.debug(f"TTS cooldown active: {self.TTS_COOLDOWN_SECS - time_since_tts:.1f}s remaining")
                        self._cooldown_logged = time.time()
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

                if self.silence_counter > 30:  # ~2 seconds silence - give user time to speak
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
            if self.eyes: self.eyes.set_expression(EyeExpression.NEUTRAL)
            if self.leds: self.leds.set_pattern(LEDPattern.IDLE_PULSE, (0, 255, 0))
        elif new_state == State.PROCESSING_AUDIO:
            if self.eyes: self.eyes.set_expression(EyeExpression.LOOK_RIGHT) # Listening
            if self.leds: self.leds.set_pattern(LEDPattern.LISTENING_SOLID, (0, 0, 255))
        elif new_state == State.THINKING:
            if self.eyes: self.eyes.set_expression(EyeExpression.THINKING)
            if self.leds: self.leds.set_pattern(LEDPattern.THINKING_SPIN, (255, 0, 255))
        elif new_state == State.SPEAKING:
            if self.eyes: self.eyes.set_expression(EyeExpression.HAPPY)
            if self.leds: self.leds.set_pattern(LEDPattern.SPEAKING_WAVE, (255, 255, 0))

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

        # Patrol Tick
        patrol_cmd = self.patrol_manager.tick()
        if patrol_cmd:
            logger.info(f"Patrol Command Generated: {patrol_cmd}")
            # Execute patrol command directly (skip LLM for movement updates)
            if self.is_speaking or self.is_recording:
                # Skip if busy
                pass
            else:
                 # Send generic text to process (which will trigger TTS "Exec: ...")
                 # OR better, execute silently or with brief TTS?
                 # Let's use _process_text but maybe prefix it so we know its auto?
                 # Actually, let's just run it as a "system command"
                 
                 # Basic approach: Feed it as a command execution.
                 threading.Thread(target=self._execute_patrol_command, args=(patrol_cmd,), daemon=True).start()

    def _execute_patrol_command(self, cmd: str):
        """Executes a generated patrol command."""
        logger.info(f"Executing patrol command: {cmd}")
        # Just speak it to Astro.
        self.tts_service.speak(cmd, "en")

    def _process_remote_command(self, text: str):
        """Callback for remote commands."""
        logger.info(f"Remote command received via API: {text}")
        # Process in background thread to avoid blocking the poller
        threading.Thread(target=self._process_text, args=(text,), daemon=True).start()

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

        # Ask Claude - returns a list of responses
        response_data_list = self.llm_service.process(text)

        if not response_data_list:
             logger.warning("Empty response from LLM")
             return

        with self._state_lock:
            self.state = State.SPEAKING
            self.view_state_change(State.SPEAKING)
            self.is_speaking = True

        # Stop audio input to avoid USB conflicts with speaker
        self.audio_service.stop_stream()
        time.sleep(0.1)  # Let USB settle

        try:
            for i, response_data in enumerate(response_data_list):
                 logger.info(f"Processing response action {i+1}/{len(response_data_list)}: {response_data}")
                 
                 english_resp = response_data.get("english_response")
                 astro_cmd = response_data.get("astro_command")
                 sound_effect = response_data.get("sound_effect")
                 
                 if i == 0:
                      self.latest_system_text = english_resp if english_resp else "Exec: " + str(astro_cmd)

                 # Play sound effect if requested (blocking to avoid ALSA conflict)
                 if sound_effect:
                     logger.info(f"Playing sound effect: {sound_effect}")
                     self.sound_fx.play(sound_effect, wait=True)

                 # Play English response (blocking)
                 if english_resp:
                     self.tts_service.speak(english_resp, "en")

                 # If there's an Astro command, speak it after a brief pause
                 if astro_cmd:
                     time.sleep(0.3)  # Brief pause between cowboy response and Astro command
                     self.tts_service.speak(astro_cmd, "en")
                     
                 # Add a small delay between actions if there are multiple
                 if i < len(response_data_list) - 1:
                     time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error processing response action: {e}")
        finally:
            # Wait for audio to clear, then restart audio stream
            time.sleep(1.0)  # Increased from 0.1 to avoid ALSA device busy/hidden issues
            self.audio_service.start_stream(callback=self._audio_callback)

            # Reset wake word detector to clear any buffered audio from TTS
            self.wakeword_detector.reset()
            
            # Set cooldown timestamp to prevent self-triggering
            self.tts_end_time = time.time()

            with self._state_lock:
                self.is_speaking = False
                self.state = State.LISTENING
                self.view_state_change(State.LISTENING)
                self.silence_counter = 0
        
    def stop(self):
        self.audio_service.stop_stream()
