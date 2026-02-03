#\!/usr/bin/env python3
import sys, os, subprocess
bd = "/home/cowboy/claude-astro-brain-rider"
vp = os.path.join(bd, "venv/bin/python3")
text, lang = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "en"
sc = f"""import sys,yaml;sys.path.insert(0,"{bd}");f=open("{bd}/config/config.yaml");c=yaml.safe_load(f);f.close();from src.expression.tts import TTSService;t=TTSService(c);t.speak("{text}",language="{lang}")"""
r = subprocess.run([vp, "-c", sc], cwd=bd, capture_output=True, text=True, timeout=30)
print("Spoke: " + text if r.returncode == 0 else "Error: " + r.stderr)
