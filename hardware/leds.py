import logging
import threading
import time
from enum import Enum
try:
    from rpi_ws281x import PixelStrip, Color
except ImportError:
    # Creating mock classes for dev environment
    class PixelStrip:
        def __init__(self, *args, **kwargs): pass
        def begin(self): pass
        def show(self): pass
        def setPixelColor(self, *args): pass
    
    def Color(r, g, b): return (r, g, b)


logger = logging.getLogger(__name__)


class LEDPattern(Enum):
    OFF = "off"
    IDLE_PULSE = "idle_pulse"
    THINKING_SPIN = "thinking_spin"
    LISTENING_SOLID = "listening_solid"
    SPEAKING_WAVE = "speaking_wave"
    ERROR_FLASH = "error_flash"


class LEDHAL:
    """Hardware abstraction layer for WS2812B LED strip (brain dome)."""

    # Animation timing
    PULSE_PERIOD = 2.0  # seconds for full pulse cycle
    SPIN_SPEED = 0.1  # seconds per LED
    WAVE_SPEED = 0.15  # seconds per wave step
    FLASH_SPEED = 0.2  # seconds per flash

    def __init__(self, config: dict):
        self.config = config
        hw_config = config.get("hardware", {})

        self.led_pin = hw_config.get("led_pin", 18)
        self.led_count = hw_config.get("led_count", 8)

        logger.info(f"Initializing LED strip (pin={self.led_pin}, count={self.led_count})")

        self.mock_mode = False
        try:
            # Create PixelStrip object
            # Args: num, pin, freq_hz, dma, invert, brightness, channel
            self.strip = PixelStrip(
                self.led_count,
                self.led_pin,
                800000,  # LED signal frequency (800kHz for WS2812)
                10,      # DMA channel
                False,   # Invert signal (for level shifters)
                255,     # Brightness (0-255)
                0        # PWM channel
            )
            self.strip.begin()
            logger.info("LED strip initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize LED strip, using mock mode: {e}")
            self.mock_mode = True
            self.strip = None

        self.current_pattern = LEDPattern.OFF
        self.current_color = (0, 0, 0)
        self._animation_thread = None
        self._stop_animation = threading.Event()

        # Clear all LEDs on startup
        self._clear()

    def _clear(self):
        """Turn off all LEDs."""
        if self.mock_mode:
            return
        for i in range(self.led_count):
            self.strip.setPixelColor(i, Color(0, 0, 0))
        self.strip.show()

    def _set_all(self, r: int, g: int, b: int):
        """Set all LEDs to the same color."""
        if self.mock_mode:
            return
        for i in range(self.led_count):
            self.strip.setPixelColor(i, Color(r, g, b))
        self.strip.show()

    def _animate_pulse(self, color: tuple):
        """Pulsing animation - brightness fades in and out."""
        r, g, b = color
        step = 0
        while not self._stop_animation.is_set():
            # Calculate brightness using sine wave (0.2 to 1.0 range)
            import math
            brightness = 0.2 + 0.8 * (math.sin(step * 0.1) + 1) / 2
            br, bg, bb = int(r * brightness), int(g * brightness), int(b * brightness)
            self._set_all(br, bg, bb)
            step += 1
            time.sleep(0.05)

    def _animate_spin(self, color: tuple):
        """Spinning animation - single lit LED rotates around."""
        r, g, b = color
        position = 0
        while not self._stop_animation.is_set():
            for i in range(self.led_count):
                if i == position:
                    self.strip.setPixelColor(i, Color(r, g, b))
                else:
                    # Dim trail
                    dist = min(abs(i - position), self.led_count - abs(i - position))
                    if dist == 1:
                        self.strip.setPixelColor(i, Color(r // 4, g // 4, b // 4))
                    else:
                        self.strip.setPixelColor(i, Color(0, 0, 0))
            self.strip.show()
            position = (position + 1) % self.led_count
            time.sleep(self.SPIN_SPEED)

    def _animate_wave(self, color: tuple):
        """Wave animation - brightness ripples through the strip."""
        r, g, b = color
        offset = 0
        while not self._stop_animation.is_set():
            import math
            for i in range(self.led_count):
                # Wave pattern based on position + offset
                brightness = 0.3 + 0.7 * (math.sin((i + offset) * 0.8) + 1) / 2
                br, bg, bb = int(r * brightness), int(g * brightness), int(b * brightness)
                self.strip.setPixelColor(i, Color(br, bg, bb))
            self.strip.show()
            offset += 1
            time.sleep(self.WAVE_SPEED)

    def _animate_flash(self, color: tuple):
        """Flashing animation - all LEDs flash on and off."""
        r, g, b = color
        on = True
        while not self._stop_animation.is_set():
            if on:
                self._set_all(r, g, b)
            else:
                self._clear()
            on = not on
            time.sleep(self.FLASH_SPEED)

    def _start_animation(self, pattern: LEDPattern, color: tuple):
        """Start the animation thread for the given pattern."""
        self._stop_current_animation()

        self._stop_animation.clear()

        animation_map = {
            LEDPattern.IDLE_PULSE: self._animate_pulse,
            LEDPattern.THINKING_SPIN: self._animate_spin,
            LEDPattern.SPEAKING_WAVE: self._animate_wave,
            LEDPattern.ERROR_FLASH: self._animate_flash,
        }

        if pattern == LEDPattern.LISTENING_SOLID:
            # Solid color - no animation needed
            r, g, b = color
            self._set_all(r, g, b)
        elif pattern == LEDPattern.OFF:
            self._clear()
        elif pattern in animation_map:
            self._animation_thread = threading.Thread(
                target=animation_map[pattern],
                args=(color,),
                daemon=True
            )
            self._animation_thread.start()

    def _stop_current_animation(self):
        """Stop any running animation."""
        if self._animation_thread and self._animation_thread.is_alive():
            self._stop_animation.set()
            self._animation_thread.join(timeout=0.5)
            self._animation_thread = None

    def set_pattern(self, pattern: LEDPattern, color: tuple = (255, 255, 255)):
        """Set the LED pattern and color.

        Args:
            pattern: The LED pattern to display
            color: RGB tuple (0-255 for each component)
        """
        if pattern != self.current_pattern or color != self.current_color:
            logger.debug(f"🧠 LEDs{' (mock)' if self.mock_mode else ''}: {pattern.name} with color {color}")
            self.current_pattern = pattern
            self.current_color = color
            if not self.mock_mode:
                self._start_animation(pattern, color)

    def cleanup(self):
        """Clean up LED strip."""
        if not self.mock_mode:
            self._stop_current_animation()
            self._clear()
