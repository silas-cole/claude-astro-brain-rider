
import openwakeword
from openwakeword.model import Model
import numpy as np
import logging
import os

logger = logging.getLogger(__name__)

class WakeWordDetector:
    def __init__(self, config: dict):
        self.config = config

        logger.info("Initializing OpenWakeWord...")
        
        # Check if using custom model or built-in openwakeword model
        custom_path = config.get('system', {}).get('wake_word_model_path')
        wake_word = config.get('system', {}).get('wake_word', 'hey_jarvis')
        
        if custom_path and os.path.exists(custom_path):
            # Use custom model from file
            self.model_paths = [custom_path]
            logger.info(f"Using custom wake word model: {custom_path}")
            self.owwModel = Model(
                wakeword_models=self.model_paths,
                inference_framework="onnx"
            )
        else:
            # Use built-in openwakeword model (e.g., hey_jarvis, alexa, hey_mycroft)
            logger.info(f"Using built-in wake word: {wake_word}")
            self.owwModel = Model(
                wakeword_models=[wake_word],
                inference_framework="onnx"
            )
        
        logger.info(f"Loaded model keys: {list(self.owwModel.models.keys())}")
        
    _log_counter = 0

    def detect(self, audio_chunk_bytes) -> bool:
        """
        Feeds audio chunk to model and returns True if wake word detected.
        Audio chunk should be 16-bit PCM (bytes).
        """
        # Convert bytes to numpy array (int16)
        audio_int16 = np.frombuffer(audio_chunk_bytes, dtype=np.int16)

        # Log audio stats periodically (every 50 chunks ~= every second at 16kHz)
        WakeWordDetector._log_counter += 1
        if WakeWordDetector._log_counter % 50 == 0:
            max_amp = np.max(np.abs(audio_int16)) if len(audio_int16) > 0 else 0
            rms = np.sqrt(np.mean(audio_int16.astype(np.float32)**2)) if len(audio_int16) > 0 else 0
            logger.info(f"Audio stats: samples={len(audio_int16)}, max_amp={max_amp}, rms={rms:.1f}")

        # Feed to model
        # openwakeword expects 1280 samples typically, but handles buffering internally
        prediction = self.owwModel.predict(audio_int16)

        # Get threshold from config
        threshold = self.config.get('system', {}).get('wake_word_threshold', 0.5)

        # Log prediction dict periodically for debugging
        if WakeWordDetector._log_counter % 100 == 0:
            logger.info(f"Prediction keys: {list(prediction.keys())}, values: {list(prediction.values())} (threshold={threshold})")

        # Check predictions directly
        for key, score in prediction.items():
            # Log notable scores (above 0.01 = 1%)
            if score > 0.01:
                logger.info(f"Wake word elevated score: {key} = {score:.4f}")
            elif score > 0.001:
                logger.debug(f"Wake word score: {key} = {score:.4f}")
            
            # Check against threshold
            if score > threshold:
                logger.info(f"Wake word DETECTED: {key} (Score: {score:.4f} > {threshold})")
                return True

        return False

    def reset(self):
        """
        Reset the wake word detector's internal state.
        Call this after TTS to clear any buffered audio that might cause false triggers.
        """
        self.owwModel.reset()
