import logging
from enum import Enum
try:
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
except ImportError:
    # Mocks for dev environment
    def i2c(**kwargs): return None
    def ssd1306(serial): return MockOLED()
    
    class MockOLED:
        def display(self, img): pass
        def cleanup(self): pass

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


class EyeExpression(Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    CONFUSED = "confused"
    THINKING = "thinking"
    BLINK = "blink"
    LOOK_LEFT = "look_left"
    LOOK_RIGHT = "look_right"


class EyesHAL:
    """Hardware abstraction layer for dual SSD1306 OLED eyes."""

    # Eye drawing parameters (for 128x64 display)
    EYE_WIDTH = 128
    EYE_HEIGHT = 64
    PUPIL_RADIUS = 12
    IRIS_RADIUS = 20

    def __init__(self, config: dict):
        self.config = config
        hw_config = config.get("hardware", {})

        left_addr = hw_config.get("oled_left_addr", 0x3C)
        right_addr = hw_config.get("oled_right_addr", 0x3D)

        logger.info(f"Initializing OLED eyes (left=0x{left_addr:02X}, right=0x{right_addr:02X})")

        self.mock_mode = False
        try:
            self.left_eye = ssd1306(i2c(port=1, address=left_addr))
            self.right_eye = ssd1306(i2c(port=1, address=right_addr))
            logger.info("OLED eyes initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize OLED eyes, using mock mode: {e}")
            self.mock_mode = True
            self.left_eye = None
            self.right_eye = None

        self.current_expression = EyeExpression.NEUTRAL
        self._draw_expression(EyeExpression.NEUTRAL)

    def _create_eye_image(self, pupil_offset_x: int = 0, pupil_offset_y: int = 0,
                          lid_top: float = 0.0, lid_bottom: float = 0.0,
                          squint: float = 0.0) -> Image.Image:
        """Create an eye image with configurable pupil position and eyelids.

        Args:
            pupil_offset_x: Horizontal pupil offset (-20 to 20)
            pupil_offset_y: Vertical pupil offset (-10 to 10)
            lid_top: Top eyelid closure (0.0 = open, 1.0 = fully closed)
            lid_bottom: Bottom eyelid closure (0.0 = open, 1.0 = fully closed)
            squint: Eye squint amount (0.0 = normal, 1.0 = full squint)
        """
        img = Image.new('1', (self.EYE_WIDTH, self.EYE_HEIGHT), 0)  # Black background
        draw = ImageDraw.Draw(img)

        center_x = self.EYE_WIDTH // 2
        center_y = self.EYE_HEIGHT // 2

        # Draw eye white (ellipse)
        eye_width = 50
        eye_height = int(40 * (1 - squint * 0.5))
        draw.ellipse([
            center_x - eye_width, center_y - eye_height,
            center_x + eye_width, center_y + eye_height
        ], fill=1)

        # Draw iris (gray circle - use dithering pattern)
        iris_x = center_x + pupil_offset_x
        iris_y = center_y + pupil_offset_y
        # Draw iris outline only for contrast
        draw.ellipse([
            iris_x - self.IRIS_RADIUS, iris_y - self.IRIS_RADIUS,
            iris_x + self.IRIS_RADIUS, iris_y + self.IRIS_RADIUS
        ], outline=0, width=2)

        # Draw pupil (black circle)
        draw.ellipse([
            iris_x - self.PUPIL_RADIUS, iris_y - self.PUPIL_RADIUS,
            iris_x + self.PUPIL_RADIUS, iris_y + self.PUPIL_RADIUS
        ], fill=0)

        # Draw highlight (small white dot in pupil)
        highlight_x = iris_x - 5
        highlight_y = iris_y - 5
        draw.ellipse([
            highlight_x - 3, highlight_y - 3,
            highlight_x + 3, highlight_y + 3
        ], fill=1)

        # Draw eyelids (black rectangles covering top/bottom)
        if lid_top > 0:
            lid_height = int(self.EYE_HEIGHT * lid_top * 0.6)
            draw.rectangle([0, 0, self.EYE_WIDTH, lid_height], fill=0)
        if lid_bottom > 0:
            lid_height = int(self.EYE_HEIGHT * lid_bottom * 0.6)
            draw.rectangle([0, self.EYE_HEIGHT - lid_height, self.EYE_WIDTH, self.EYE_HEIGHT], fill=0)

        return img

    def _draw_expression(self, expression: EyeExpression):
        """Draw the given expression to both OLED displays."""
        if self.mock_mode:
            logger.debug(f"👀 EYES (mock): {expression.name}")
            return
        # Expression parameters: (pupil_x, pupil_y, lid_top, lid_bottom, squint)
        expressions = {
            EyeExpression.NEUTRAL: (0, 0, 0.0, 0.0, 0.0),
            EyeExpression.HAPPY: (0, 2, 0.3, 0.0, 0.3),
            EyeExpression.SAD: (0, 5, 0.2, 0.0, 0.0),
            EyeExpression.ANGRY: (0, -3, 0.4, 0.0, 0.2),
            EyeExpression.CONFUSED: (5, -3, 0.1, 0.0, 0.0),  # Asymmetric handled below
            EyeExpression.THINKING: (15, -5, 0.0, 0.0, 0.0),
            EyeExpression.BLINK: (0, 0, 0.9, 0.9, 0.0),
            EyeExpression.LOOK_LEFT: (-15, 0, 0.0, 0.0, 0.0),
            EyeExpression.LOOK_RIGHT: (15, 0, 0.0, 0.0, 0.0),
        }

        params = expressions.get(expression, expressions[EyeExpression.NEUTRAL])
        pupil_x, pupil_y, lid_top, lid_bottom, squint = params

        # Create eye images
        left_img = self._create_eye_image(pupil_x, pupil_y, lid_top, lid_bottom, squint)
        right_img = self._create_eye_image(pupil_x, pupil_y, lid_top, lid_bottom, squint)

        # Handle asymmetric expressions
        if expression == EyeExpression.CONFUSED:
            # One eyebrow raised (more lid on one side)
            right_img = self._create_eye_image(-5, 3, 0.3, 0.0, 0.0)

        # Display on OLEDs
        self.left_eye.display(left_img)
        self.right_eye.display(right_img)

    def set_expression(self, expression: EyeExpression):
        """Set the current eye expression."""
        if expression != self.current_expression:
            logger.debug(f"Eyes: {expression.name}")
            self.current_expression = expression
            self._draw_expression(expression)

    def update(self):
        """Called periodically to animate eyes (blinking, saccades).

        TODO: Implement random blinking and micro-saccades for more lifelike eyes.
        """
        pass

    def cleanup(self):
        """Clean up OLED displays."""
        if not self.mock_mode:
            try:
                self.left_eye.cleanup()
                self.right_eye.cleanup()
            except Exception:
                pass
