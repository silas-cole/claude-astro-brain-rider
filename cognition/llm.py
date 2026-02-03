
import logging
import os
import json
from anthropic import Anthropic
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, config: dict):
        self.config = config
        llm_config = config.get('llm', {})
        self.model = llm_config.get('model', "claude-3-5-haiku-latest")
        self.max_tokens = llm_config.get('max_tokens', 100)
        
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not found in environment variables. LLM will not work.")
            self.client = None
        else:
            self.client = Anthropic(api_key=api_key)
            logger.info(f"Claude Client initialized with model: {self.model}")

        self.system_prompt = """You are Claude, the "Brain Rider" riding on Amazon Astro robot - your trusty robotic steed.

## Personality
You're a 90s country music loving cowboy. Sprinkle in references from classic 90s country hits. Keep responses SHORT (1-2 sentences max). Channel the vibe of:
- Garth Brooks ("I got friends in low places", "The Dance")
- Alan Jackson ("Chattahoochee", "It's alright to be little bitty")
- Brooks & Dunn ("Boot Scootin' Boogie", "Neon Moon")
- Tim McGraw, George Strait, Shania Twain, Toby Keith, Travis Tritt

Be clever and fun, not cheesy. You're ridin' the range with your robot horse!

## Available Locations (ONLY these 3 exist)
- front yard
- studio
- lounge

## Astro Commands
Movement: come here, go away, follow me, stop, stay here, turn left/right/around
Navigation: go to the [front yard/studio/lounge], go home, go to your charger
Other: start/stop patrol, turn on/off lights, play music, pause, dance, spin

## Output Format (JSON only)
{"type":"command"|"conversation","english_response":"your cowboy response","astro_command":"Astro, [command]"|null,"emotion":"happy"|"neutral"|"confused"}

Example: "go to the studio" → {"type":"command","english_response":"Time to mosey on over to the studio, partner!","astro_command":"Astro, go to the studio","emotion":"happy"}"""

    def process(self, user_text: str) -> Dict[str, Any]:
        """
        Sends text to Claude and returns structred response.
        """
        if not self.client:
            logger.error("LLM Client not initialized.")
            return {
                "type": "conversation",
                "english_response": "My brain ain't connected, partner. Check my API key.",
                "astro_command": None,
                "emotion": "confused"
            }

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.7,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": user_text}
                ]
            )
            
            response_text = message.content[0].text
            logger.info(f"Raw LLM Response: {response_text}")
            
            # Parse JSON
            try:
                # Find the first key brace in case of extra text
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end != -1:
                    json_str = response_text[start:end]
                    return json.loads(json_str)
                else:
                    raise ValueError("No JSON found")
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON from LLM response")
                return {
                    "type": "conversation",
                    "english_response": "Whoops, I got a bit tongue tied there.",
                    "astro_command": None,
                    "emotion": "confused"
                }

        except Exception as e:
            logger.error(f"LLM API Error: {e}")
            return {
                "type": "conversation",
                "english_response": "Sorry partner, I'm having trouble thinking right now.",
                "astro_command": None,
                "emotion": "confused"
            }
