
from faster_whisper import WhisperModel
import logging
import os
import numpy as np

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self, config: dict):
        self.config = config
        stt_config = config.get('stt', {})
        self.model_size = stt_config.get('model_size', 'base.en')
        self.compute_type = stt_config.get('compute_type', 'int8')
        
        logger.info(f"Loading Whisper model: {self.model_size} ({self.compute_type})")
        # On Pi 5, int8 is good. On Mac M1/M2/M3, float16 or float32 might be better if no CUDA.
        # faster-whisper supports CoreML or CPU execution.
        
        device = "cpu" # Default to CPU
        # auto-detect device if needed, but for now stick to CPU/auto
        
        self.model = WhisperModel(
            self.model_size, 
            device=device, 
            compute_type=self.compute_type
        )
        logger.info("Whisper model loaded")

    def transcribe(self, audio_data: np.ndarray) -> str:
        """
        Transcribes audio data.
        :param audio_data: normalized float32 numpy array or something Whisper accepts.
                           Whisper expects float32 audio at 16kHz usually.
        """
        # faster-whisper accepts:
        # - A numpy array of audio samples (16kHz)
        
        segments, info = self.model.transcribe(
            audio_data,
            beam_size=3,              # Better accuracy than greedy (1), faster than full (5)
            language="en",            # Skip language detection overhead
            condition_on_previous_text=False,  # Faster, no context dependency
            vad_filter=True,          # Trim silence for shorter audio
            vad_parameters=dict(min_silence_duration_ms=300),
        )
        
        text = " ".join([segment.text for segment in segments]).strip()
        logger.info(f"Transcribed: '{text}' (prob: {info.language_probability})")
        return text
