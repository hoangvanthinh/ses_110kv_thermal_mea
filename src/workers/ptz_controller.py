"""PTZ (Pan-Tilt-Zoom) controller worker."""
"""docstring:
This module contains the PTZ controller worker.
It is responsible for controlling the PTZ camera.
It listens to the command queue for PTZ preset and movement commands,
executes them, and reports results.
Sesion:  2.5.3.3.	PTZ position command rotate 
"""
import threading
import queue
import json
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from utils.http import fetch_text, HTTPError, URLError
from utils.logging import get_logger


log = get_logger("workers.ptz_controller")


# Global dictionary to track auto-stop timers for each camera
_active_timers: Dict[str, threading.Timer] = {}


# PTZ direction to action parameter mapping
PTZ_DIRECTION_MAP = {
    "home": "action=home",
    "up": "action=moveUp",
    "down": "action=moveDown",
    "left": "action=moveLeft",
    "right": "action=moveRight",
    "up-left": "action=moveUpLeft",
    "up-right": "action=moveUpRight",
    "down-left": "action=moveDownLeft",
    "down-right": "action=moveDownRight",
    "stop": "action=stop",
    "zoom_in": "action=zoomIn",
    "zoom_out": "action=zoomOut",
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
    mode_manager = None,
    timeout_seconds: float = 2.0,
) -> bool:
    """
    Execute PTZ movement command with auto-stop timeout.
    
    Args:
        direction: Movement direction
        speed: Movement speed (1-10)
        camera_name: Name of camera
        ptz_config: PTZ configuration
        out_queue: Output queue for results
        mode_manager: Optional mode manager for Auto/Manual control
        timeout_seconds: Seconds before auto-stop (default: 2.0)
        
    Returns:
        True if successful, False otherwise
    """
    # Auto-switch to MANUAL mode when receiving manual control command
    if mode_manager:
        from workers.mode_manager import CameraMode
        mode_manager.set_mode(camera_name, CameraMode.MANUAL, duration_seconds=300)  # 5 min
        log.info("[%s] Switched to MANUAL mode (auto-revert in 5 min)", camera_name)
    
    # Cancel any active timer when receiving new command (including stop)
    # This prevents previous move from auto-stopping after new command
    _cancel_active_timer(camera_name)
    
    if direction == "stop":
        log.info("[%s] Received explicit STOP command", camera_name)
    
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
    # base_url = ptz_config.get("base_url", "")
    base_url = ptz_config.get("url_ptz_base", "")
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
    log.info(f"Action: {action}")
    if direction == "right":
        move_url = f"{base_url}&action=rotate&pan=10&tilt=0"
    elif direction == "left":
        move_url = f"{base_url}&action=rotate&pan=-10&tilt=0"
    elif direction == "up":
        move_url = f"{base_url}&action=rotate&pan=0&tilt=10"
    elif direction == "down":
        move_url = f"{base_url}&action=rotate&pan=0&tilt=-10"
    elif direction == "up-left":
        move_url = f"{base_url}&action=rotate&pan=-10&tilt=10"
    elif direction == "up-right":
        move_url = f"{base_url}&action=rotate&pan=10&tilt=10"
    elif direction == "down-left":
        move_url = f"{base_url}&action=rotate&pan=-10&tilt=-10"
    elif direction == "down-right":
        move_url = f"{base_url}&action=rotate&pan=10&tilt=-10"
    elif direction == "stop":
        move_url = f"{base_url}&action=stop"
    else:
        move_url = f"{base_url}&action=stop"
    
    # Execute PTZ move
    try:
        fetch_text(
            move_url,
            timeout_seconds=5.0,
            username=ptz_config.get("username"),
            password=ptz_config.get("password"),
        )
        
        log.info(f"PTZ move {direction} at speed {speed} executed for {camera_name}")
        
        # Schedule auto-stop for movement commands (not for stop command)
        if direction != "stop":
            _schedule_auto_stop(camera_name, ptz_config, out_queue, timeout_seconds)
            log.info(f"[{camera_name}] PTZ will auto-stop in {timeout_seconds}s")
        
        _emit_ptz_result(
            out_queue,
            camera_name,
            "ptz_move_result",
            "success",
            direction=direction,
            speed=speed,
            timeout=timeout_seconds,
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


def _cancel_active_timer(camera_name: str) -> None:
    """
    Cancel active auto-stop timer for camera.
    
    Args:
        camera_name: Name of camera
    """
    if camera_name in _active_timers:
        timer = _active_timers[camera_name]
        if timer.is_alive():
            timer.cancel()
            log.debug("[%s] Cancelled active auto-stop timer", camera_name)
        del _active_timers[camera_name]


def _schedule_auto_stop(
    camera_name: str,
    ptz_config: Dict[str, Any],
    out_queue: "queue.Queue[dict]",
    timeout_seconds: float,
) -> None:
    """
    Schedule automatic stop command after timeout.
    
    Args:
        camera_name: Name of camera
        ptz_config: PTZ configuration
        out_queue: Output queue for results
        timeout_seconds: Seconds before auto-stop
    """
    def auto_stop():
        log.info("[%s] Auto-stopping PTZ after %.1fs timeout", camera_name, timeout_seconds)
        # Send stop command
        base_url = "http://192.168.1.171/cgi-bin/ptz.cgi?cameraID=1"
        stop_url = f"{base_url}&action=stop"
        
        try:
            fetch_text(
                stop_url,
                timeout_seconds=5.0,
                username=ptz_config.get("username"),
                password=ptz_config.get("password"),
            )
            log.info("[%s] PTZ auto-stopped successfully", camera_name)
            
            _emit_ptz_result(
                out_queue,
                camera_name,
                "ptz_auto_stop",
                "success",
                message="Auto-stopped after timeout"
            )
        except Exception as e:
            log.error("[%s] Auto-stop failed: %s", camera_name, e)
        
        # Clean up timer reference
        if camera_name in _active_timers:
            del _active_timers[camera_name]
    
    # Cancel any existing timer
    _cancel_active_timer(camera_name)
    
    # Schedule new timer
    timer = threading.Timer(timeout_seconds, auto_stop)
    timer.daemon = True
    timer.start()
    _active_timers[camera_name] = timer
    
    log.debug("[%s] Scheduled auto-stop in %.1fs", camera_name, timeout_seconds)


def _parse_ptz_move_payload(payload: str) -> Tuple[str, int, float]:
    """
    Parse PTZ move command payload.
    
    Args:
        payload: Payload string in format:
                 - "direction" (e.g., "up")
                 - "direction:speed" (e.g., "up:8")
                 - "direction:speed:timeout" (e.g., "up:8:3.5")
                 - JSON: {"direction": "up", "speed": 8, "timeout": 3.5}
        
    Returns:
        Tuple of (direction, speed, timeout_seconds)
    """
    default_timeout = 2.0  # Default 2 seconds
    
    # Try to parse as JSON first
    try:
        data = json.loads(payload)
        direction = data.get("direction", "stop")
        speed = int(data.get("speed", 5))
        timeout = float(data.get("timeout", default_timeout))
        return direction, speed, timeout
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    
    # Parse as colon-separated string
    if ":" in payload:
        parts = payload.split(":")
        direction = parts[0]
        
        # Parse speed
        try:
            speed = int(parts[1]) if len(parts) > 1 else 5
        except ValueError:
            speed = 5
        
        # Parse timeout
        try:
            timeout = float(parts[2]) if len(parts) > 2 else default_timeout
        except (ValueError, IndexError):
            timeout = default_timeout
    else:
        direction = payload
        speed = 5
        timeout = default_timeout
    
    return direction, speed, timeout


def _process_ptz_command(
    cmd_data: Dict[str, Any],
    camera_name: str,
    ptz_config: Dict[str, Any],
    out_queue: "queue.Queue[dict]",
    mode_manager = None,
) -> None:
    """
    Process PTZ command.
    
    Args:
        cmd_data: Command data dictionary
        camera_name: Name of camera
        ptz_config: PTZ configuration
        out_queue: Output queue for results
        mode_manager: Optional mode manager for Auto/Manual control
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
            direction, speed, timeout = _parse_ptz_move_payload(payload)
            log.info(f"Direction: {direction}, Speed: {speed}, Timeout: {timeout}s")
            _execute_ptz_move(direction, speed, camera_name, ptz_config, out_queue, mode_manager, timeout)
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
    mode_manager = None,
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
        mode_manager: Optional mode manager for Auto/Manual control
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
            _process_ptz_command(cmd_data, camera_name, ptz_config, out_queue, mode_manager)
        except json.JSONDecodeError:
            log.error(f"Invalid JSON command: {cmd}")
        except Exception as e:
            log.error(f"Error processing PTZ command: {cmd} - {e}")
    
    log.info("PTZ controller stopped for camera: %s", camera_name)


__all__ = ["ptz_controller_worker"]
