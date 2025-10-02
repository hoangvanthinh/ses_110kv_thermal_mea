import threading
import queue
import json
from datetime import datetime
from typing import Optional, Dict, Any

from utils.http import fetch_text, HTTPError, URLError
from utils.logging import get_logger


log = get_logger("workers.ptz_controller")


def ptz_controller_worker(
    cmd_queue: "queue.Queue[str]",
    out_queue: "queue.Queue[dict]",
    stop_event: threading.Event,
    camera_name: str,
    ptz_config: Dict[str, Any],
    poll_interval_seconds: float = 0.5,
) -> None:
    """
    PTZ Controller worker that processes PTZ commands.
    
    Args:
        cmd_queue: Queue containing PTZ commands
        out_queue: Queue for outputting results
        stop_event: Event to signal shutdown
        camera_name: Name of the camera this controller manages
        ptz_config: Configuration for PTZ operations
        poll_interval_seconds: How often to check for commands
    """
    
    def execute_ptz_preset(preset_id: int) -> bool:
        """Execute PTZ preset command."""
        try:
            # Find the preset URL for this camera
            preset_url = None
            for node in ptz_config.get("node_thermals", []):
                if f"presetID={preset_id}" in node.get("url_presetID", ""):
                    preset_url = node["url_presetID"]
                    break
            
            if not preset_url:
                log.error(f"Preset {preset_id} not found for camera {camera_name}")
                return False
            
            # Execute PTZ preset
            response = fetch_text(
                preset_url,
                timeout_seconds=5.0,
                username=ptz_config.get("username"),
                password=ptz_config.get("password"),
            )
            
            log.info(f"PTZ preset {preset_id} executed for {camera_name}")
            
            # Emit success message
            out_queue.put({
                "camera": camera_name,
                "type": "ptz_preset_result",
                "preset_id": preset_id,
                "status": "success",
                "timestamp": datetime.now().isoformat(timespec="seconds")
            }, block=False)
            
            return True
            
        except (HTTPError, URLError) as e:
            log.error(f"PTZ preset error for {camera_name}: {e}")
            out_queue.put({
                "camera": camera_name,
                "type": "ptz_preset_result", 
                "preset_id": preset_id,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(timespec="seconds")
            }, block=False)
            return False
    
    def execute_ptz_move(direction: str, speed: int = 5) -> bool:
        """Execute PTZ movement command."""
        try:
            # Build PTZ move URL based on direction
            # This is a simplified implementation - adjust based on your camera's API
            base_url = ptz_config.get("base_url", "")
            if not base_url:
                log.error(f"No base URL configured for PTZ moves on {camera_name}")
                return False
            
            # Map direction to PTZ parameters
            direction_map = {
                "up": f"action=moveUp&speed={speed}",
                "down": f"action=moveDown&speed={speed}",
                "left": f"action=moveLeft&speed={speed}",
                "right": f"action=moveRight&speed={speed}",
                "zoom_in": f"action=zoomIn&speed={speed}",
                "zoom_out": f"action=zoomOut&speed={speed}",
                "stop": "action=stop"
            }
            
            if direction not in direction_map:
                log.error(f"Invalid PTZ direction: {direction}")
                return False
            
            move_url = f"{base_url}?{direction_map[direction]}"
            
            # Execute PTZ move
            response = fetch_text(
                move_url,
                timeout_seconds=5.0,
                username=ptz_config.get("username"),
                password=ptz_config.get("password"),
            )
            
            log.info(f"PTZ move {direction} at speed {speed} executed for {camera_name}")
            
            # Emit success message
            out_queue.put({
                "camera": camera_name,
                "type": "ptz_move_result",
                "direction": direction,
                "speed": speed,
                "status": "success",
                "timestamp": datetime.now().isoformat(timespec="seconds")
            }, block=False)
            
            return True
            
        except (HTTPError, URLError) as e:
            log.error(f"PTZ move error for {camera_name}: {e}")
            out_queue.put({
                "camera": camera_name,
                "type": "ptz_move_result",
                "direction": direction,
                "speed": speed,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(timespec="seconds")
            }, block=False)
            return False
    
    # Main processing loop
    while not stop_event.wait(poll_interval_seconds):
        try:
            cmd = cmd_queue.get_nowait()
        except queue.Empty:
            continue

        try:
            cmd_data = json.loads(cmd)
            
            # Only process commands for this camera
            if cmd_data.get("camera") != camera_name:
                continue
                
            cmd_type = cmd_data.get("type")
            payload = cmd_data.get("payload", "")
            
            if cmd_type == "ptz_preset":
                # Parse preset ID from payload
                try:
                    preset_id = int(payload)
                    execute_ptz_preset(preset_id)
                except ValueError:
                    log.error(f"Invalid preset ID: {payload}")
                    
            elif cmd_type == "ptz_move":
                # Parse movement command from payload
                # Format: "direction:speed" e.g., "up:5", "left:3"
                try:
                    if ":" in payload:
                        direction, speed_str = payload.split(":", 1)
                        speed = int(speed_str)
                    else:
                        direction = payload
                        speed = 5  # Default speed
                    execute_ptz_move(direction, speed)
                except ValueError:
                    log.error(f"Invalid PTZ move command: {payload}")
                    
            elif cmd_type == "command":
                # Handle general commands
                log.debug(f"General command for {camera_name}: {payload}")
                
        except json.JSONDecodeError:
            log.error(f"Invalid JSON command: {cmd}")
        except Exception as e:
            log.error(f"Error processing PTZ command: {cmd} - {e}")


__all__ = ["ptz_controller_worker"]
