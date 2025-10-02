import threading
import json
from typing import Dict, Any, List

from utils.logging import get_logger


log = get_logger("workers.mqtt_subscriber")


def mqtt_subscriber_worker(
    settings: Dict[str, Any],
    stop_event: threading.Event,
    cmd_queue: "queue.Queue[str]" = None,
    camera_names: List[str] = [],
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
    base_topic = (settings or {}).get("topic")
    camera_names = (settings or {}).get("camera_names") or camera_names
    # Derive subscription base from the first path segment of base_topic by default
    subscribe_base = (base_topic.split(
        "/")[0] if base_topic else "camera")
    if camera_names:
        # Remove square brackets from camera names
        cleaned_camera_names = [name.strip("[]'") for name in camera_names]
        subscribe_base = f"{subscribe_base}/{cleaned_camera_names[0]}"
    default_topics: List[str] = [
        f"{subscribe_base}/cmd",
        f"{subscribe_base}/get_url",
    ]
    subscribe_topics: List[str] = list(default_topics)
    log.info("Subscribe topics: %s", subscribe_topics)

    client = mqtt.Client()
    if username and password:
        client.username_pw_set(username, password)

    # type: ignore[no-redef]
    def on_connect(client_obj, _userdata, _flags, rc):
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
        # Extract camera name from topic path
        topic_parts = topic.split('/')
        camera_name = None
        for name in camera_names:
            if name in topic_parts:
                camera_name = name
                break

        if camera_name:
            if cmd_queue is not None:
                try:
                    msg_data = {
                        "camera": camera_name,
                        "topic": topic,
                        "payload": payload_text.strip()
                    }

                    if topic.endswith("/get_url") or topic.endswith("/get_url_rtsp"):
                        msg_data["type"] = "get_url_rtsp"
                    elif topic.endswith("/cmd"):
                        msg_data["type"] = "command"

                    cmd_queue.put_nowait(json.dumps(msg_data))
                except queue.Full:
                    log.error(
                        "Command queue is full; dropping command from %s", topic)
        log.info("[MQTT] %s -> %s", topic, payload_text)

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
