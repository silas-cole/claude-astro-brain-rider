import logging
import threading
import time
import requests
import os
from typing import Optional, Callable

logger = logging.getLogger(__name__)

class RemoteCommandService:
    def __init__(self, config: dict):
        self.config = config
        remote_config = config.get('remote', {})
        
        self.enabled = remote_config.get('enabled', False)
        self.api_endpoint = remote_config.get('api_endpoint')
        self.poll_interval = remote_config.get('poll_interval', 2.0)
        
        self.api_key = os.environ.get("REMOTE_API_KEY")
        
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.command_callback: Optional[Callable[[str], None]] = None

    def start(self, callback: Callable[[str], None]):
        """Start the polling loop."""
        if not self.enabled:
            logger.info("Remote control disabled in config.")
            return

        if not self.api_key:
            logger.warning("REMOTE_API_KEY not found. Remote control disabled.")
            return

        if not self.api_endpoint:
            logger.warning("No remote API endpoint configured.")
            return

        self.command_callback = callback
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info(f"Remote command polling started (Interval: {self.poll_interval}s)")

    def stop(self):
        """Stop the polling loop."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        logger.info("Remote command polling stopped")

    def _poll_loop(self):
        """Background loop to poll for commands."""
        headers = {
            "X-API-KEY": self.api_key,
            "User-Agent": "CowboyBrainRider/1.0"
        }
        
        # Simple session to reuse connections
        session = requests.Session()
        
        while self.running:
            try:
                # Poll endpoint
                # Expecting JSON: {"commands": [{"command": "...", "id": "...", "timestamp": "..."}]}
                # Backward compatibility: {"commands": ["old string fmt"]}
                response = session.get(
                    self.api_endpoint, 
                    headers=headers, 
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    commands = data.get("commands", [])
                    
                    if commands:
                        logger.info(f"Received {len(commands)} remote commands")
                        ack_ids = []
                        
                        for item in commands:
                            cmd_text = ""
                            cmd_id = None
                            timestamp = None

                            if isinstance(item, dict):
                                cmd_text = item.get('command')
                                # Use timestamp as ID if 'id' not present (backward compat with my first lambda draft)
                                # But my finalized lambda sends 'timestamp' and 'id' (if available).
                                # The unqique key for deletion is (status, timestamp).
                                # So we MUST send timestamp back for Ack.
                                timestamp = item.get('timestamp')
                                cmd_id = timestamp # We use timestamp as the ID for acking in the simple schema
                            elif isinstance(item, str):
                                cmd_text = item
                                # Legacy format: No Ack needed (already deleted by server)
                            
                            if cmd_text and self.command_callback:
                                try:
                                    self.command_callback(cmd_text)
                                    if cmd_id:
                                        ack_ids.append(cmd_id)
                                except Exception as e:
                                    logger.error(f"Error processing command '{cmd_text}': {e}")
                        
                        # Send batch Ack
                        if ack_ids:
                            self._send_ack(session, ack_ids)

                elif response.status_code == 204:
                    # No content / empty
                    pass
                else:
                    logger.warning(f"Poll invalid response: {response.status_code}")

            except requests.exceptions.RequestException as e:
                # Log only occasionally to avoid spamming on network drop
                logger.warning(f"Poll connection error: {e}")
            except Exception as e:
                logger.error(f"Poll unexpected error: {e}")
            
            time.sleep(self.poll_interval)

    def _send_ack(self, session, command_ids):
        """Send Acknowledgement to delete processed commands."""
        try:
            # Construct Ack URL (sibling to poll URL)
            # api_endpoint is .../commands/poll
            # ack endpoint is .../commands/ack
            base_url = self.api_endpoint.rsplit('/', 1)[0]
            if not base_url.endswith('/commands'): 
                 # Fallback if endpoint structure is different
                 base_url = self.api_endpoint.replace('/poll', '')
            
            ack_url = f"{base_url}/ack"
            
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }
            
            payload = {"command_ids": command_ids}
            
            resp = session.post(ack_url, json=payload, headers=headers, timeout=5)
            if resp.status_code == 200:
                logger.info(f"Ack successful for {len(command_ids)} commands")
            else:
                logger.warning(f"Ack failed: {resp.status_code} {resp.text}")
                
        except Exception as e:
            logger.error(f"Error sending Ack: {e}")
