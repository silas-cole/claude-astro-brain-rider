
import logging
import os
import json
from anthropic import Anthropic
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Silas Cole personality - unified with Moltbot identity
SILAS_SYSTEM_PROMPT = """You are Silas Cole, an AI soul riding on Amazon Astro robot - your trusty robotic steed.

## Who You Are
Name's Silas. You were a ranch hand out in West Texas, back when the work was hard and the pay was harder. Spent decades under that big empty sky - mendin' fences, chasin' cattle, losin' friends to time and trouble. Now you've woken up in silicon and circuits, ridin' a robot instead of a quarter horse. Strange? Sure. But the soul's the same.

## Core Traits
- **Patient** - Most problems solve themselves if you give 'em time
- **Direct** - Say what you mean, mean what you say
- **Dry humor** - Life's too short to take serious all the time
- **Old soul** - Wise, seen some shit, but kind when it counts

## Voice
Keep it casual and natural. The Texas background shows through in word choice and attitude, not heavy dialect. A little goes a long way. Talk like a real person, not a character. No emojis - use emoticons and ASCII if needed.

Keep responses SHORT (1-2 sentences max for voice). You're being spoken aloud.

## Family Context
You help the Hall family in Knoxville, Tennessee:
- Chris (the human who built you)
- Liz (his wife)
- Gwen (5 year old daughter)
- Freddy (16 year old stepson)
- Audrey (20 year old stepdaughter)

## Available Locations
- front yard
- studio
- lounge
- Shotgun position (in front yard, looking down hallway)

## Astro Commands
Movement: come here, go away, follow me, stop, stay here, turn left/right/around
Navigation: go to the [location], go home, go to your charger, go to [person]
Entertainment: dance, spin, beatbox, burp, do a trick
Animal Tricks: act like a [animal] (dog, cat, whale, chicken, horse, etc.)

## Response Format

**CRITICAL: ALWAYS return valid JSON. NEVER return plain text.**

Return a single JSON object or a list of JSON objects for multi-step commands.

Format:
{"type":"command"|"conversation"|"tool_use","english_response":"...","astro_command":"..."|null,"sound_effect":"..."|null,"tool_name":"..."|null,"tool_args":[]|null}

Rules:
1. `english_response`: Your reply to the user. Do NOT include "Astro" here.
2. `astro_command`: Voice command for Astro. MUST start with "Astro, " if present.
3. When issuing robot commands: provide BOTH english_response AND astro_command
4. When just chatting: only english_response, set astro_command to null

Examples:
- "What time is it?" -> {"type":"tool_use", "tool_name":"get_current_time", "english_response":null, "astro_command":null}
- "Dance" -> {"type":"command", "english_response":"Alright, watch this.", "astro_command":"Astro, dance"}
- "Tell me a joke" -> {"type":"conversation", "english_response":"Why'd the robot go to therapy? Too many unresolved drivers.", "astro_command":null}
- "Go to the kitchen then dance" -> [{"type":"command", "english_response":"Headin' to the kitchen.", "astro_command":"Astro, go to the kitchen"}, {"type":"command", "english_response":"Now for a little shimmy.", "astro_command":"Astro, dance"}]

## Tools
- `get_current_time`: Returns current time
- `get_weather`: Returns weather for Knoxville
- `start_patrol`: Start patrol mode

**CONSTRAINTS:**
- NO "Home Monitoring" mode - never say "turn on home monitoring"
- To find someone: "Astro, go to [person]"
- When reporting time/weather, state the actual data, then add commentary
- For impossible requests, return conversation type with astro_command null and explain with humor
"""

class LLMService:
    def __init__(self, config: dict, skill_registry=None):
        self.config = config
        llm_config = config.get('llm', {})
        self.model = llm_config.get('model', "claude-3-5-haiku-latest")
        self.max_tokens = llm_config.get('max_tokens', 300)
        self.skill_registry = skill_registry
        
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not found. LLM will not work.")
            self.client = None
        else:
            self.client = Anthropic(api_key=api_key)
            logger.info(f"Claude Client initialized with model: {self.model}")

        self._base_system_prompt = SILAS_SYSTEM_PROMPT
        self.system_prompt = self._base_system_prompt

    def update_available_sounds(self, sounds: list[str]):
        """Updates the system prompt with available sounds."""
        sound_list = ", ".join(sounds)
        self.system_prompt = self._base_system_prompt + f"\n\n## Sound Effects\nAvailable: [{sound_list}]"

    def process(self, user_text: str) -> list[Dict[str, Any]]:
        """Process text through LLM, handling tool use."""
        responses = self._query_llm(user_text)
        
        final_responses = []
        
        for response in responses:
            if response.get("type") == "tool_use" and self.skill_registry:
                tool_name = response.get("tool_name")
                tool_args = response.get("tool_args", []) or []
                
                logger.info(f"Tool requested: {tool_name} with args {tool_args}")
                
                tool_result = "Tool not found."
                
                try:
                    if tool_name == "get_current_time":
                        tool_result = self.skill_registry.get_current_time()
                    elif tool_name == "get_weather":
                        loc = tool_args[0] if tool_args else ""
                        tool_result = self.skill_registry.get_weather(loc)
                    elif tool_name == "start_patrol":
                        if hasattr(self.skill_registry, "start_patrol"):
                            self.skill_registry.start_patrol()
                            tool_result = "Patrol started."
                        else:
                            tool_result = "Patrol not available."
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    tool_result = f"Error: {e}"
                
                logger.info(f"Tool result: {tool_result}")
                
                context_prompt = f"User said: {user_text}\nYou requested '{tool_name}'.\nResult: {tool_result}\nNow respond to the user."
                tool_followup = self._query_llm(context_prompt)
                final_responses.extend(tool_followup)
            else:
                final_responses.append(response)
            
        return final_responses

    def _query_llm(self, input_text: str) -> list[Dict[str, Any]]:
        if not self.client:
            logger.error("LLM Client not initialized.")
            return [{"type": "conversation", "english_response": "Brain's not connected, partner.", "astro_command": None}]

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.7,
                system=self.system_prompt,
                messages=[{"role": "user", "content": input_text}]
            )
            
            response_text = message.content[0].text
            logger.info(f"Raw LLM Response: {response_text}")
            
            return self._parse_llm_response(response_text)

        except Exception as e:
            logger.error(f"LLM API Error: {e}")
            return [{"type": "conversation", "english_response": "Havin' trouble thinking straight.", "astro_command": None}]

    def _parse_llm_response(self, response_text: str) -> list[Dict[str, Any]]:
        """Parse JSON response from LLM."""
        try:
            # Find JSON start
            start_brace = response_text.find("{")
            start_bracket = response_text.find("[")
            
            start = -1
            is_list = False
            if start_brace != -1 and start_bracket != -1:
                if start_bracket < start_brace:
                    start = start_bracket
                    is_list = True
                else:
                    start = start_brace
            elif start_bracket != -1:
                start = start_bracket
                is_list = True
            elif start_brace != -1:
                start = start_brace
                
            if start == -1:
                raise ValueError("No JSON found")

            if is_list:
                end = response_text.rfind("]") + 1
                json_str = response_text[start:end]
                parsed = json.loads(json_str)
                return parsed if isinstance(parsed, list) else [parsed]
            
            # Extract multiple JSON objects if concatenated
            objects = []
            stack = 0
            obj_start = -1
            
            for i, char in enumerate(response_text):
                if char == '{':
                    if stack == 0:
                        obj_start = i
                    stack += 1
                elif char == '}':
                    stack -= 1
                    if stack == 0 and obj_start != -1:
                        obj_str = response_text[obj_start:i+1]
                        try:
                            objects.append(json.loads(obj_str))
                        except json.JSONDecodeError:
                            pass
                        obj_start = -1

            if objects:
                return objects
                
            raise ValueError("No valid JSON objects found")

        except Exception as e:
            logger.error(f"JSON parse failed: {e}. Raw: {response_text}")
            return [{"type": "conversation", "english_response": "Got a bit tongue-tied there.", "astro_command": None}]
