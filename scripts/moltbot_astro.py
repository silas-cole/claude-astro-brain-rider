#!/usr/bin/env python3
import sys, os, subprocess, json
CMDS = {"move forward": "Astro, move forward", "move backward": "Astro, move backward", "turn left": "Astro, turn left", "turn right": "Astro, turn right", "stop": "Astro, stop", "come here": "Astro, come here", "go home": "Astro, go home", "follow me": "Astro, follow me", "stay": "Astro, stay", "patrol": "Astro, patrol", "dance": "Astro, dance", "spin around": "Astro, spin around"}
cmd = " ".join(sys.argv[1:]).lower().strip()
if cmd not in CMDS: print(json.dumps({"error": "Unknown command", "available": list(CMDS.keys())}, indent=2)); sys.exit(1)
acmd = CMDS[cmd]
bd = "/home/cowboy/claude-astro-brain-rider"
sc = f'import sys,yaml;sys.path.insert(0,"{bd}");f=open("{bd}/config/config.yaml");c=yaml.safe_load(f);f.close();from src.expression.tts import TTSService;t=TTSService(c);t.speak("{acmd}",language="en")'
r = subprocess.run([os.path.join(bd, "venv/bin/python3"), "-c", sc], cwd=bd, capture_output=True, text=True, timeout=30)
if r.returncode != 0: print(json.dumps({"error": r.stderr}, indent=2), file=sys.stderr); sys.exit(1)
print(f"Sent to Astro: {cmd} -> {acmd}")
print(json.dumps({"status": "success", "command": cmd, "astro_command": acmd}, indent=2))
