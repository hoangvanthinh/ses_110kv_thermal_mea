import threading
import time
import queue
from typing import List, Optional

from config_loader import load_config

from utils.logging import get_logger
from workers.read_thermal_poller import poller_worker
from workers.mqtt_publisher import mqtt_publisher_worker
from workers.mqtt_subscriber import mqtt_subscriber_worker
from workers.rtsp_fetcher import rtsp_fetcher_worker


log = get_logger("main")


def main() -> None:
    stop_event = threading.Event()
    config = load_config()

    out_queue: "queue.Queue[dict]" = queue.Queue(maxsize=100)

    # Start poller threads
    camera_threads: List[threading.Thread] = []
    for p in config.get("cameras", []):
        name = str(p.get("name") or f"camera_{len(camera_threads)+1}")
        t = threading.Thread(
            target=poller_worker,
            args=(
                name,
                int(p.get("interval_seconds", 10)),
                out_queue,
                stop_event,
                p.get("node_thermals") or None,
                p.get("username") or None,
                p.get("password") or None,
                float(p.get("timeout_seconds", 5.0)),
                float(p.get("settle_seconds", 2.0)),
            ),
            daemon=True,
            name=f"camera:{name}",
        )
        t.start()
        camera_threads.append(t)

    # Start publisher unconditionally; worker will drain to stdout if MQTT disabled
    mqtt_cfg = config.get("mqtt", {}) or {}
    mqtt_thread: Optional[threading.Thread] = threading.Thread(
        target=mqtt_publisher_worker,
        args=(mqtt_cfg, out_queue, stop_event),
        daemon=True,
        name="mqtt-publisher",
    )
    mqtt_thread.start()

    # Start subscriber if MQTT is enabled
    mqtt_enabled = bool(mqtt_cfg.get("enabled", False))
    mqtt_sub_thread: Optional[threading.Thread] = None
    cmd_queue: "queue.Queue[str]" = queue.Queue(maxsize=50)
    if mqtt_enabled:
        mqtt_sub_thread = threading.Thread(
            target=mqtt_subscriber_worker,
            args=(mqtt_cfg, stop_event, cmd_queue),
            daemon=True,
            name="mqtt-subscriber",
        )
        mqtt_sub_thread.start()

    # Start RTSP fetcher worker(s) per poller that defines rtsp_endpoint
    rtsp_threads: List[threading.Thread] = []
    for p in config.get("cameras", []):
        endpoint = p.get("url_get_rtsp_url")
        if not endpoint:
            continue
        t = threading.Thread(
            target=rtsp_fetcher_worker,
            args=(endpoint, out_queue, cmd_queue, stop_event, p.get(
                "username") or None, p.get("password") or None),
            daemon=True,
            name=f"rtsp-fetcher:{p.get('name') or 'unknown'}",
        )
        t.start()
        rtsp_threads.append(t)

    log.info(
        "Started %d poller(s). Press Ctrl+C to stop.",
        len(camera_threads),
    )

    try:
        while any(t.is_alive() for t in camera_threads) or (
            mqtt_thread and mqtt_thread.is_alive()
        ) or (
            mqtt_sub_thread and mqtt_sub_thread.is_alive()
        ) or any(t.is_alive() for t in rtsp_threads):
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping...")
        stop_event.set()
    finally:
        try:
            out_queue.put(None, block=False)  # sentinel for publisher
        except Exception:
            pass

        for t in camera_threads:
            t.join(timeout=5)

        if mqtt_thread is not None:
            mqtt_thread.join(timeout=5)
        if mqtt_sub_thread is not None:
            mqtt_sub_thread.join(timeout=5)
        for t in rtsp_threads:
            t.join(timeout=5)

        log.info("Stopped.")


if __name__ == "__main__":
    main()
