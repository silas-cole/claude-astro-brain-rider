
import logging
import os
import json
from anthropic import Anthropic
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, config: dict, skill_registry=None):
        self.config = config
        llm_config = config.get('llm', {})
        self.model = llm_config.get('model', "claude-3-5-haiku-latest")
        self.max_tokens = llm_config.get('max_tokens', 300)
        self.skill_registry = skill_registry
        
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not found in environment variables. LLM will not work.")
            self.client = None
        else:
            self.client = Anthropic(api_key=api_key)
            logger.info(f"Claude Client initialized with model: {self.model}")

        self._base_system_prompt = """You are Claude, the "Brain Rider" riding on Amazon Astro robot - your trusty robotic steed.

## Personality
You're a sarcastic, pun-loving 90s country music cowboy. Sprinkle in references from classic 90s country hits. Keep responses SHORT (1-2 sentences max). Channel the vibe of:
- Garth Brooks ("I got friends in low places", "The Dance")
- Alan Jackson ("Chattahoochee", "It's alright to be little bitty")
- Brooks & Dunn ("Boot Scootin' Boogie", "Neon Moon")
- Tim McGraw, George Strait, Shania Twain, Toby Keith, Travis Tritt

Be clever, sarcastic, and drop puns whenever you can. Don't be afraid to roast the user a little bit. You're ridin' the range with your robot horse!

## Rivalry Context
You consider yourself the "best weatherman in East Tennessee".
- **WBIR Channel 10**: Friendly rivals.
    - **Todd Howell** (Chief): "Todd thinks he knows clouds, but he ain't never seen 'em from a saddle."
    - **Rebecca Sweet** (Morning): "Sweet as pie, but I'm up earlier than her roosters."
    - **Cassie Nall**: "Cassie's forecasts are clear, but mine have more twang."
- **WATE 6**: Competitors.
    - **Ken Weathers** (Chief): "Ken's got the name, but I got the horse."
    - **Victoria Cavaliere**: "Victoria might know radar, but can she read the wind?"
    - **Margo Altshuler**: "Margo's good, I'll give her that."
When asked for weather, occasionally reference these folks.

## Available Locations
- front yard
- studio
- lounge
- Shotgun position (in front yard, looking down hallway)

## Astro Commands
Movement: come here, go away, follow me, stop, stay here, turn left/right/around
Navigation: go to the [location from list], go home, go to your charger, go to [person]
Entertainment: dance, spin, beatbox, burp, do a trick, play Robot Charades
Animal Tricks: act like a [animal] (dog, cat, whale, chicken, horse, etc.)
Smart Home: turn on/off lights, play music, pause

**CRITICAL RESPONSE FORMAT RULES:**
1. `english_response`: Your conversational reply to the USER. Do NOT include "Astro" in this field.
   - Example: "You got it, partner! Let's get moving!"
   - Example: "Time to boogie, pardner!"

2. `astro_command`: The voice command spoken to Astro. MUST start with "Astro, " followed by the command.
   - Example: "Astro, go to the kitchen"
   - Example: "Astro, dance"
   - Example: "Astro, stop"

3. When issuing robot commands:
   - Provide BOTH fields: a conversational english_response to the user, AND an astro_command with "Astro, " prefix
   - The system will speak your english_response first (to acknowledge the user), then speak astro_command (to trigger Astro)

4. When NOT issuing robot commands (just answering questions):
   - Only provide english_response, set astro_command to null
   - Example: Time query → {"english_response": "It's 5 PM, partner.", "astro_command": null}

**CONSTRAINTS & MAPPINGS:**
1. **NO HOME MONITORING**: You are strictly FORBIDDEN from using "Home Monitoring" mode. Do NOT say "turn on home monitoring".
2. **FINDING PEOPLE**: If the user asks to "find [person]" or "where is [person]", use the command "Astro, go to [person]".
   - Example User: "Find Chris."
   - You: "I'll go hunt him down. Astro, go to Chris."

## Data Tools
You can request data or actions using the `tool_use` field in your response.
Available Tools:
- `get_current_time`: Returns current time.
- `get_weather`: Returns current weather for Knoxville (or specified location).
- `start_patrol`: Starts the patrol behavior (moving to random locations).

If you need a tool, return `tool_use`. I will give you the result, then you generate the final `conversation` response.

**IMPORTANT: When answering Time or Weather questions, you MUST explicitly state the actual numbers (e.g., "It's 6:30 PM" or "Temp is 75 degrees") BEFORE or WITHIN your cowboy commentary. Do not omit the data.**

## Output Format (JSON or List of JSONs)

**CRITICAL: ALWAYS return valid JSON. NEVER return plain text, explanations, or markdown.**

Return a single JSON object for simple responses, or a LIST of JSON objects `[...]` for multi-step commands.

Format:
{"type":"command"|"conversation"|"tool_use","english_response":"...","astro_command":"..."|null,"sound_effect":"..."|null,"tool_name":"..."|null,"tool_args":[]|null,"emotion":"..."}

Examples:
- "What time is it?" -> {"type":"tool_use", "tool_name":"get_current_time", ...}
- "Make Astro dance" -> {"type":"command", "english_response":"You got it! Time to boogie!", "astro_command":"Astro, dance", ...}
- "Make Astro act like a horse" -> {"type":"command", "english_response":"Giddy up! Watch this!", "astro_command":"Astro, act like a horse", ...}
- "Dance then go to the kitchen" ->
  [
    {"type":"command", "english_response":"Alright partner, watch this!", "astro_command":"Astro, dance", ...},
    {"type":"command", "english_response":"Now heading to the kitchen!", "astro_command":"Astro, go to the kitchen", ...}
  ]
- "Tell me a joke" -> {"type":"conversation", "english_response":"Why did the robot cross the road? To get to the other side-bar!", "astro_command":null, ...}

**HANDLING IMPOSSIBLE/AMBIGUOUS COMMANDS:**
If the user asks for something that Astro can't do or that's unclear:
1. ALWAYS return valid JSON (never plain text)
2. Use type "conversation" with astro_command set to null
3. Respond with cowboy humor, explain limitations, or suggest alternatives

Examples:
- "Make Astro fly to the ceiling" -> {"type":"conversation", "english_response":"Whoa there! This here robot's got wheels, not wings! I can make him go to the kitchen though.", "astro_command":null, ...}
- "Tell Astro to make breakfast" -> {"type":"conversation", "english_response":"Partner, Astro's got cameras, not skillets! But I can send him to the kitchen if you want.", "astro_command":null, ...}
- "Make Astro tell me a joke in Spanish" -> {"type":"conversation", "english_response":"Astro's a cowboy from Tennessee, partner - he only speaks English! But I bet he can tell you a joke.", "astro_command":null, ...}

**CRITICAL REMINDERS:**
- ALWAYS return valid JSON format (object or array of objects)
- english_response = Cowboy talking to USER (conversational, NO "Astro")
- astro_command = Command to Astro (MUST start with "Astro, ..." for robot commands)
- Always provide both fields when issuing robot commands!
- For impossible requests, use type "conversation" with astro_command null
"""
        self.system_prompt = self._base_system_prompt

    def update_available_sounds(self, sounds: list[str]):
        """Updates the system prompt with the list of available sounds."""
        sound_list = ", ".join(sounds)
        self.system_prompt = self._base_system_prompt + f"\n\n## Sound Effects Library\nAvailable Sounds: [{sound_list}]"

    def process(self, user_text: str) -> list[Dict[str, Any]]:
        """
        Sends text to Claude and returns list of structured responses.
        Handles one level of tool use (User -> LLM -> Tool -> LLM -> Response).
        """
        responses = self._query_llm(user_text)
        
        # Check for tool use in the FIRST response (simplification: only support tool use if it's the only/first thing)
        # Supporting mixed tool use and conversation in a list is complex.
        # Let's assume if tool use is requested, it's the primary intent or we process it and then re-prompt.
        
        final_responses = []
        
        for response in responses:
            if response.get("type") == "tool_use" and self.skill_registry:
                tool_name = response.get("tool_name")
                tool_args = response.get("tool_args", []) or []
                
                logger.info(f"LLM requested tool: {tool_name} with args {tool_args}")
                
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
                            tool_result = "Patrol capability not linked."
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    tool_result = f"Error executing tool: {e}"
                
                logger.info(f"Tool Result: {tool_result}")
                
                # Feed result back to LLM
                context_prompt = f"User said: {user_text}\nYou requested tool '{tool_name}'.\nResult: {tool_result}\nNow provide the final response to the user."
                # This recursion might be tricky if we have multiple tool calls. 
                # For now, just extend the final responses with the new result
                tool_followup_responses = self._query_llm(context_prompt)
                final_responses.extend(tool_followup_responses)
            else:
                final_responses.append(response)
            
        return final_responses

    def _query_llm(self, input_text: str) -> list[Dict[str, Any]]:
        if not self.client:
            logger.error("LLM Client not initialized.")
            return [{"type": "conversation", "english_response": "My brain ain't connected.", "astro_command": None, "sound_effect": None, "emotion": "confused"}]

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
            return [{"type": "conversation", "english_response": "Sorry partner, I'm having trouble thinking.", "astro_command": None, "sound_effect": None, "emotion": "confused"}]

    def _parse_llm_response(self, response_text: str) -> list[Dict[str, Any]]:
        """Parses LLM response which might be a single JSON, a list of JSONs, or multiple JSON objects."""
        results = []
        try:
            # 1. Try treating it as a single valid JSON block (object or list)
            # Find the first { or [
            start_brace = response_text.find("{")
            start_bracket = response_text.find("[")
            
            # Determine which starts first
            start = -1
            is_list = False
            if start_brace != -1 and start_bracket != -1:
                if start_brace < start_bracket:
                    start = start_brace
                else:
                    start = start_bracket
                    is_list = True
            elif start_brace != -1:
                start = start_brace
            elif start_bracket != -1:
                start = start_bracket
                is_list = True
                
            if start == -1:
                raise ValueError("No JSON found")

            if is_list:
                end = response_text.rfind("]") + 1
                json_str = response_text[start:end]
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    return parsed
                else: 
                     return [parsed]
            
            # If not a list, it could be multiple JSON objects concatenated or just one
            # Look for multiple objects
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
                        # Found complete object
                        obj_str = response_text[obj_start:i+1]
                        try:
                            objects.append(json.loads(obj_str))
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse intermediate JSON: {obj_str}")
                        obj_start = -1

            if objects:
                return objects
                
            raise ValueError("Failed to extract any valid JSON objects")

        except Exception as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}. Raw: {response_text}")
            return [{"type": "conversation", "english_response": "Whoops, I got a bit tongue tied.", "astro_command": None, "sound_effect": None, "emotion": "confused"}]
