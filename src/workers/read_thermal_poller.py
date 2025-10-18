"""Thermal camera polling worker."""
import threading
import queue
from datetime import datetime
from typing import Optional, List, Dict, Any

from utils.http import fetch_text, HTTPError, URLError
from utils.logging import get_logger
from utils.types import QueueItem


log = get_logger("workers.thermal_poller")


def _parse_temperature_from_response(response_text: str) -> str:
    """
    Parse average temperature value from camera response.
    
    Args:
        response_text: Raw response text from camera
        
    Returns:
        Temperature value string
    """
    for line in response_text.splitlines():
        if line.startswith("aveTemperature="):
            return line.split("=")[1].strip()
    return response_text


def _invoke_preset(
    preset_url: str,
    node_name: str,
    timeout_seconds: float,
    username: Optional[str],
    password: Optional[str],
) -> bool:
    """
    Invoke PTZ preset position.
    
    Args:
        preset_url: URL to invoke preset
        node_name: Name of thermal node
        timeout_seconds: Request timeout
        username: Optional authentication username
        password: Optional authentication password
        
    Returns:
        True if successful, False otherwise
    """
    try:
        fetch_text(
            preset_url,
            timeout_seconds=timeout_seconds,
            username=username,
            password=password,
        )
        log.info("[%s] Invoked preset via %s", node_name, preset_url)
        return True
    except HTTPError as e:
        log.error("[%s] Preset HTTP error: %s %s", node_name, e.code, e.reason)
        return False
    except URLError as e:
        log.error("[%s] Preset URL error: %s", node_name, e.reason)
        return False


def _read_temperature(
    temp_url: str,
    timeout_seconds: float,
    username: Optional[str],
    password: Optional[str],
) -> Optional[str]:
    """
    Read temperature from camera.
    
    Args:
        temp_url: URL to read temperature
        timeout_seconds: Request timeout
        username: Optional authentication username
        password: Optional authentication password
        
    Returns:
        Temperature value or None if failed
    """
    try:
        response = fetch_text(
            temp_url,
            timeout_seconds=timeout_seconds,
            username=username,
            password=password,
        )
        return _parse_temperature_from_response(response)
    except (HTTPError, URLError) as e:
        log.error("Temperature read error: %s", e)
        return None


def _process_node_thermal(
    node_thermal: Dict[str, Any],
    camera_name: str,
    out_queue: "queue.Queue[QueueItem]",
    stop_event: threading.Event,
    username: Optional[str],
    password: Optional[str],
    timeout_seconds: float,
    settle_seconds: float,
) -> bool:
    """
    Process a single thermal node: invoke preset, wait, read temperature.
    
    Args:
        node_thermal: Node thermal configuration
        camera_name: Name of camera
        out_queue: Output queue for temperature data
        stop_event: Event to signal stop
        username: Optional authentication username
        password: Optional authentication password
        timeout_seconds: Request timeout
        settle_seconds: Time to wait after preset invocation
        
    Returns:
        True if should continue, False if should stop
    """
    node_name = node_thermal.get("name", "unknown")
    url_preset = node_thermal.get("url_presetID")
    url_temperature = node_thermal.get("url_areaTemperature")
    
    # Validate required URL
    if not url_temperature:
        log.error("[%s] Missing url_areaTemperature for node", camera_name)
        return True
    
    # Step 1: Invoke preset if configured
    if url_preset:
        success = _invoke_preset(
            url_preset,
            node_name,
            timeout_seconds,
            username,
            password,
        )
        
        if not success:
            return True
        
        # Wait for camera to settle
        if stop_event.wait(settle_seconds):
            return False
    
    # Step 2: Read temperature
    temperature = _read_temperature(
        url_temperature,
        timeout_seconds,
        username,
        password,
    )
    
    if temperature is None:
        return True
    
    # Step 3: Publish temperature data
    try:
        out_queue.put(
            {
                "camera": camera_name,
                "type": "temperature",
                "node_thermal": node_name,
                "url": url_temperature,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "data_t": temperature,
            },
            block=False,
        )
    except queue.Full:
        log.warning("[%s] Output queue full, dropping temperature data", camera_name)
    
    return True


def poller_worker(
    name: str,
    interval_seconds: int,
    out_queue: "queue.Queue[QueueItem]",
    stop_event: threading.Event,
    preset_thermals: Optional[List[Dict[str, Any]]] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    settle_seconds: Optional[float] = None,
) -> None:
    """
    Thermal camera polling worker.
    
    Polls thermal nodes at regular intervals, invoking PTZ presets and reading temperatures.
    
    Args:
        name: Camera name
        interval_seconds: Polling interval in seconds
        out_queue: Output queue for temperature data
        stop_event: Event to signal worker shutdown
        preset_thermals: List of thermal preset configurations
        username: Optional authentication username
        password: Optional authentication password
        timeout_seconds: HTTP request timeout (default: 5.0)
        settle_seconds: Time to wait after preset invocation (default: 5.0)
    """
    if not preset_thermals:
        log.error("[%s] No preset_thermals configured", name)
        return
    
    timeout = timeout_seconds or 5.0
    settle_time = settle_seconds or 5.0
    
    log.info("[%s] Starting thermal poller with %d nodes", name, len(preset_thermals))
    
    while not stop_event.is_set():
        try:
            # Process each thermal node
            for node_thermal in preset_thermals:
                should_continue = _process_node_thermal(
                    node_thermal,
                    name,
                    out_queue,
                    stop_event,
                    username,
                    password,
                    timeout,
                    settle_time,
                )
                
                if not should_continue:
                    return
                    
        except Exception as e:
            log.exception("[%s] Unexpected error: %s", name, e)
        
        # Wait for next polling interval
        if stop_event.wait(interval_seconds):
            break
    
    log.info("[%s] Thermal poller stopped", name)


__all__ = ["poller_worker"]
