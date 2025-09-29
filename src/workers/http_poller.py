import threading
import queue
from datetime import datetime
from typing import Optional
import time

from utils.http import fetch_text, HTTPError, URLError
from utils.logging import get_logger
from utils.types import QueueItem


log = get_logger("workers.http_poller")


def poller_worker(
    name: str,
    interval_seconds: int,
    out_queue: "queue.Queue[QueueItem]",
    stop_event: threading.Event,
    cameras: Optional[List[dict]] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    settle_seconds: Optional[float] = None,
) -> None:
    while not stop_event.is_set():
        try:
            data: str
            url_for_item: str

            # Two-step mode: preset -> wait -> read temperature
            if cameras:
                for camera in cameras:
                    url_presetID = camera.get("url_presetID")
                    url_areaTemperature = camera.get("url_areaTemperature")
                try:
                    _ = fetch_text(
                        url_presetID,
                        timeout_seconds=timeout_seconds or 5.0,
                        username=username,
                        password=password,
                    )
                    log.info("[%s] Invoked preset via %s", name, url_presetID)
                except HTTPError as e:
                    log.error("[%s] Preset HTTP error: %s %s",
                              name, e.code, e.reason)
                    if stop_event.wait(interval_seconds):
                        break
                    continue
                except URLError as e:
                    log.error("[%s] Preset URL error: %s", name, e.reason)
                    if stop_event.wait(interval_seconds):
                        break
                    continue

                # Allow camera to settle before reading temperature
                wait_seconds = (
                    settle_seconds if settle_seconds is not None else 6.0)
                if stop_event.wait(wait_seconds):
                    break

                data = fetch_text(
                    url_areaTemperature,
                    timeout_seconds=timeout_seconds or 5.0,
                    username=username,
                    password=password,
                )
                url_for_item = url_areaTemperature

            # Legacy single-URL mode
            elif cameras:
                for camera in cameras:
                    url = camera.get("url_areaTemperature")
                data = fetch_text(
                    url,
                    timeout_seconds=timeout_seconds or 5.0,
                    username=username,
                    password=password,
                )
                url_for_item = url
            else:
                log.error("[%s] No URL configured", name)
                break
            timestamp = datetime.now().isoformat(timespec="seconds")
            out_queue.put(
                {
                    "poller": name,
                    "url": url_for_item,
                    "timestamp": timestamp,
                    "data": data,
                },
                block=False,
            )
            log.info("[%s] Polled data: %s", name, data)
        except HTTPError as e:
            log.error("[%s] HTTP error: %s %s", name, e.code, e.reason)
        except URLError as e:
            log.error("[%s] URL error: %s", name, e.reason)
        except Exception as e:
            log.exception("[%s] Unexpected error: %s", name, e)

        if stop_event.wait(interval_seconds):
            break


__all__ = ["poller_worker"]
