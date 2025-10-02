import threading
import queue
from datetime import datetime
from typing import Optional, List
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
    node_thermals: Optional[List[dict]] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    settle_seconds: Optional[float] = None,
) -> None:
    while not stop_event.is_set():
        try:
            # Two-step mode per node_thermal: preset -> wait -> read temperature
            if node_thermals:
                for node_thermal in node_thermals:
                    url_presetID = node_thermal.get("url_presetID")
                    url_areaTemperature = node_thermal.get(
                        "url_areaTemperature")
                    node_thermal_name = node_thermal.get("name") or "unknown"
                    if not url_areaTemperature:
                        log.error(
                            "[%s] Missing url_areaTemperature for a node_thermal entry", name)
                        continue

                    if url_presetID:
                        try:
                            _ = fetch_text(
                                url_presetID,
                                timeout_seconds=timeout_seconds or 5.0,
                                username=username,
                                password=password,
                            )
                            log.info("[%s] Invoked preset via %s",
                                     node_thermal_name, url_presetID)
                        except HTTPError as e:
                            log.error("[%s] Preset HTTP error: %s %s",
                                      name, e.code, e.reason)
                            continue
                        except URLError as e:
                            log.error("[%s] Preset URL error: %s",
                                      name, e.reason)
                            continue

                        # Allow node_thermal to settle before reading temperature
                        wait_seconds = (
                            settle_seconds if settle_seconds is not None else 5.0)
                        if stop_event.wait(wait_seconds):
                            break

                    data = fetch_text(
                        url_areaTemperature,
                        timeout_seconds=timeout_seconds or 5.0,
                        username=username,
                        password=password,
                    )
                    # log.info(data)
                    # Parse average temperature from response
                    for line in data.splitlines():
                        # neu khong co ave thi data van bang data ERROR => gay sai, Tai sao thieu data?
                        if line.startswith("aveTemperature="):
                            data = line.split("=")[1].strip()
                            break

                    timestamp = datetime.now().isoformat(timespec="seconds")

                    out_queue.put(
                        {
                            "camera": name,
                            "type": "temperature",
                            "node_thermal": node_thermal_name,
                            "url": url_areaTemperature,
                            "timestamp": timestamp,
                            "data_t": data,
                        },
                        block=False,
                    )
                    # log.info("[%s] Read temperature data: %s",
                    #          node_thermal_name, data)
            else:
                log.error("[%s] No node_thermals configured", name)
                break
        except HTTPError as e:
            log.error("[%s] HTTP error: %s %s", name, e.code, e.reason)
        except URLError as e:
            log.error("[%s] URL error: %s", name, e.reason)
        except Exception as e:
            log.exception("[%s] Unexpected error: %s", name, e)

        if stop_event.wait(interval_seconds):
            break


__all__ = ["poller_worker"]
