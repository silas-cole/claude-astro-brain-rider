
import os
import sys
import yaml
import logging
import signal
import time
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Rich Imports
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align
from rich.text import Text

# Load env vars
load_dotenv()

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

# Local Imports
from core.orchestrator import Orchestrator, State
from utils.config_validation import validate_config

# Setup logging - Log to console for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Main")

def load_config(config_path: str):
    with open(config_path, "r") as f:
        config_dict = yaml.safe_load(f)
    # Validate Config
    try:
        validated_config = validate_config(config_dict)
        # Return dict as Orchestrator expects dict, but validation ensures correctness
        return config_dict 
    except Exception as e:
        print(f"Configuration Error: {e}")
        sys.exit(1)

def signal_handler(sig, frame):
    logger.info("Shutdown signal received")
    # We rely on the keyboard interrupt in the main loop to exit cleanly
    sys.exit(0)

def make_layout():
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3),
    )
    layout["main"].split_row(
        Layout(name="status", ratio=1),
        Layout(name="interaction", ratio=2),
    )
    return layout

def generate_ui(orchestrator, tick_count):
    layout = make_layout()
    
    # Header
    layout["header"].update(Panel(Align.center(Text("Claude Astro Brain Rider", style="bold magenta")), style="blue"))
    
    # Status
    # Determine color based on state
    if orchestrator.state == State.LISTENING:
        state_color = "green"
        icon = "👂"
    elif orchestrator.state == State.PROCESSING_AUDIO:
        state_color = "yellow"
        icon = "🔊"
    elif orchestrator.state == State.THINKING:
        state_color = "cyan"
        icon = "🧠"
    elif orchestrator.state == State.SPEAKING:
        state_color = "magenta"
        icon = "🗣️"
    else:
        state_color = "red"
        icon = "❓"

    status_content = Align.center(
        Text(f"\n{icon}\n\n{orchestrator.state.name}", style=f"bold {state_color}", justify="center"),
        vertical="middle"
    )
    
    layout["status"].update(Panel(
        status_content,
        title="Current State",
        border_style=state_color
    ))
    
    # Interaction
    interact_text = Text()
    interact_text.append("User Input:\n", style="bold white underline")
    interact_text.append(f"{orchestrator.latest_user_text}\n\n", style="white")
    interact_text.append("System Response:\n", style="bold cyan underline")
    interact_text.append(f"{orchestrator.latest_system_text}", style="cyan")
    
    if orchestrator.last_interaction_time > 0:
        ago = int(time.time() - orchestrator.last_interaction_time)
        interact_text.append(f"\n\n(Last interaction {ago}s ago)", style="dim italic")

    layout["interaction"].update(Panel(interact_text, title="Live Transcript", border_style="white"))
    
    # Footer
    layout["footer"].update(Panel(f"Ticks: {tick_count} | {datetime.now().strftime('%H:%M:%S')} | Log: brain_rider.log", style="dim"))
    
    return layout

def main():
    print("Starting Claude Brain Rider...")
    
    # Load Config
    config_path = os.path.join(os.path.dirname(__file__), "../../config/config.yaml")
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"Failed to load config: {e}")
        return

    # Initialize Orchestrator
    # We wrap hardware init in try/catch in case running on non-Pi for dev
    try:
        orchestrator = Orchestrator(config)
    except Exception as e:
        logger.error(f"Failed to init Orchestrator: {e}")
        print(f"Failed to init Orchestrator (Hardware missing?): {e}")
        return
    
    try:
        orchestrator.start()
    except Exception as e:
        print(f"Orchestrator start failed: {e}")
        return
    
    # Main Loop with Rich Live
    console = Console()
    tick_count = 0
    
    try:
        with Live(console=console, screen=True, refresh_per_second=10) as live:
            while True:
                tick_count += 1
                orchestrator.tick()
                
                # Update UI
                live.update(generate_ui(orchestrator, tick_count))
                
                # Sleep briefly to yield CPU
                time.sleep(0.05)
                
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        orchestrator.stop()
        print("Stopped.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main()
