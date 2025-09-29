import threading
import time
import queue
from typing import List, Optional

from config_loader import load_config

from utils.logging import get_logger
from workers.http_poller import poller_worker
from workers.mqtt_publisher import mqtt_publisher_worker


log = get_logger("main")


def main() -> None:
    stop_event = threading.Event()
    config = load_config()

    out_queue: "queue.Queue[dict]" = queue.Queue(maxsize=100)

    # Start poller threads
    poller_threads: List[threading.Thread] = []
    for p in config.get("pollers", []):
        name = str(p.get("name") or f"poller_{len(poller_threads)+1}")
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
            name=f"poller:{name}",
        )
        t.start()
        poller_threads.append(t)

    # Start publisher unconditionally; worker will drain to stdout if MQTT disabled
    mqtt_cfg = config.get("mqtt", {}) or {}
    mqtt_thread: Optional[threading.Thread] = threading.Thread(
        target=mqtt_publisher_worker,
        args=(mqtt_cfg, out_queue, stop_event),
        daemon=True,
        name="mqtt-publisher",
    )
    mqtt_thread.start()

    log.info(
        "Started %d poller(s). Press Ctrl+C to stop.",
        len(poller_threads),
    )

    try:
        while any(t.is_alive() for t in poller_threads) or (
            mqtt_thread and mqtt_thread.is_alive()
        ):
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping...")
        stop_event.set()
    finally:
        try:
            out_queue.put(None, block=False)  # sentinel for publisher
        except Exception:
            pass

        for t in poller_threads:
            t.join(timeout=5)

        if mqtt_thread is not None:
            mqtt_thread.join(timeout=5)

        log.info("Stopped.")


if __name__ == "__main__":
    main()
