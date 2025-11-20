"""Worker lifecycle management for thermal camera monitoring system."""
import threading
import queue
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from config_loader import load_config
from utils.logging import get_logger
from workers.read_thermal_poller import poller_worker
from workers.mqtt_publisher import mqtt_publisher_worker
from workers.mqtt_subscriber import mqtt_subscriber_worker
from workers.rtsp_fetcher import rtsp_fetcher_worker
from workers.ptz_controller import ptz_controller_worker
from workers.mode_manager import ModeManager


log = get_logger("worker_manager")


@dataclass
class CommandQueues:
    """Container for command queues."""
    rtsp: "queue.Queue[str]" = field(default_factory=lambda: queue.Queue(maxsize=50))
    ptz: "queue.Queue[str]" = field(default_factory=lambda: queue.Queue(maxsize=50))
    thermal: "queue.Queue[str]" = field(default_factory=lambda: queue.Queue(maxsize=50))
    
    def as_dict(self) -> Dict[str, "queue.Queue[str]"]:
        """Return command queues as dictionary."""
        return {
            "rtsp": self.rtsp,
            "ptz": self.ptz,
            "thermal": self.thermal,
        }


@dataclass
class WorkerThreads:
    """Container for all worker threads."""
    camera_threads: List[threading.Thread] = field(default_factory=list)
    mqtt_publisher: Optional[threading.Thread] = None
    mqtt_subscriber: Optional[threading.Thread] = None
    rtsp_fetcher: Optional[threading.Thread] = None
    ptz_controllers: List[threading.Thread] = field(default_factory=list)
    mode_timeout_checker: Optional[threading.Thread] = None
    
    def all_threads(self) -> List[threading.Thread]:
        """Return all non-None threads as a flat list."""
        threads = self.camera_threads + self.ptz_controllers
        if self.mqtt_publisher:
            threads.append(self.mqtt_publisher)
        if self.mqtt_subscriber:
            threads.append(self.mqtt_subscriber)
        if self.rtsp_fetcher:
            threads.append(self.rtsp_fetcher)
        if self.mode_timeout_checker:
            threads.append(self.mode_timeout_checker)
        return threads


class WorkerManager:
    """Manages the lifecycle of all worker threads."""
    
    def __init__(self):
        """Initialize worker manager."""
        self.config = load_config()
        self.stop_event = threading.Event()
        self.out_queue: "queue.Queue[dict]" = queue.Queue(maxsize=100)
        self.cmd_queues = CommandQueues()
        self.threads = WorkerThreads()
        self.mode_manager = ModeManager(default_manual_timeout=300)  # 5 minutes default
        
    def start_camera_pollers(self) -> List[threading.Thread]:
        """Start thermal camera polling threads."""
        threads: List[threading.Thread] = []
        
        for idx, camera_cfg in enumerate(self.config.get("cameras", []), start=1):
            camera_name = str(camera_cfg.get("camera_sid") or f"camera_{idx}")
            
            thread = threading.Thread(
                target=poller_worker,
                args=(
                    camera_name,
                    int(camera_cfg.get("interval_seconds", 30)),
                    self.out_queue,
                    self.stop_event,
                    camera_cfg.get("preset_thermals"),
                    camera_cfg.get("username"),
                    camera_cfg.get("password"),
                    float(camera_cfg.get("timeout_seconds", 10.0)),
                    float(camera_cfg.get("settle_seconds", 2.0)),
                    camera_cfg.get("url_snapshot"),
                    camera_cfg.get("img_server_host"),
                    self.mode_manager,  # Pass mode_manager
                ),
                daemon=True,
                name=f"camera:{camera_name}",
            )
            thread.start()
            threads.append(thread)
            
        log.info("Started %d camera poller(s)", len(threads))
        return threads
    
    def start_mqtt_publisher(self) -> Optional[threading.Thread]:
        """Start MQTT publisher thread."""
        mqtt_cfg = self.config.get("mqtt", {}) or {}
        
        thread = threading.Thread(
            target=mqtt_publisher_worker,
            args=(mqtt_cfg, self.out_queue, self.stop_event),
            daemon=True,
            name="mqtt-publisher",
        )
        thread.start()
        
        log.info("Started MQTT publisher")
        return thread
    
    def start_mqtt_subscriber(self) -> Optional[threading.Thread]:
        """Start MQTT subscriber thread if enabled."""
        mqtt_cfg = self.config.get("mqtt", {}) or {}
        
        if not mqtt_cfg.get("enabled", False):
            log.info("MQTT subscriber disabled")
            return None
        
        camera_names = [
            p.get("camera_sid") 
            for p in self.config.get("cameras", []) 
            if p.get("camera_sid")
        ]
        
        thread = threading.Thread(
            target=mqtt_subscriber_worker,
            args=(mqtt_cfg, self.stop_event, self.cmd_queues.as_dict(), camera_names, self.mode_manager, self.out_queue),
            daemon=True,
            name="mqtt-subscriber",
        )
        thread.start()
        
        log.info("Started MQTT subscriber")
        return thread
    
    def start_rtsp_fetcher(self) -> Optional[threading.Thread]:
        """Start RTSP URL fetcher thread."""
        thread = threading.Thread(
            target=rtsp_fetcher_worker,
            args=(self.out_queue, self.cmd_queues.rtsp, self.stop_event),
            daemon=True,
            name="rtsp-fetcher",
        )
        thread.start()
        
        log.info("Started RTSP fetcher")
        return thread
    
    def start_ptz_controllers(self) -> List[threading.Thread]:
        """Start PTZ controller threads for each camera."""
        threads: List[threading.Thread] = []
        
        for camera_cfg in self.config.get("cameras", []):
            camera_name = camera_cfg.get("camera_sid")
            if not camera_name:
                continue
                
            thread = threading.Thread(
                target=ptz_controller_worker,
                args=(
                    self.cmd_queues.ptz,
                    self.out_queue,
                    self.stop_event,
                    camera_name,
                    camera_cfg,
                    self.mode_manager,  # Pass mode_manager
                ),
                daemon=True,
                name=f"ptz-controller:{camera_name}",
            )
            thread.start()
            threads.append(thread)
            
        log.info("Started %d PTZ controller(s)", len(threads))
        return threads
    
    def start_mode_timeout_checker(self) -> Optional[threading.Thread]:
        """Start mode timeout checker thread."""
        def timeout_checker_worker():
            """Periodically check and revert manual mode timeouts."""
            log.info("Mode timeout checker started")
            while not self.stop_event.wait(2.0):  # Check every 2 seconds
                try:
                    self.mode_manager.check_and_revert_manual_timeouts()
                except Exception as e:
                    log.error("Error in mode timeout checker: %s", e)
            log.info("Mode timeout checker stopped")
        
        thread = threading.Thread(
            target=timeout_checker_worker,
            daemon=True,
            name="mode-timeout-checker",
        )
        thread.start()
        
        log.info("Started mode timeout checker")
        return thread
    
    def start_all(self) -> Tuple[WorkerThreads, "queue.Queue[dict]"]:
        """Start all worker threads."""
        log.info("Starting all workers...")
        
        self.threads.camera_threads = self.start_camera_pollers()
        self.threads.mqtt_publisher = self.start_mqtt_publisher()
        self.threads.mqtt_subscriber = self.start_mqtt_subscriber()
        self.threads.rtsp_fetcher = self.start_rtsp_fetcher()
        self.threads.ptz_controllers = self.start_ptz_controllers()
        self.threads.mode_timeout_checker = self.start_mode_timeout_checker()
        
        mqtt_status = "enabled" if self.threads.mqtt_subscriber else "disabled"
        log.info(
            "All workers started: %d camera(s), %d PTZ controller(s), MQTT=%s",
            len(self.threads.camera_threads),
            len(self.threads.ptz_controllers),
            mqtt_status
        )
        
        return self.threads, self.out_queue
    
    def stop_all(self) -> None:
        """Stop all worker threads gracefully."""
        log.info("Stopping all workers...")
        
        # Signal stop to all threads
        self.stop_event.set()
        
        # Send sentinel to publisher queue
        try:
            self.out_queue.put_nowait(None)
        except queue.Full:
            pass
        
        # Wait for all threads to finish
        join_timeout = 5.0
        for thread in self.threads.all_threads():
            if thread and thread.is_alive():
                thread.join(timeout=join_timeout)
                if thread.is_alive():
                    log.warning("Thread %s did not stop within timeout", thread.name)
        
        log.info("All workers stopped")


__all__ = ["WorkerManager", "CommandQueues", "WorkerThreads"]

