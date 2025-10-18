import threading
import queue
import json
from typing import Dict, Any, List, Optional, Callable

from utils.logging import get_logger


log = get_logger("workers.mqtt_subscriber")


# Topic routing configuration: maps topic suffixes to (message_type, target_queue)
TOPIC_ROUTES = {
    "/get_url": ("get_url_rtsp", "rtsp"),
    "/get_url_rtsp": ("get_url_rtsp", "rtsp"),
    "/ptz_preset": ("ptz_preset", "ptz"),
    "/ptz_move": ("ptz_move", "ptz"),
    "/get_temperature": ("get_temperature", "thermal"),
    "/cmd": ("command", "broadcast"),  # Special case: broadcast to all queues
}


def _extract_camera_name(topic: str, camera_names: List[str]) -> Optional[str]:
    """
    Extract camera name from topic path by matching against known camera names.
    
    Args:
        topic: MQTT topic string
        camera_names: List of valid camera names
        
    Returns:
        Camera name if found in topic, None otherwise
    """
    topic_parts = topic.split('/')
    for name in camera_names:
        if name in topic_parts:
            return name
    return None


def _route_message_to_queue(
    msg_data: Dict[str, Any],
    topic: str,
    cmd_queues: Dict[str, queue.Queue[str]]
) -> None:
    """
    Route message to appropriate command queue(s) based on topic.
    
    Args:
        msg_data: Message data dictionary
        topic: MQTT topic
        cmd_queues: Dictionary of command queues
    """
    # Find matching route
    msg_type = None
    target_queue = None
    
    for topic_suffix, (mtype, queue_name) in TOPIC_ROUTES.items():
        if topic.endswith(topic_suffix):
            msg_type = mtype
            target_queue = queue_name
            break
    
    if not msg_type:
        log.debug("No route found for topic: %s", topic)
        return
    
    msg_data["type"] = msg_type
    msg_json = json.dumps(msg_data)
    
    # Handle broadcast to all queues
    if target_queue == "broadcast":
        for queue_name, cmd_queue in cmd_queues.items():
            try:
                cmd_queue.put_nowait(msg_json)
            except queue.Full:
                log.error(
                    "Queue '%s' is full; dropping command from topic: %s",
                    queue_name, topic
                )
    # Route to specific queue
    elif target_queue in cmd_queues:
        try:
            cmd_queues[target_queue].put_nowait(msg_json)
        except queue.Full:
            log.error(
                "Queue '%s' is full; dropping command from topic: %s",
                target_queue, topic
            )
    else:
        log.warning("Target queue '%s' not found for topic: %s", target_queue, topic)


def _create_on_connect_handler(
    subscribe_topics: List[str]
) -> Callable:
    """
    Create on_connect callback for MQTT client.
    
    Args:
        subscribe_topics: List of topics to subscribe to
        
    Returns:
        Callback function for MQTT on_connect event
    """
    def on_connect(client_obj, _userdata, _flags, rc):
        if rc == 0:
            log.info("MQTT connection established successfully")
            for topic in subscribe_topics:
                try:
                    client_obj.subscribe(topic)
                    log.info("Subscribed to topic: %s", topic)
                except Exception as e:
                    log.error("Failed to subscribe to '%s': %s", topic, e)
        else:
            log.error("MQTT connection failed with return code: %s", rc)
    
    return on_connect


def _create_on_message_handler(
    camera_names: List[str],
    cmd_queues: Optional[Dict[str, queue.Queue[str]]]
) -> Callable:
    """
    Create on_message callback for MQTT client.
    
    Args:
        camera_names: List of camera names
        cmd_queues: Dictionary of command queues
        
    Returns:
        Callback function for MQTT on_message event
    """
    def on_message(_client, _userdata, msg):
        try:
            payload_text = msg.payload.decode("utf-8", errors="replace")
        except Exception as e:
            log.warning("Failed to decode message payload: %s", e)
            payload_text = "<binary>"
        
        topic = msg.topic
        log.info("[MQTT] %s -> %s", topic, payload_text)
        
        # Extract camera name from topic
        camera_name = _extract_camera_name(topic, camera_names)
        if not camera_name:
            log.debug("No camera name found in topic: %s", topic)
            return
        
        # Route message to appropriate queue
        if cmd_queues is not None:
            try:
                msg_data = {
                    "camera": camera_name,
                    "topic": topic,
                    "payload": payload_text.strip()
                }
                _route_message_to_queue(msg_data, topic, cmd_queues)
            except Exception as e:
                log.error("Error routing command from topic '%s': %s", topic, e)
    
    return on_message


def _extract_settings(settings: Dict[str, Any], camera_names: List[str]) -> Dict[str, Any]:
    """
    Extract and validate MQTT settings.
    
    Args:
        settings: Raw settings dictionary
        camera_names: Default camera names
        
    Returns:
        Processed settings dictionary
    """
    safe_settings = settings or {}
    
    return {
        "username": safe_settings.get("username") or None,
        "password": safe_settings.get("password") or None,
        "host": safe_settings.get("host", "localhost"),
        "port": int(safe_settings.get("port", 1883)),
        "base_topic": safe_settings.get("topic"),
        "camera_names": safe_settings.get("camera_names") or camera_names,
    }


def _build_subscribe_topics(base_topic: Optional[str], camera_names: List[str]) -> List[str]:
    """
    Build list of MQTT topics to subscribe to.
    
    Args:
        base_topic: Base topic string
        camera_names: List of camera names
        
    Returns:
        List of subscription topic patterns
    """
    # Derive subscription base from the first path segment of base_topic
    subscribe_base = base_topic.split("/")[0] if base_topic else "camera"
    
    if camera_names:
        return [f"{subscribe_base}/{name}/#" for name in camera_names]
    else:
        return [f"{subscribe_base}/#"]


def mqtt_subscriber_worker(
    settings: Dict[str, Any],
    stop_event: threading.Event,
    cmd_queues: Optional[Dict[str, queue.Queue[str]]] = None,
    camera_names: List[str] = [],
) -> None:
    """
    MQTT subscriber worker that listens to camera topics and routes messages.
    
    Args:
        settings: MQTT connection settings
        stop_event: Event to signal worker shutdown
        cmd_queues: Dictionary of command queues for routing messages
        camera_names: List of camera names to monitor
    """
    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except ImportError:
        log.error("MQTT library (paho-mqtt) not available; subscriber cannot start.")
        return
    
    # Extract and validate settings
    config = _extract_settings(settings, camera_names)
    camera_names = config["camera_names"]
    
    # Build subscription topics
    subscribe_topics = _build_subscribe_topics(config["base_topic"], camera_names)
    log.info("MQTT subscribe topics: %s", subscribe_topics)
    
    # Create and configure MQTT client
    client = mqtt.Client()
    if config["username"] and config["password"]:
        client.username_pw_set(config["username"], config["password"])
    
    # Set up callbacks
    client.on_connect = _create_on_connect_handler(subscribe_topics)
    client.on_message = _create_on_message_handler(camera_names, cmd_queues)
    
    # Connect to MQTT broker
    try:
        client.connect(config["host"], config["port"], keepalive=60)
        client.loop_start()
        log.info("MQTT subscriber connected to %s:%s", config["host"], config["port"])
    except Exception as e:
        log.error(
            "Failed to connect to MQTT broker at %s:%s: %s",
            config["host"], config["port"], e
        )
        return
    
    # Run until stop event is set
    try:
        while not stop_event.wait(0.5):
            pass
    finally:
        log.info("Shutting down MQTT subscriber...")
        try:
            client.loop_stop()
            client.disconnect()
        except Exception as e:
            log.warning("Error during MQTT disconnect: %s", e)


__all__ = ["mqtt_subscriber_worker"]
