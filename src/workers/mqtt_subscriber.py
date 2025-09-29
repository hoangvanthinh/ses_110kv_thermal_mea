import threading
from typing import Dict, Any, List

from utils.logging import get_logger


log = get_logger("workers.mqtt_subscriber")


def mqtt_subscriber_worker(
    settings: Dict[str, Any],
    stop_event: threading.Event,
    cmd_queue: "queue.Queue[str]" = None,
) -> None:
    import queue
    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except Exception:
        log.error("MQTT library not available; subscriber cannot start.")
        return

    username = (settings or {}).get("username") or None
    password = (settings or {}).get("password") or None
    host = (settings or {}).get("host", "localhost")
    port = int((settings or {}).get("port", 1883))
    base_topic = (settings or {}).get("topic", "node_thermal/areaTemperature")

    # Derive subscription base from the first path segment of base_topic by default
    subscribe_base = (settings or {}).get("subscribe_base") or (base_topic.split("/")[0] if base_topic else "node_thermal")
    default_topics: List[str] = [
        f"{subscribe_base}/cmd",
        f"{subscribe_base}/get_url",
    ]
    subscribe_topics: List[str] = list((settings or {}).get("subscribe_topics") or default_topics)

    client = mqtt.Client()
    if username and password:
        client.username_pw_set(username, password)

    def on_connect(client_obj, _userdata, _flags, rc):  # type: ignore[no-redef]
        if rc == 0:
            for topic in subscribe_topics:
                try:
                    client_obj.subscribe(topic)
                    log.info("Subscribed to topic: %s", topic)
                except Exception as e:
                    log.error("Failed to subscribe %s: %s", topic, e)
        else:
            log.error("MQTT connect returned code %s", rc)

    def on_message(_client, _userdata, msg):  # type: ignore[no-redef]
        try:
            payload_text = msg.payload.decode("utf-8", errors="replace")
        except Exception:
            payload_text = "<binary>"
        topic = msg.topic
        log.info("[MQTT] %s -> %s", topic, payload_text)
        if cmd_queue is not None:
            try:
                if topic.endswith("/get_url") or topic.endswith("/get_url_rtsp"):
                    cmd_queue.put_nowait("get_url_rtsp")
                elif topic.endswith("/cmd"):
                    cmd_queue.put_nowait(payload_text.strip())
            except queue.Full:
                log.error("Command queue is full; dropping command from %s", topic)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(host, port, keepalive=60)
        client.loop_start()
    except Exception as e:
        log.error("Subscriber failed to connect to MQTT %s:%s: %s", host, port, e)
        return

    try:
        while not stop_event.wait(0.5):
            pass
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass


__all__ = ["mqtt_subscriber_worker"]


