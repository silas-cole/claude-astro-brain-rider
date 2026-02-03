
import pyaudio
import numpy as np
import logging
import queue
import threading
import time
import traceback
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

        self.pa = None  # Lazy init
        self.stream = None
        self.is_running = False
        self.audio_queue = queue.Queue()
        self._thread = None
        self._callback = None
        self._restart_count = 0
        self._max_restarts = 5
        self._last_audio_time = 0
        
    def _find_usb_mic(self):
        """Find USB microphone device by name pattern."""
        if self.pa is None:
            self.pa = pyaudio.PyAudio()
            
        info = self.pa.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        
        # Look for USB mic by common name patterns
        usb_patterns = ['USB PnP Sound', 'USB Audio', 'USB Microphone']
        
        for i in range(numdevices):
            try:
                dev_info = self.pa.get_device_info_by_host_api_device_index(0, i)
                if dev_info.get('maxInputChannels', 0) > 0:
                    dev_name = dev_info.get('name', '')
                    for pattern in usb_patterns:
                        if pattern.lower() in dev_name.lower():
                            logger.info(f"Found USB mic: [{i}] {dev_name}")
                            return i
            except Exception as e:
                logger.debug(f"Error checking device {i}: {e}")
                
        return None
        
    def list_devices(self):
        info = self.pa.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        devices = []
        logger.info(f"Scanning {numdevices} devices on Host API 0 (ALSA)...")
        for i in range(0, numdevices):
            try:
                dev_info = self.pa.get_device_info_by_host_api_device_index(0, i)
                input_channels = dev_info.get('maxInputChannels')
                logger.info(f"  - Device {i}: {dev_info.get('name')} (Max Input: {input_channels})")
                if input_channels > 0:
                    devices.append(dev_info)
            except Exception as e:
                logger.warning(f"  - Device {i}: Error getting info: {e}")
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

        self._callback = callback

        # Initialize PyAudio if not already done (Lazy Init)
        if self.pa is None:
            self.pa = pyaudio.PyAudio()

        # Auto-detect USB mic if not explicitly configured
        if self.input_device is None:
            usb_mic = self._find_usb_mic()
            if usb_mic is not None:
                self.input_device = usb_mic
                logger.info(f"Auto-selected USB mic device index: {self.input_device}")

        # Log available devices
        devices = self.list_devices()
        logger.info(f"Available Input Devices: {len(devices)}")
        for dev in devices:
             logger.info(f" - [{dev['index']}] {dev['name']} (Channels: {dev['maxInputChannels']}, Rate: {dev['defaultSampleRate']})")

        # Calculate hw chunk size to get similar output chunk size after resampling
        self.hw_chunk_size = int(self.chunk_size * self.hw_sample_rate / self.target_sample_rate)

        try:
            # Try native target sample rate first (e.g., 16000)
            logger.info(f"Attempting to open audio stream at {self.target_sample_rate}Hz on device {self.input_device}")
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
        except Exception as e:
            logger.warning(f"Failed to open at {self.target_sample_rate}Hz: {e}")
            # Fallback to device's default sample rate
            try:
                if self.input_device is None:
                    try:
                        dev_info = self.pa.get_default_input_device_info()
                        self.input_device = dev_info['index']
                    except Exception:
                        logger.warning("No default input device found. Searching for available devices...")
                        devices = self.list_devices()
                        if not devices:
                            raise Exception("No input devices found on the system!")
                        # Pick the first available input device
                        dev_info = devices[0]
                        self.input_device = dev_info['index']
                        logger.info(f"Selected fallback input device: [{self.input_device}] {dev_info['name']}")
                else:
                    dev_info = self.pa.get_device_info_by_host_api_device_index(0, self.input_device)
                
                default_rate = int(dev_info.get('defaultSampleRate', 44100))
                logger.warning(f"Falling back to device default {default_rate}Hz")
                
                self.hw_sample_rate = default_rate
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
            except Exception as e:
                logger.error(f"Failed to open fallback stream: {e}")
                logger.error(traceback.format_exc())
                raise

        # Start the reader thread
        self.is_running = True
        self._last_audio_time = time.time()
        self._thread = threading.Thread(target=self._read_stream_with_recovery, daemon=True)
        self._thread.start()
        logger.info("Audio stream started")

    def _read_stream_with_recovery(self):
        """Wrapper that handles automatic recovery from stream errors."""
        while self.is_running:
            try:
                self._read_stream_loop()
            except Exception as e:
                logger.error(f"Audio stream crashed: {e}")
                logger.error(traceback.format_exc())
                
                if not self.is_running:
                    break
                    
                self._restart_count += 1
                if self._restart_count > self._max_restarts:
                    logger.error(f"Audio stream exceeded max restarts ({self._max_restarts}), giving up")
                    break
                
                logger.warning(f"Attempting audio stream recovery (attempt {self._restart_count}/{self._max_restarts})...")
                time.sleep(1.0)  # Wait before retry
                
                try:
                    self._recover_stream()
                except Exception as recover_error:
                    logger.error(f"Recovery failed: {recover_error}")
                    logger.error(traceback.format_exc())
                    time.sleep(2.0)
                    
        logger.info("Audio read thread exiting")

    def _recover_stream(self):
        """Attempt to recover the audio stream after an error."""
        # Close existing stream
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
            
        # Small delay for USB device to settle
        time.sleep(0.5)
        
        # Reopen stream
        try:
            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.hw_sample_rate,
                input=True,
                frames_per_buffer=self.hw_chunk_size,
                input_device_index=self.input_device
            )
            logger.info(f"Audio stream recovered at {self.hw_sample_rate}Hz")
        except Exception as e:
            logger.error(f"Failed to recover stream: {e}")
            raise

    def _read_stream_loop(self):
        """Main audio reading loop."""
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while self.is_running:
            try:
                data = self.stream.read(self.hw_chunk_size, exception_on_overflow=False)
                consecutive_errors = 0  # Reset on success
                self._last_audio_time = time.time()
                
                # Resample to target rate
                data = self._resample(data)
                
                if self._callback:
                    self._callback(data)
                else:
                    self.audio_queue.put(data)
                    
            except IOError as e:
                # Common during USB audio glitches
                consecutive_errors += 1
                logger.warning(f"Audio read IOError ({consecutive_errors}/{max_consecutive_errors}): {e}")
                if consecutive_errors >= max_consecutive_errors:
                    raise Exception(f"Too many consecutive audio errors: {e}")
                time.sleep(0.01)  # Brief pause before retry
                
            except Exception as e:
                logger.error(f"Unexpected error in audio loop: {e}")
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

    def is_healthy(self) -> bool:
        """Check if audio stream is healthy (receiving data)."""
        if not self.is_running or self.stream is None:
            return False
        # Consider unhealthy if no audio received in 5 seconds
        return (time.time() - self._last_audio_time) < 5.0

    def stop_stream(self):
        logger.info("Stopping audio stream...")
        self.is_running = False
        
        if self._thread:
            # Wait for thread to finish with a timeout to prevent hanging
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                logger.warning("Audio thread did not exit cleanly, proceeding to close stream anyway")
        
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error closing stream: {e}")
            finally:
                self.stream = None
                
        # Reset restart counter for next start
        self._restart_count = 0
        logger.info("Audio stream stopped")

    def __del__(self):
        self.stop_stream()
        if self.pa:
            self.pa.terminate()
