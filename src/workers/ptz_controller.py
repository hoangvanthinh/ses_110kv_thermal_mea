"""PTZ (Pan-Tilt-Zoom) controller worker."""
import threading
import queue
import json
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from utils.http import fetch_text, HTTPError, URLError
from utils.logging import get_logger


log = get_logger("workers.ptz_controller")


# PTZ direction to action parameter mapping
PTZ_DIRECTION_MAP = {
    "up": "action=moveUp",
    "down": "action=moveDown",
    "left": "action=moveLeft",
    "right": "action=moveRight",
    "zoom_in": "action=zoomIn",
    "zoom_out": "action=zoomOut",
    "stop": "action=stop",
}


def _find_preset_url(
    preset_id: int,
    preset_thermals: list,
) -> Optional[str]:
    """
    Find preset URL for given preset ID.
    
    Args:
        preset_id: Preset ID to find
        preset_thermals: List of thermal preset configurations
        
    Returns:
        Preset URL or None if not found
    """
    for node in preset_thermals:
        url_preset = node.get("url_presetID", "")
        if f"presetID={preset_id}" in url_preset:
            return url_preset
    return None


def _emit_ptz_result(
    out_queue: "queue.Queue[dict]",
    camera_name: str,
    result_type: str,
    status: str,
    **kwargs,
) -> None:
    """
    Emit PTZ operation result to output queue.
    
    Args:
        out_queue: Output queue
        camera_name: Name of camera
        result_type: Type of result ("ptz_preset_result" or "ptz_move_result")
        status: Status string ("success" or "error")
        **kwargs: Additional fields to include in result
    """
    try:
        result = {
            "camera": camera_name,
            "type": result_type,
            "status": status,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            **kwargs,
        }
        out_queue.put(result, block=False)
    except queue.Full:
        log.warning("Output queue full, dropping PTZ result for %s", camera_name)


def _execute_ptz_preset(
    preset_id: int,
    camera_name: str,
    ptz_config: Dict[str, Any],
    out_queue: "queue.Queue[dict]",
) -> bool:
    """
    Execute PTZ preset command.
    
    Args:
        preset_id: Preset ID to invoke
        camera_name: Name of camera
        ptz_config: PTZ configuration
        out_queue: Output queue for results
        
    Returns:
        True if successful, False otherwise
    """
    # Find preset URL
    preset_thermals = ptz_config.get("preset_thermals", [])
    preset_url = _find_preset_url(preset_id, preset_thermals)
    
    if not preset_url:
        log.error(f"Preset {preset_id} not found for camera {camera_name}")
        _emit_ptz_result(
            out_queue,
            camera_name,
            "ptz_preset_result",
            "error",
            preset_id=preset_id,
            error="Preset not found",
        )
        return False
    
    # Execute preset
    try:
        fetch_text(
            preset_url,
            timeout_seconds=5.0,
            username=ptz_config.get("username"),
            password=ptz_config.get("password"),
        )
        
        log.info(f"PTZ preset {preset_id} executed for {camera_name}")
        _emit_ptz_result(
            out_queue,
            camera_name,
            "ptz_preset_result",
            "success",
            preset_id=preset_id,
        )
        return True
        
    except (HTTPError, URLError) as e:
        log.error(f"PTZ preset error for {camera_name}: {e}")
        _emit_ptz_result(
            out_queue,
            camera_name,
            "ptz_preset_result",
            "error",
            preset_id=preset_id,
            error=str(e),
        )
        return False


def _execute_ptz_move(
    direction: str,
    speed: int,
    camera_name: str,
    ptz_config: Dict[str, Any],
    out_queue: "queue.Queue[dict]",
) -> bool:
    """
    Execute PTZ movement command.
    
    Args:
        direction: Movement direction
        speed: Movement speed (1-10)
        camera_name: Name of camera
        ptz_config: PTZ configuration
        out_queue: Output queue for results
        
    Returns:
        True if successful, False otherwise
    """
    # Validate direction
    if direction not in PTZ_DIRECTION_MAP:
        log.error(f"Invalid PTZ direction: {direction}")
        _emit_ptz_result(
            out_queue,
            camera_name,
            "ptz_move_result",
            "error",
            direction=direction,
            speed=speed,
            error="Invalid direction",
        )
        return False
    
    # Build PTZ move URL
    base_url = ptz_config.get("base_url", "")
    if not base_url:
        log.error(f"No base URL configured for PTZ moves on {camera_name}")
        _emit_ptz_result(
            out_queue,
            camera_name,
            "ptz_move_result",
            "error",
            direction=direction,
            speed=speed,
            error="Base URL not configured",
        )
        return False
    
    # Build full URL with action and speed
    action = PTZ_DIRECTION_MAP[direction]
    if direction != "stop":
        move_url = f"{base_url}?{action}&speed={speed}"
    else:
        move_url = f"{base_url}?{action}"
    
    # Execute PTZ move
    try:
        fetch_text(
            move_url,
            timeout_seconds=5.0,
            username=ptz_config.get("username"),
            password=ptz_config.get("password"),
        )
        
        log.info(f"PTZ move {direction} at speed {speed} executed for {camera_name}")
        _emit_ptz_result(
            out_queue,
            camera_name,
            "ptz_move_result",
            "success",
            direction=direction,
            speed=speed,
        )
        return True
        
    except (HTTPError, URLError) as e:
        log.error(f"PTZ move error for {camera_name}: {e}")
        _emit_ptz_result(
            out_queue,
            camera_name,
            "ptz_move_result",
            "error",
            direction=direction,
            speed=speed,
            error=str(e),
        )
        return False


def _parse_ptz_move_payload(payload: str) -> Tuple[str, int]:
    """
    Parse PTZ move command payload.
    
    Args:
        payload: Payload string in format "direction" or "direction:speed"
        
    Returns:
        Tuple of (direction, speed)
    """
    if ":" in payload:
        direction, speed_str = payload.split(":", 1)
        try:
            speed = int(speed_str)
        except ValueError:
            speed = 5  # Default speed
    else:
        direction = payload
        speed = 5  # Default speed
    
    return direction, speed


def _process_ptz_command(
    cmd_data: Dict[str, Any],
    camera_name: str,
    ptz_config: Dict[str, Any],
    out_queue: "queue.Queue[dict]",
) -> None:
    """
    Process PTZ command.
    
    Args:
        cmd_data: Command data dictionary
        camera_name: Name of camera
        ptz_config: PTZ configuration
        out_queue: Output queue for results
    """
    # Only process commands for this camera
    if cmd_data.get("camera") != camera_name:
        return
    
    cmd_type = cmd_data.get("type")
    payload = cmd_data.get("payload", "")
    
    if cmd_type == "ptz_preset":
        # Parse preset ID from payload
        try:
            preset_id = int(payload)
            _execute_ptz_preset(preset_id, camera_name, ptz_config, out_queue)
        except ValueError:
            log.error(f"Invalid preset ID: {payload}")
    
    elif cmd_type == "ptz_move":
        # Parse movement command from payload
        try:
            direction, speed = _parse_ptz_move_payload(payload)
            _execute_ptz_move(direction, speed, camera_name, ptz_config, out_queue)
        except Exception as e:
            log.error(f"Invalid PTZ move command: {payload} - {e}")
    
    elif cmd_type == "command":
        # Handle general commands
        log.debug(f"General command for {camera_name}: {payload}")


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
    
    Listens to command queue for PTZ preset and movement commands,
    executes them, and reports results.
    
    Args:
        cmd_queue: Queue containing PTZ commands
        out_queue: Queue for outputting results
        stop_event: Event to signal shutdown
        camera_name: Name of the camera this controller manages
        ptz_config: Configuration for PTZ operations
        poll_interval_seconds: How often to check for commands (default: 0.5)
    """
    log.info("PTZ controller started for camera: %s", camera_name)
    
    # Main processing loop
    while not stop_event.wait(poll_interval_seconds):
        try:
            cmd = cmd_queue.get_nowait()
        except queue.Empty:
            continue
        
        try:
            cmd_data = json.loads(cmd)
            _process_ptz_command(cmd_data, camera_name, ptz_config, out_queue)
        except json.JSONDecodeError:
            log.error(f"Invalid JSON command: {cmd}")
        except Exception as e:
            log.error(f"Error processing PTZ command: {cmd} - {e}")
    
    log.info("PTZ controller stopped for camera: %s", camera_name)


__all__ = ["ptz_controller_worker"]
