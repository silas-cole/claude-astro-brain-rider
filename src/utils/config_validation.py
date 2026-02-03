import os
from typing import Optional, Literal
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)

class SystemConfig(BaseModel):
    wake_word: str = Field(default="hey_jarvis")
    wake_word_model_path: Optional[str] = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")

    @validator('wake_word_model_path')
    def validate_model_path(cls, v):
        if v and not os.path.exists(v):
            raise ValueError(f"Wake word model path does not exist: {v}")
        return v
        
    @validator('wake_word')
    def validate_api_key(cls, v):
        # Check for API key in environment
        if not os.getenv("ANTHROPIC_API_KEY"):
            # Don't raise error if valid .env file exists but just not loaded yet? 
            # Actually load_dotenv() is called before this.
            # So if it's missing, we should warn or fail.
            # Let's log a warning instead of failing to allow offline testing if needed,
            # though LLMService will fail later.
            logging.getLogger(__name__).warning("ANTHROPIC_API_KEY not found in environment variables!")
        return v


class AudioConfig(BaseModel):
    input_device_index: Optional[int] = None
    output_device_index: Optional[int] = None
    sample_rate: int = Field(default=16000, ge=8000, le=48000)
    chunk_size: int = Field(default=1024, ge=256)
    alsa_output_device: str = Field(default="default")

class STTConfig(BaseModel):
    model_size: str = Field(default="tiny.en")
    compute_type: str = Field(default="int8")

class TTSConfig(BaseModel):
    english_voice: str
    mandarin_voice: str
    playback_speed: float = Field(default=1.0, gt=0.0, le=3.0)

class LLMConfig(BaseModel):
    model: str
    max_tokens: int = Field(default=150, gt=0)

class HardwareConfig(BaseModel):
    oled_left_addr: int
    oled_right_addr: int
    led_pin: int
    led_count: int = Field(gt=0)

class AppConfig(BaseModel):
    system: SystemConfig
    audio: AudioConfig
    stt: STTConfig
    tts: TTSConfig
    llm: LLMConfig
    hardware: HardwareConfig

def validate_config(config_dict: dict) -> AppConfig:
    """
    Validates the configuration dictionary using Pydantic models.
    Returns a validated AppConfig object.
    raises ValidationError if config is invalid.
    """
    try:
        config = AppConfig(**config_dict)
        logger.info("Configuration validation successful.")
        return config
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
