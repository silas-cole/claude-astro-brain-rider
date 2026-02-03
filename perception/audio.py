
import pyaudio
import numpy as np
import logging
import queue
import threading
from typing import Optional, Callable
from scipy.signal import resample_poly

logger = logging.getLogger(__name__)

class AudioService:
    def __init__(self, config: dict):
        self.config = config
        self.target_sample_rate = config.get('audio', {}).get('sample_rate', 16000)
        self.chunk_size = config.get('audio', {}).get('chunk_size', 1024)
        self.input_device = config.get('audio', {}).get('input_device_index')

        # Hardware sample rate - most USB mics support 44100
        self.hw_sample_rate = 44100

        self.pa = pyaudio.PyAudio()
        self.stream = None
        self.is_running = False
        self.audio_queue = queue.Queue()
        self._thread = None
        
    def list_devices(self):
        info = self.pa.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        devices = []
        for i in range(0, numdevices):
            if (self.pa.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                devices.append(self.pa.get_device_info_by_host_api_device_index(0, i))
        return devices

    def start_stream(self, callback: Optional[Callable] = None):
        """
        Starts the audio stream.
        :param callback: Optional function to call with audio chunks. 
                         If None, audio is put into self.audio_queue.
        """
        if self.is_running:
            logger.warning("Audio stream already running")
            return

        # Log available devices
        devices = self.list_devices()
        logger.info(f"Available Input Devices: {len(devices)}")
        for dev in devices:
             logger.info(f" - [{dev['index']}] {dev['name']} (Channels: {dev['maxInputChannels']}, Rate: {dev['defaultSampleRate']})")

        # Calculate hw chunk size to get similar output chunk size after resampling
        self.hw_chunk_size = int(self.chunk_size * self.hw_sample_rate / self.target_sample_rate)

        try:
            # Try native target sample rate first (e.g., 16000)
            logger.info(f"Attempting to open audio stream at {self.target_sample_rate}Hz")
            self.hw_sample_rate = self.target_sample_rate
            self.hw_chunk_size = self.chunk_size

            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.hw_sample_rate,
                input=True,
                frames_per_buffer=self.hw_chunk_size,
                input_device_index=self.input_device
            )
            logger.info(f"Successfully opened audio stream at {self.hw_sample_rate}Hz")
        except Exception:
            # Fallback to 44100 or 48000
            logger.warning(f"Failed to open at {self.target_sample_rate}Hz, trying 44100Hz")
            self.hw_sample_rate = 44100
            self.hw_chunk_size = int(self.chunk_size * self.hw_sample_rate / self.target_sample_rate)
            
            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.hw_sample_rate,
                input=True,
                frames_per_buffer=self.hw_chunk_size,
                input_device_index=self.input_device
            )
            logger.info(f"Opened fallback audio stream at {self.hw_sample_rate}Hz")
            self.is_running = True
            self._thread = threading.Thread(target=self._read_stream, args=(callback,), daemon=True)
            self._thread.start()
            logger.info("Audio stream started")
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            raise

    def _resample(self, audio_bytes: bytes) -> bytes:
        """Resample audio from hw_sample_rate to target_sample_rate.

        Uses resample_poly for efficient integer-ratio resampling.
        44100 -> 16000 uses ratio 160/441 (GCD optimization).
        """
        if self.hw_sample_rate == self.target_sample_rate:
            return audio_bytes

        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        # 44100 -> 16000: ratio 160/441 (faster than arbitrary resampling)
        resampled = resample_poly(audio_int16, 160, 441)
        
        # No gain boost needed - mic levels are good and excessive gain causes clipping
        # which distorts the audio and breaks wake word detection
        resampled = resampled.astype(np.int16)
        return resampled.tobytes()

    def _read_stream(self, callback):
        while self.is_running:
            try:
                data = self.stream.read(self.hw_chunk_size, exception_on_overflow=False)
                # Resample to target rate
                data = self._resample(data)
                if callback:
                    callback(data)
                else:
                    self.audio_queue.put(data)
            except Exception as e:
                logger.error(f"Error reading audio stream: {e}")
                break

    def stop_stream(self):
        self.is_running = False
        if self._thread:
            self._thread.join()
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        logger.info("Audio stream stopped")

    def __del__(self):
        self.stop_stream()
        self.pa.terminate()
