
import time
import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class PatrolManager:
    def __init__(self):
        self.is_patrolling = False
        self.start_time = 0
        self.last_move_time = 0
        self.patrol_duration = 300  # 5 minutes
        self.move_interval_min = 30
        self.locations = ["front yard", "studio", "lounge", "kitchen"] 
        # Note: "kitchen" isn't in original system prompt list but usually standard. 
        # I'll stick to the ones from llm.py for safety: 
        self.locations = ["front yard", "studio", "lounge", "Shotgun position"]

    def start_patrol(self):
        logger.info("Starting patrol...")
        self.is_patrolling = True
        self.start_time = time.time()
        self.last_move_time = 0 # Force immediate move or soon

    def stop_patrol(self):
        if self.is_patrolling:
            logger.info("Stopping patrol.")
        self.is_patrolling = False

    def tick(self) -> Optional[str]:
        """
        Called periodically. Returns an Astro command string if a move is needed.
        """
        if not self.is_patrolling:
            return None

        now = time.time()
        
        # Check duration
        if now - self.start_time > self.patrol_duration:
            logger.info("Patrol finished.")
            self.stop_patrol()
            return "Astro, go home" # End patrol by going home

        # Check move interval
        if now - self.last_move_time > self.move_interval_min:
            # Time to move
            loc = random.choice(self.locations)
            self.last_move_time = now + random.randint(0, 20) # Add some jitter
            logger.info(f"Patrol moving to {loc}")
            return f"Astro, go to the {loc}"

        return None
