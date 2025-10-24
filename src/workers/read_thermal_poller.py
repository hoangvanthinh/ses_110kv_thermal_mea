"""Thermal camera polling worker."""
import os
import threading
import queue
from datetime import datetime
from typing import Optional, List, Dict, Any, NamedTuple
from dataclasses import dataclass

from utils.http import fetch_text, HTTPError, URLError
from utils.logging import get_logger
from utils.types import QueueItem


log = get_logger("workers.thermal_poller")


@dataclass
class ThermalNode:
    """Represents a thermal measurement node."""
    sid: str
    name: str
    url: str
    id_node: Optional[int] = None


@dataclass
class ThermalPreset:
    """Represents a thermal preset configuration."""
    name: str
    preset_url: Optional[str]
    temperature_url: Optional[str]
    nodes: List[ThermalNode]


@dataclass
class TemperatureData:
    """Represents temperature measurement data."""
    camera: str
    sid: str
    node_thermal: str
    node_name: str
    temperature: Dict[str, Any]
    timestamp: str
    sent_at: str
    img: str


class ThermalPollerConfig:
    """Configuration for thermal poller."""
    
    def __init__(
        self,
        name: str,
        interval_seconds: int,
        timeout_seconds: float = 5.0,
        settle_seconds: float = 5.0,
        username: Optional[str] = None,
        password: Optional[str] = None,
        url_snapshot: Optional[str] = None,
        img_server_host: Optional[str] = None,
    ):
        self.name = name
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds
        self.settle_seconds = settle_seconds
        self.username = username
        self.password = password
        self.url_snapshot = url_snapshot
        self.img_server_host = img_server_host


def _parse_thermal_preset_from_config(preset_config: Dict[str, Any]) -> ThermalPreset:
    """Parse thermal preset configuration from dictionary."""
    nodes = []
    for node_config in preset_config.get("nodes", []):
        node = ThermalNode(
            sid=node_config.get("SID", "unknown"),
            name=node_config.get("name_node", "unknown"),
            url=node_config.get("url_areaTemperature", ""),
            id_node=node_config.get("ID_node")
        )
        nodes.append(node)
    
    return ThermalPreset(
        name=preset_config.get("preset_name", "unknown"),
        preset_url=preset_config.get("url_presetID"),
        temperature_url=preset_config.get("url_areaTemperature"),
        nodes=nodes
    )


def _parse_temperature_from_response(response_text: str) -> Dict[str, Any]:
    """
    Parse temperature value from camera response and return structured object.
    
    Args:
        response_text: Raw response text from camera
        
    Returns:
        Dictionary with 'value' (float) and 'unit' (string) keys
    """
    for line in response_text.splitlines():
        if line.startswith("maxTemperature="):
            temp_str = line.split("=")[1].strip()
            try:
                # Try to parse as float, default to 0.0 if parsing fails
                temp_value = float(temp_str)
                return {
                    "value": temp_value,
                    "unit": "C"
                }
            except ValueError:
                # If parsing fails, return the raw string as value
                return {
                    "value": temp_str,
                    "unit": "C"
                }
    
    # If no maxTemperature line found, return the raw response
    return {
        "value": response_text,
        "unit": "C"
    }


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
) -> Optional[Dict[str, Any]]:
    """
    Read temperature from camera.
    
    Args:
        temp_url: URL to read temperature
        timeout_seconds: Request timeout
        username: Optional authentication username
        password: Optional authentication password
        
    Returns:
        Temperature object with 'value' and 'unit' keys, or None if failed
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


def _publish_temperature_data(
    data: TemperatureData,
    out_queue: "queue.Queue[QueueItem]",
    camera_name: str,
) -> None:
    """Publish temperature data to output queue."""
    try:
        queue_item = {
            "camera": data.camera,
            "type": "temperature",
            "sid": data.sid,
            "node_thermal": data.node_thermal,
            "node_name": data.node_name,
            "timestamp": data.timestamp,  # legacy, will be removed
            "sent_at": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "temperature": data.temperature,
            "img": data.img,
        }
        out_queue.put(queue_item, block=False)
    except queue.Full:
        log.warning(
            "[%s] Output queue full, dropping temperature data (sid=%s)", 
            camera_name, 
            data.sid
        )


def _capture_snapshot(
    snapshot_url: str,
    timeout_seconds: float,
    username: Optional[str],
    password: Optional[str],
    camera_name: str,
) -> Optional[bytes]:
    """
    Capture snapshot image from camera.
    
    Args:
        snapshot_url: URL to capture snapshot
        timeout_seconds: Request timeout
        username: Optional authentication username
        password: Optional authentication password
        camera_name: Name of camera for logging
        
    Returns:
        Snapshot image bytes, or None if failed
    """
    try:
        from utils.http import fetch_binary
        snapshot_bytes = fetch_binary(
            snapshot_url,
            timeout_seconds=timeout_seconds,
            username=username,
            password=password,
        )
        log.info("[%s] Snapshot captured from %s", camera_name, snapshot_url)
        return snapshot_bytes
    except Exception as e:
        log.error("[%s] Snapshot capture failed: %s", camera_name, e)
        return None


def _save_snapshot_to_img_server(
    snapshot_bytes: bytes,
    camera_name: str,
    preset_name: str,
    server_save_dir: str = "/FTPserver",
) -> Optional[str]:
    """
    Save snapshot image to img_server directory.
    
    Args:
        snapshot_bytes: Image data in bytes
        camera_name: Name of camera
        preset_name: Name of preset
        server_save_dir: Directory path to save images (default: /FTPserver)
        
    Returns:
        Local file path if saved successfully, None if failed
    """
    try:
        # Create unique filename with timestamp
        fname = f"{camera_name}_{preset_name}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')}.jpg"
        os.makedirs(server_save_dir, exist_ok=True)
        local_file_path = os.path.join(server_save_dir, fname)
        
        with open(local_file_path, "wb") as f:
            f.write(snapshot_bytes)
        
        log.info("[%s] Snapshot saved to %s", camera_name, local_file_path)
        return local_file_path
    except Exception as e:
        log.error("[%s] Failed to save snapshot: %s", camera_name, e)
        return None

def _process_thermal_nodes(
    preset: ThermalPreset,
    camera_name: str,
    out_queue: "queue.Queue[QueueItem]",
    stop_event: threading.Event,
    config: ThermalPollerConfig,
) -> bool:
    """Process all thermal nodes in a preset."""
    if not preset.nodes:
        log.error("[%s] No nodes configured in preset '%s'", camera_name, preset.name)
        return True

    # Capture snapshot and save to img_server
    img_url_on_server = ""

    if config.url_snapshot:
        # Step 1: Capture snapshot from camera
        snapshot_bytes = _capture_snapshot(
            config.url_snapshot,
            config.timeout_seconds,
            config.username,
            config.password,
            camera_name,
        )
        
        # Step 2: Save snapshot to img_server
        if snapshot_bytes:
            local_file_path = _save_snapshot_to_img_server(
                snapshot_bytes,
                camera_name,
                preset.name,
                server_save_dir="/FTPserver",
            )
            
            if local_file_path and config.img_server_host:
                fname = os.path.basename(local_file_path)
                img_url_on_server = f"http://{config.img_server_host}/{fname}"
    
    # Read temperature from camera and publish to output queue
    for node in preset.nodes:
        if stop_event.is_set():
            return False

        if not node.url:
            log.error("[%s] Missing url_areaTemperature for node SID=%s", camera_name, node.sid)
            continue

        temperature = _read_temperature(
            node.url,
            config.timeout_seconds,
            config.username,
            config.password,
        )

        if temperature is None:
            continue

        data = TemperatureData(
            camera=camera_name,
            sid=node.sid,
            node_thermal=preset.name,
            node_name=node.name,
            temperature=temperature,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            sent_at=datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            img=img_url_on_server,
        )
        
        _publish_temperature_data(data, out_queue, camera_name)

    return True


def _process_node_thermal(
    node_thermal: Dict[str, Any],
    camera_name: str,
    out_queue: "queue.Queue[QueueItem]",
    stop_event: threading.Event,
    username: Optional[str],
    password: Optional[str],
    timeout_seconds: float,
    settle_seconds: float,
    url_snapshot: Optional[str] = None,
    img_server_host: Optional[str] = None,
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
    # Parse configuration
    preset = _parse_thermal_preset_from_config(node_thermal)
    config = ThermalPollerConfig(
        name=camera_name,
        interval_seconds=0,  # Not used in this context
        timeout_seconds=timeout_seconds,
        settle_seconds=settle_seconds,
        username=username,
        password=password,
        url_snapshot=url_snapshot,
        img_server_host=img_server_host,
    )
    
    # Step 1: Invoke preset if configured
    if preset.preset_url:
        success = _invoke_preset(
            preset.preset_url,
            preset.name,
            config.timeout_seconds,
            config.username,
            config.password,
        )
        
        if not success:
            return True
        
        # Wait for camera to settle
        if stop_event.wait(config.settle_seconds):
            return False
    
    # Step 2: Process thermal nodes
    return _process_thermal_nodes(preset, camera_name, out_queue, stop_event, config)


def _validate_preset_config(preset_config: Dict[str, Any], camera_name: str) -> bool:
    """Validate thermal preset configuration."""
    if not preset_config.get("preset_name"):
        log.error("[%s] Missing preset_name in configuration", camera_name)
        return False
    
    nodes = preset_config.get("nodes", [])
    if not nodes:
        log.error("[%s] No nodes configured in preset '%s'", camera_name, preset_config.get("preset_name"))
        return False
    
    for i, node in enumerate(nodes):
        if not node.get("SID"):
            log.error("[%s] Missing SID for node %d in preset '%s'", camera_name, i, preset_config.get("preset_name"))
            return False
        if not node.get("url_areaTemperature"):
            log.error("[%s] Missing url_areaTemperature for node %d in preset '%s'", camera_name, i, preset_config.get("preset_name"))
            return False
    
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
    url_snapshot: Optional[str] = None,
    img_server_host: Optional[str] = None,
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
        url_snapshot: Optional URL to capture snapshot images
        img_server_host: Optional hostname/IP of image server
    """
    if not preset_thermals:
        log.error("[%s] No preset_thermals configured", name)
        return
    
    # Validate all preset configurations
    valid_presets = []
    for preset in preset_thermals:
        if _validate_preset_config(preset, name):
            valid_presets.append(preset)
    
    if not valid_presets:
        log.error("[%s] No valid preset configurations found", name)
        return
    
    timeout = timeout_seconds or 5.0
    settle_time = settle_seconds or 5.0
    
    log.info("[%s] Starting thermal poller with %d valid presets", name, len(valid_presets))
    
    while not stop_event.is_set():
        try:
            # Process each thermal preset
            for node_thermal in valid_presets:
                should_continue = _process_node_thermal(
                    node_thermal,
                    name,
                    out_queue,
                    stop_event,
                    username,
                    password,
                    timeout,
                    settle_time,
                    url_snapshot,
                    img_server_host,
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
