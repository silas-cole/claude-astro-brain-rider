#!/usr/bin/env python3
"""
Moltbot Integration: Chat
Chat with the cowboy personality via text (Claude API).
"""
import sys
import os
import json
import subprocess

def chat(message: str):
    """Chat with cowboy personality and return text response."""
    try:
        brain_rider_dir = '/home/cowboy/claude-astro-brain-rider'
        venv_python = os.path.join(brain_rider_dir, 'venv/bin/python3')

        # Escape message for safe embedding in Python script
        safe_message = message.replace('"', '\\"').replace('\n', '\\n')

        script = f"""
import sys
import json
from datetime import datetime
sys.path.insert(0, '{brain_rider_dir}')
from src.cognition.llm_client import LLMClient

llm = LLMClient()
response = llm.generate_response("{safe_message}")

result = {{
    'status': 'success',
    'user_message': "{safe_message}",
    'cowboy_response': response,
    'timestamp': datetime.now().isoformat()
}}
print(json.dumps(result, indent=2))
"""

        # Run in Brain Rider venv with proper paths
        result = subprocess.run(
            [venv_python, '-c', script],
            cwd=brain_rider_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            print(json.dumps({
                'error': 'Chat failed',
                'stderr': result.stderr,
                'user_message': message
            }, indent=2), file=sys.stderr)
            return 1

        # Output the JSON response from the script
        print(result.stdout)
        return 0

    except Exception as e:
        print(json.dumps({
            'error': str(e),
            'user_message': message
        }, indent=2), file=sys.stderr)
        return 1

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: moltbot_chat.py <message>")
        print("Example: moltbot_chat.py 'What is the weather like?'")
        sys.exit(1)

    message = ' '.join(sys.argv[1:])
    sys.exit(chat(message))
