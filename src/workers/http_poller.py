import threading
import queue
from datetime import datetime
from typing import Optional

from utils.http import fetch_text, HTTPError, URLError
from utils.logging import get_logger
from utils.types import QueueItem


log = get_logger("workers.http_poller")


def poller_worker(
    name: str,
    url: str,
    interval_seconds: int,
    out_queue: "queue.Queue[QueueItem]",
    stop_event: threading.Event,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
) -> None:
    while not stop_event.is_set():
        try:
            data = fetch_text(
                url,
                timeout_seconds=timeout_seconds or 5.0,
                username=username,
                password=password,
            )
            timestamp = datetime.now().isoformat(timespec="seconds")
            out_queue.put(
                {
                    "poller": name,
                    "url": url,
                    "timestamp": timestamp,
                    "data": data,
                },
                block=False,
            )
        except HTTPError as e:
            log.error("[%s] HTTP error: %s %s", name, e.code, e.reason)
        except URLError as e:
            log.error("[%s] URL error: %s", name, e.reason)
        except Exception as e:
            log.exception("[%s] Unexpected error: %s", name, e)

        if stop_event.wait(interval_seconds):
            break


__all__ = ["poller_worker"]


