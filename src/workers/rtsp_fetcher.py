"""RTSP URL fetcher worker."""
import threading
import queue
import json
from datetime import datetime
from typing import Optional, Dict, Any

from config_loader import load_config
from utils.http import fetch_text, HTTPError, URLError
from utils.logging import get_logger


log = get_logger("workers.rtsp_fetcher")


def _inject_credentials_into_rtsp_url(
    rtsp_url: str,
    username: Optional[str],
    password: Optional[str],
) -> str:
    """
    Inject username and password into RTSP URL.
    
    Args:
        rtsp_url: Original RTSP URL
        username: Username for authentication
        password: Password for authentication
        
    Returns:
        RTSP URL with credentials
    """
    if not username or not password or "://" not in rtsp_url:
        return rtsp_url
    
    proto, rest = rtsp_url.split("://", 1)
    return f"{proto}://{username}:{password}@{rest}"


def _fetch_rtsp_url(
    camera_name: str,
    url_get_rtsp: str,
    username: Optional[str],
    password: Optional[str],
) -> Optional[str]:
    """
    Fetch RTSP URL from camera.
    
    Args:
        camera_name: Name of camera
        url_get_rtsp: URL to fetch RTSP stream info
        username: Optional authentication username
        password: Optional authentication password
        
    Returns:
        RTSP URL string or None if failed
    """
    try:
        data = fetch_text(
            url_get_rtsp,
            timeout_seconds=5.0,
            username=username,
            password=password,
        )
        rtsp_url = data.strip()
        rtsp_url = _inject_credentials_into_rtsp_url(rtsp_url, username, password)
        
        log.info("Fetched RTSP URL for %s: %s", camera_name, rtsp_url)
        return rtsp_url
        
    except (HTTPError, URLError) as e:
        log.error("RTSP fetch error for %s: %s", camera_name, getattr(e, "reason", e))
        return None
    except Exception as e:
        log.exception("Unexpected error while fetching RTSP URL for %s: %s", camera_name, e)
        return None


def _emit_rtsp_result(
    out_queue: "queue.Queue[dict]",
    camera_name: str,
    rtsp_url: Optional[str],
    status: str,
) -> None:
    """
    Emit RTSP fetch result to output queue.
    
    Args:
        out_queue: Output queue
        camera_name: Name of camera
        rtsp_url: RTSP URL or None if failed
        status: Status string ("ok" or "error")
    """
    try:
        result = {
            "sid": camera_name,
            "type": "rtsp_url",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "status": status,
        }
        
        if rtsp_url:
            result["rtsp_url"] = rtsp_url
        
        out_queue.put(result, block=False)
    except queue.Full:
        log.warning("Output queue full, dropping RTSP result for %s", camera_name)


def _process_rtsp_command(
    cmd_data: Dict[str, Any],
    camera_lookup: Dict[str, Dict[str, Any]],
    out_queue: "queue.Queue[dict]",
) -> None:
    """
    Process RTSP fetch command.
    
    Args:
        cmd_data: Command data dictionary
        camera_lookup: Lookup dictionary of camera configs by name
        out_queue: Output queue for results
    """
    camera_name = cmd_data.get("camera")
    if not camera_name:
        log.warning("RTSP fetcher: missing camera name in command: %s", cmd_data)
        return
    
    # Find camera config
    cam_cfg = camera_lookup.get(str(camera_name))
    if not cam_cfg:
        log.warning("RTSP fetcher: unknown camera '%s'", camera_name)
        _emit_rtsp_result(out_queue, camera_name, None, "error")
        return
    
    # Validate camera config
    url_get_rtsp = cam_cfg.get("url_get_rtsp_url")
    if not url_get_rtsp:
        log.warning("RTSP fetcher: missing url_get_rtsp_url for camera '%s'", camera_name)
        _emit_rtsp_result(out_queue, camera_name, None, "error")
        return
    
    # Fetch RTSP URL
    username = cam_cfg.get("username")
    password = cam_cfg.get("password")
    
    rtsp_url = _fetch_rtsp_url(camera_name, url_get_rtsp, username, password)
    
    # Emit result
    status = "ok" if rtsp_url else "error"
    _emit_rtsp_result(out_queue, camera_name, rtsp_url, status)


def rtsp_fetcher_worker(
    out_queue: "queue.Queue[dict]",
    cmd_queue: "queue.Queue[str]",
    stop_event: threading.Event,
) -> None:
    """
    Worker to fetch RTSP URLs for cameras on demand.
    
    Listens to command queue for RTSP fetch requests and retrieves
    RTSP stream URLs from cameras, then emits results to output queue.
    
    Args:
        out_queue: Output queue for RTSP results
        cmd_queue: Command queue for incoming requests
        stop_event: Event to signal worker shutdown
    """
    # Load camera configurations
    config = load_config()
    cameras = config.get("cameras", [])
    
    # Build lookup for camera config by both name and sid
    camera_lookup = {}
    for cam in cameras:
        cam_name = cam.get("camera_name")
        cam_sid = cam.get("camera_sid")
        if cam_name:
            camera_lookup[str(cam_name)] = cam
        if cam_sid:
            camera_lookup[str(cam_sid)] = cam
    
    log.info("RTSP fetcher started with %d camera(s)", len(cameras))
    
    while not stop_event.wait(0.5):
        try:
            cmd = cmd_queue.get_nowait()
        except queue.Empty:
            continue
        
        try:
            cmd_data = json.loads(cmd)
            _process_rtsp_command(cmd_data, camera_lookup, out_queue)
        except json.JSONDecodeError:
            log.error("RTSP fetcher: invalid JSON command: %s", cmd)
        except Exception as e:
            log.error("RTSP fetcher: error processing command: %s", e)
    
    log.info("RTSP fetcher stopped")


__all__ = ["rtsp_fetcher_worker"]
