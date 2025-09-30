import threading
import queue
from datetime import datetime
from typing import Optional

from utils.http import fetch_text, HTTPError, URLError
from utils.logging import get_logger


log = get_logger("workers.rtsp_fetcher")


def rtsp_fetcher_worker(
    url_get_rtsp_url: str,
    out_queue: "queue.Queue[dict]",
    cmd_queue: "queue.Queue[str]",
    stop_event: threading.Event,
    username: Optional[str] = None,
    password: Optional[str] = None,
    poll_interval_seconds: float = 0.5,
) -> None:
    def fetch_and_emit() -> None:
        try:
            data = fetch_text(
                url_get_rtsp_url,
                timeout_seconds=5.0,
                username=username,
                password=password,
            )
            timestamp = datetime.now().isoformat(timespec="seconds")
            out_queue.put(
                {
                    "type": "rtsp_url",
                    "timestamp": timestamp,
                    "url": url_get_rtsp_url,
                    "rtsp_url": data.strip(),
                },
                block=False,
            )
            log.info("Fetched RTSP URL: %s", data.strip())
        except (HTTPError, URLError) as e:
            log.error("RTSP fetch error: %s", getattr(e, "reason", e))
        except Exception as e:
            log.exception("Unexpected error while fetching RTSP URL: %s", e)

    # Fetch once at startup
    fetch_and_emit()

    # Process commands
    while not stop_event.wait(poll_interval_seconds):
        try:
            cmd = cmd_queue.get_nowait()
        except queue.Empty:
            continue

        if cmd == "get_url_rtsp":
            fetch_and_emit()
        else:
            log.debug("Ignored command: %s", cmd)


__all__ = ["rtsp_fetcher_worker"]


