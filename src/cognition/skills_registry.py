
import logging
import datetime
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SkillRegistry:
    def __init__(self, config: dict):
        self.config = config
        self.weather_location = "Knoxville TN 37917"

    def get_current_time(self) -> str:
        """Returns the current time with some hillbilly flair."""
        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p")
        
        # Hillbilly Logic
        hour = now.hour
        flavor = ""
        if 5 <= hour < 10:
            flavor = "Time to get the roosters up."
        elif 10 <= hour < 12:
            flavor = "Sun's gettin' high."
        elif 12 <= hour < 14:
            flavor = "High noon, time for vittles."
        elif 14 <= hour < 17:
            flavor = "Prime nappin' time."
        elif 17 <= hour < 20:
            flavor = "Sun's goin' down."
        else:
            flavor = "Time to hunker down."

        return f"It's about {time_str}. {flavor}"

    def get_weather(self, location: str = "") -> str:
        """Gets weather from wttr.in"""
        target_loc = location if location else self.weather_location
        try:
            # format=%C+%t -> Condition + Temp (e.g. "Sunny +75°F")
            # But the user asked for full context, so let's get a bit more text.
            # Custom format: Location: Condition Temp Humidity Wind
            # %l = location, %C = condition, %t = temp, %h = humidity, %w = wind
            url = f"https://wttr.in/{target_loc}?format=%l:+%C+%t+Humidity:%h+Wind:%w"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return f"Weather report for {target_loc}: {response.text.strip()}"
            else:
                return "My weather knee is actin' up, can't tell right now."
        except Exception as e:
            logger.error(f"Weather fetch failed: {e}")
            return "Can't see past the barn door right now."

