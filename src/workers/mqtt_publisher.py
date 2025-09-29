import threading
import queue
import json
from typing import Dict, Any

from utils.logging import get_logger


log = get_logger("workers.mqtt_publisher")


def mqtt_publisher_worker(
    settings: Dict[str, Any],
    in_queue: "queue.Queue[dict]",
    stop_event: threading.Event,
) -> None:
    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except Exception:
        log.warning("MQTT library not available. Falling back to stdout.")
        while not stop_event.is_set():
            try:
                item = in_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            log.info("[%s] %s -> %s\n%s", item.get("timestamp"), item.get("poller"), item.get("url"), item.get("data"))
        return

    client = mqtt.Client()
    username = (settings or {}).get("username") or None
    password = (settings or {}).get("password") or None
    if username and password:
        client.username_pw_set(username, password)
    host = (settings or {}).get("host", "localhost")
    port = int((settings or {}).get("port", 1883))
    base_topic = (settings or {}).get("topic", "camera/areaTemperature")

    try:
        client.connect(host, port, keepalive=60)
        client.loop_start()
    except Exception as e:
        log.error("Failed to connect to MQTT broker %s:%s: %s", host, port, e)
        return

    try:
        while not stop_event.is_set():
            try:
                item = in_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break

            topic = f"{base_topic}/{item.get('poller','unknown')}"
            payload = json.dumps(item, ensure_ascii=False)
            try:
                client.publish(topic, payload, qos=0, retain=False)
            except Exception as e:
                log.error("MQTT publish error: %s", e)
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass


__all__ = ["mqtt_publisher_worker"]


