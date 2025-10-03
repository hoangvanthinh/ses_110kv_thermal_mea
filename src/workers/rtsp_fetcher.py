import threading
import queue
from datetime import datetime
from typing import Optional
import json

from utils.http import fetch_text, HTTPError, URLError
from utils.logging import get_logger


log = get_logger("workers.rtsp_fetcher")

def rtsp_fetcher_worker(
    out_queue: "queue.Queue[dict]",
    cmd_queue: "queue.Queue[str]",
    stop_event: threading.Event,
) -> None:
    """
    Worker to fetch RTSP URLs for cameras on demand via commands from cmd_queue.
    Expects commands as JSON strings with at least 'camera', 'type', etc.
    """
    import time

    from config_loader import load_config

    config = load_config()
    cameras = config.get("cameras", [])

    # Build a lookup for camera config by name
    camera_lookup = {str(cam.get("name")): cam for cam in cameras if cam.get("name")}

    def fetch_and_emit(camera_name: str, username: str, password: str, url_get_rtsp_url: str) -> None:
        try:
            data = fetch_text(
                url_get_rtsp_url,
                timeout_seconds=5.0,
                username=username,
                password=password,
            )
            rtsp_url = data.strip()
            if username and password and "://" in rtsp_url:
                proto, rest = rtsp_url.split("://", 1)
                rtsp_url = f"{proto}://{username}:{password}@{rest}"

            timestamp = datetime.now().isoformat(timespec="seconds")
            out_queue.put(
                {
                    "sid": camera_name,
                    "type": "rtsp_url",
                    "timestamp": timestamp,
                    "rtsp_url": rtsp_url,
                    "status": "ok"
                },
                block=False,
            )
            log.info("Fetched RTSP URL for %s: %s", camera_name, rtsp_url)
        except (HTTPError, URLError) as e:
            log.error("RTSP fetch error for %s: %s", camera_name, getattr(e, "reason", e))
        except Exception as e:
            log.exception("Unexpected error while fetching RTSP URL for %s: %s", camera_name, e)

    while not stop_event.wait(0.5):
        try:
            cmd = cmd_queue.get_nowait()
        except queue.Empty:
            continue

        try:
            cmd_data = json.loads(cmd)
            camera_name = cmd_data.get("camera")
            if not camera_name:
                log.warning("RTSP fetcher: missing camera name in command: %s", cmd)
                continue

            cam_cfg = camera_lookup.get(str(camera_name))
            if not cam_cfg:
                log.warning("RTSP fetcher: unknown camera '%s'", camera_name)
                continue

            username = cam_cfg.get("username")
            password = cam_cfg.get("password")
            url_get_rtsp_url = cam_cfg.get("url_get_rtsp_url")
            if not url_get_rtsp_url:
                log.warning("RTSP fetcher: missing url_get_rtsp_url for camera '%s'", camera_name)
                continue

            fetch_and_emit(camera_name, username, password, url_get_rtsp_url)
        except Exception as e:
            log.error("RTSP fetcher: error processing command: %s", e)



__all__ = ["rtsp_fetcher_worker"]
