"""
Ping Monitor Worker

Periodically pings camera IPs to check connectivity status.
"""

import threading
import time
import subprocess
import platform
from typing import Dict, Any
from queue import Queue

from utils.logging import get_logger

log = get_logger("ping_monitor")


def ping_camera(ip: str, timeout: int = 2) -> bool:
    """
    Ping a camera IP to check if it's reachable.
    
    Args:
        ip: Camera IP address
        timeout: Ping timeout in seconds
        
    Returns:
        True if ping successful, False otherwise
    """
    try:
        # Determine ping command based on OS
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        
        # Build ping command: ping -n 1 -w 2000 IP (Windows) or ping -c 1 -W 2 IP (Linux)
        command = ['ping', param, '1', timeout_param, str(timeout * 1000 if platform.system().lower() == 'windows' else timeout), ip]
        
        # Execute ping
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 1
        )
        
        return result.returncode == 0
    
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        log.error(f"Ping error for {ip}: {e}")
        return False


def ping_monitor_worker(
    camera_sid: str,
    camera_ip: str,
    interval_seconds: int,
    out_queue: Queue,
    stop_event: threading.Event
):
    """
    Worker thread that periodically pings a camera.
    
    Args:
        camera_sid: Camera identifier
        camera_ip: Camera IP address to ping
        interval_seconds: Ping interval in seconds
        out_queue: Queue for sending ping results
        stop_event: Event to signal worker shutdown
    """
    log.info(f"[{camera_sid}] Ping monitor started (interval: {interval_seconds}s)")
    
    while not stop_event.is_set():
        try:
            # Perform ping
            is_alive = ping_camera(camera_ip)
            
            # Send result to UI
            status_data = {
                'type': 'ping_status',
                'camera_sid': camera_sid,
                'camera_ip': camera_ip,
                'status': 'online' if is_alive else 'offline',
                'timestamp': time.time()
            }
            
            try:
                out_queue.put_nowait(status_data)
                log.info(f"[{camera_sid}] Ping status sent to UI: {status_data['status']}")
            except Exception as e:
                log.warning(f"[{camera_sid}] Output queue full, dropping ping status: {e}")
            
        except Exception as e:
            log.error(f"[{camera_sid}] Ping monitor error: {e}")
        
        # Wait for next interval (check stop_event periodically)
        for _ in range(interval_seconds):
            if stop_event.is_set():
                break
            time.sleep(1)
    
    log.info(f"[{camera_sid}] Ping monitor stopped")


__all__ = ["ping_monitor_worker"]

