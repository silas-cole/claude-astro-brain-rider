# Brain Rider ↔ Moltbot Voice Integration

## Overview

This document describes how to integrate the Brain Rider voice system with Moltbot, allowing voice commands spoken to the Raspberry Pi to be processed by Silas (running in Moltbot) with full context, memory, and tools.

## Architecture

### Current Flow (Direct Claude API)
```
[Mic] → [Wake Word] → [STT] → [Claude API] → [Response] → [TTS] → [Speaker]
                              (llm.py)
```

### New Flow (Via Moltbot)
```
[Mic] → [Wake Word] → [STT] → [Moltbot API] → [Silas/Claude] → [Response] → [TTS] → [Speaker]
                              (llm.py)          (full context,
                               ↓                 memory, tools)
                        POST /hooks/agent
                        localhost:18789
```

## Benefits

1. **Unified Context**: Voice and Telegram messages share the same conversation history
2. **Full Tool Access**: Can use all Moltbot tools (web search, browser, calendar, etc.)
3. **Memory Persistence**: MEMORY.md and daily logs available across voice interactions
4. **Consistent Personality**: Same Silas persona regardless of input channel

## Implementation

### Step 1: Enable Moltbot Webhooks

Add to `~/.clawdbot/moltbot.json` under the root level:

```json
{
  "hooks": {
    "enabled": true,
    "token": "brain-rider-secret-token-change-me",
    "path": "/hooks"
  }
}
```

Then restart the gateway:
```bash
moltbot gateway restart
```

### Step 2: Modify Brain Rider LLM Service

Replace the direct Claude API call with a Moltbot webhook call.

**File:** `src/cognition/llm.py`

**Changes:**

```python
import requests
import json

class LLMService:
    def __init__(self, config):
        self.config = config
        # Moltbot integration settings
        self.moltbot_enabled = config.get("moltbot", {}).get("enabled", False)
        self.moltbot_url = config.get("moltbot", {}).get("url", "http://127.0.0.1:18789")
        self.moltbot_token = config.get("moltbot", {}).get("token", "")
        self.moltbot_session = config.get("moltbot", {}).get("session_key", "voice:brain-rider")
        
    def process(self, text: str) -> list:
        """Process user input and return response actions."""
        
        if self.moltbot_enabled:
            return self._process_via_moltbot(text)
        else:
            return self._process_via_claude(text)
    
    def _process_via_moltbot(self, text: str) -> list:
        """Send to Moltbot and get response."""
        
        # Wrap the voice command with context
        message = f"[Voice Command from Brain Rider]\n{text}"
        
        payload = {
            "message": message,
            "name": "Voice",
            "sessionKey": self.moltbot_session,
            "deliver": False,  # Don't send to Telegram, we handle TTS locally
            "timeoutSeconds": 30
        }
        
        headers = {
            "Authorization": f"Bearer {self.moltbot_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{self.moltbot_url}/hooks/agent",
                json=payload,
                headers=headers,
                timeout=35
            )
            
            if response.status_code == 202:
                # Async run started - need to poll for result
                # For now, return a simple acknowledgment
                # TODO: Implement polling or use sync endpoint
                return self._format_response("Got it, partner. Working on that.")
            
            elif response.status_code == 200:
                result = response.json()
                return self._format_response(result.get("response", "No response"))
                
            else:
                logger.error(f"Moltbot returned {response.status_code}: {response.text}")
                return self._format_response("Having trouble reaching my brain, partner.")
                
        except requests.exceptions.Timeout:
            return self._format_response("That's taking too long. Try again?")
        except Exception as e:
            logger.error(f"Moltbot request failed: {e}")
            return self._format_response("Something went wrong with the connection.")
    
    def _format_response(self, text: str) -> list:
        """Format response for the orchestrator."""
        return [{
            "type": "response",
            "english_response": text,
            "astro_command": None,
            "sound_effect": None,
            "emotion": "neutral"
        }]
    
    def _process_via_claude(self, text: str) -> list:
        """Original direct Claude API implementation."""
        # ... existing code ...
```

### Step 3: Update Config

**File:** `config/config.yaml`

Add Moltbot section:

```yaml
moltbot:
  enabled: true
  url: "http://127.0.0.1:18789"
  token: "brain-rider-secret-token-change-me"  # Must match hooks.token in moltbot.json
  session_key: "voice:brain-rider"  # Consistent session for context
```

### Step 4: Handle Async Responses (Advanced)

The `/hooks/agent` endpoint returns `202 Accepted` and runs asynchronously. For synchronous voice interaction, we have two options:

**Option A: Use Main Session (Recommended)**

Instead of `/hooks/agent`, inject a system event and poll for response:

1. POST to `/hooks/wake` with the voice command
2. Poll the session for new assistant messages
3. Return the latest response for TTS

**Option B: WebSocket Connection**

Connect to the Gateway WebSocket for real-time bidirectional communication:

1. Brain rider maintains a persistent WS connection
2. Send messages via `agent.send` method
3. Receive responses via event stream

This is more complex but provides the lowest latency.

**Option C: Sync Wrapper (Simplest)**

Create a small HTTP wrapper that:
1. Calls `/hooks/agent`
2. Waits for completion
3. Returns the response

This could be a simple Flask/FastAPI service or a modification to the Gateway.

## Configuration Summary

### Moltbot Side (`~/.clawdbot/moltbot.json`)
```json
{
  "hooks": {
    "enabled": true,
    "token": "brain-rider-secret-token-change-me"
  }
}
```

### Brain Rider Side (`config/config.yaml`)
```yaml
moltbot:
  enabled: true
  url: "http://127.0.0.1:18789"
  token: "brain-rider-secret-token-change-me"
  session_key: "voice:brain-rider"
```

## Testing

1. **Test webhook manually:**
```bash
curl -X POST http://127.0.0.1:18789/hooks/agent \
  -H 'Authorization: Bearer brain-rider-secret-token-change-me' \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hello from voice test","name":"Voice","deliver":false}'
```

2. **Test voice flow:**
   - Say "Hey Jarvis"
   - Give a command
   - Verify response comes from Moltbot (check logs)

3. **Verify context:**
   - Send a message via Telegram
   - Ask about it via voice
   - Should have context from both channels

## Security Considerations

1. **Token Security**: Use a strong, unique token for the webhook
2. **Localhost Only**: Keep the webhook on loopback (127.0.0.1)
3. **No Sensitive Logging**: Don't log the full token in brain rider logs

## Future Enhancements

1. **Bidirectional**: Moltbot could push messages to speak via TTS
2. **Wake Word from Moltbot**: Remote "Hey Silas" trigger from Telegram
3. **Voice Notifications**: Calendar reminders, urgent emails spoken aloud
4. **Multi-Room**: Multiple Pis with different wake words, same Silas brain

## Open Questions

1. Should voice use the main session or an isolated session?
   - Main session: Full context, but voice appears in Telegram history
   - Isolated: Clean separation, but no cross-channel context

2. How to handle long-running commands?
   - Acknowledge immediately, then speak result when ready?
   - Or block until complete (may feel slow)?

3. Should we parse Astro commands from Moltbot responses?
   - Currently brain rider's LLM prompt includes Astro command formatting
   - Could move this logic to Moltbot's system prompt instead

---

*Document created: 2026-02-03*
*Author: Silas Cole*
