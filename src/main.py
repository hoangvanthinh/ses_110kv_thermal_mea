import threading
import queue
from typing import List, Optional, Tuple
from config_loader import load_config
from utils.logging import get_logger
from workers.read_thermal_poller import poller_worker
from workers.mqtt_publisher import mqtt_publisher_worker
from workers.mqtt_subscriber import mqtt_subscriber_worker
from workers.rtsp_fetcher import rtsp_fetcher_worker
from workers.ptz_controller import ptz_controller_worker
from nicegui import ui, app
from ui_app import register_pages    # 👈 import UI từ file riêng

log = get_logger("main")


def start_workers(stop_event: threading.Event) -> Tuple[
    List[threading.Thread], threading.Thread, Optional[threading.Thread], threading.Thread, List[threading.Thread], "queue.Queue[dict]"
]:
    """Khởi động các worker (poller, MQTT, RTSP fetcher, PTZ controller)."""
    config = load_config()
    out_queue: "queue.Queue[dict]" = queue.Queue(maxsize=100)
    
    # Create separate command queues for different consumers
    rtsp_cmd_queue: "queue.Queue[str]" = queue.Queue(maxsize=50)
    ptz_cmd_queue: "queue.Queue[str]" = queue.Queue(maxsize=50)
    thermal_cmd_queue: "queue.Queue[str]" = queue.Queue(maxsize=50)
    
    cmd_queues = {
        "rtsp": rtsp_cmd_queue,
        "ptz": ptz_cmd_queue,
        "thermal": thermal_cmd_queue,
    }

    # --- Start poller threads ---
    camera_threads: List[threading.Thread] = []
    for idx, p in enumerate(config.get("cameras", []), start=1):
        name = str(p.get("name") or f"camera_{idx}")
        t = threading.Thread(
            target=poller_worker,
            args=(
                name,
                int(p.get("interval_seconds", 30)),
                out_queue,
                stop_event,
                p.get("node_thermals"),
                p.get("username"),
                p.get("password"),
                float(p.get("timeout_seconds", 10.0)),
                float(p.get("settle_seconds", 2.0)),
            ),
            daemon=True,
            name=f"camera:{name}",
        )
        t.start()
        camera_threads.append(t)

    # --- Start MQTT publisher ---
    mqtt_cfg = config.get("mqtt", {}) or {}
    mqtt_thread = threading.Thread(
        target=mqtt_publisher_worker,
        args=(mqtt_cfg, out_queue, stop_event),
        daemon=True,
        name="mqtt-publisher",
    )
    mqtt_thread.start()

    # --- Start MQTT subscriber (nếu enabled) ---
    mqtt_sub_thread: Optional[threading.Thread] = None
    if mqtt_cfg.get("enabled", False):
        mqtt_sub_thread = threading.Thread(
            target=mqtt_subscriber_worker,
            args=(mqtt_cfg, stop_event, cmd_queues, [p.get("name") for p in config.get("cameras", []) if p.get("name")]),
            daemon=True,
            name="mqtt-subscriber",
        )
        mqtt_sub_thread.start()

    # --- Start RTSP fetchers ---
    rtsp_threads = threading.Thread(
                target=rtsp_fetcher_worker,
                args=(out_queue, rtsp_cmd_queue, stop_event),
                daemon=True,
                name="rtsp-fetcher",
            )
    rtsp_threads.start()
         
    
    # --- Start PTZ controllers ---
    ptz_threads: List[threading.Thread] = []
    for p in config.get("cameras", []):
        name = p.get("name")
        if name:
            t = threading.Thread(
                target=ptz_controller_worker,
                args=(ptz_cmd_queue, out_queue, stop_event, name, p),
                daemon=True,
                name=f"ptz-controller:{name}",
            )
            t.start()
            ptz_threads.append(t)

    log.info("Started %d poller(s), 1 RTSP fetcher, %d PTZ controller(s), mqtt=%s", 
             len(camera_threads), len(ptz_threads), mqtt_cfg.get("enabled", False))
    return camera_threads, mqtt_thread, mqtt_sub_thread, rtsp_threads, ptz_threads, out_queue


def stop_workers(
    camera_threads: List[threading.Thread],
    mqtt_thread: Optional[threading.Thread],
    mqtt_sub_thread: Optional[threading.Thread],
    rtsp_thread: threading.Thread,
    ptz_threads: List[threading.Thread],
    out_queue: "queue.Queue[dict]",
    stop_event: threading.Event,
) -> None:
    """Dừng toàn bộ worker."""
    log.info("Stopping workers...")
    stop_event.set()
    try:
        out_queue.put_nowait(None)  # sentinel cho publisher
    except Exception:
        pass

    for t in camera_threads:
        t.join(timeout=5)
    if mqtt_thread:
        mqtt_thread.join(timeout=5)
    if mqtt_sub_thread:
        mqtt_sub_thread.join(timeout=5)
    rtsp_thread.join(timeout=5)
    for t in ptz_threads:
        t.join(timeout=5)
    log.info("Stopped workers.")


def build_ui():
    """Tạo layout cho UI."""
    ui.label('Hello NiceGUI!')
    ui.button('BUTTON', on_click=lambda: ui.notify('button was pressed'))

    with ui.row():
        ui.button('demo', icon='history')
        ui.button(icon='thumb_up')
        with ui.button():
            ui.label('sub-elements')


def main():
    stop_event = threading.Event()
    # workers = start_workers(stop_event)
    camera_threads, mqtt_thread, mqtt_sub_thread, rtsp_thread, ptz_threads, out_queue = start_workers(
        stop_event)

    # UI
    # build_ui()
    # register_pages(out_queue)

    # Gắn hook shutdown
    @app.on_shutdown
    def _cleanup():
        # stop_workers(*workers, stop_event)
        stop_workers(camera_threads, mqtt_thread, mqtt_sub_thread,
                     rtsp_thread, ptz_threads, out_queue, stop_event)

    # Run app
    ui.run(port=8080, reload=False, storage_secret='super-secret-key')


if __name__ in {"__main__", "__mp_main__"}:
    main()
