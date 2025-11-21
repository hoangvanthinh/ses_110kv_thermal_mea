"""
Camera Ping Worker - Monitor camera connectivity status.

This worker pings cameras periodically to check if they are online.
Publishes camera status to output queue for UI display.
"""

import logging
import platform
import subprocess
import threading
from queue import Queue
from typing import Optional

log = logging.getLogger(__name__)


def ping_host(host: str, timeout: int = 2) -> bool:
    """
    Ping a host to check if it's reachable.
    
    Args:
        host: IP address or hostname to ping
        timeout: Timeout in seconds
        
    Returns:
        True if host is reachable, False otherwise
    """
    try:
        # Determine ping command based on OS
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        
        # Build ping command: ping -c 1 -W timeout host
        command = ['ping', param, '1', timeout_param, str(timeout * 1000 if platform.system().lower() == 'windows' else timeout), host]
        
        # Execute ping
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 1
        )
        
        return result.returncode == 0
    
    except subprocess.TimeoutExpired:
        log.warning(f"Ping timeout for {host}")
        return False
    except Exception as e:
        log.error(f"Ping error for {host}: {e}")
        return False


def camera_ping_worker(
    camera_name: str,
    camera_ip: str,
    interval_seconds: int,
    out_queue: Queue,
    stop_event: threading.Event,
    timeout_seconds: int = 2
):
    """
    Worker that continuously pings a camera to monitor connectivity.
    
    Args:
        camera_name: Name/ID of camera for identification
        camera_ip: IP address to ping
        interval_seconds: Seconds between ping attempts
        out_queue: Queue to send status updates
        stop_event: Event to signal worker to stop
        timeout_seconds: Ping timeout in seconds
    """
    log.info(f"[{camera_name}] Camera ping worker started - monitoring {camera_ip} every {interval_seconds}s")
    
    while not stop_event.is_set():
        try:
            # Ping the camera
            is_online = ping_host(camera_ip, timeout=timeout_seconds)
            
            # Prepare status message
            status_msg = {
                'type': 'camera_status',
                'camera': camera_name,
                'camera_ip': camera_ip,
                'status': 'online' if is_online else 'offline',
                'timestamp': None  # Will be added by caller if needed
            }
            
            # Send to output queue (non-blocking)
            try:
                out_queue.put_nowait(status_msg)
                log.debug(f"[{camera_name}] Status: {'online' if is_online else 'offline'}")
            except:
                log.warning(f"[{camera_name}] Output queue full, dropping status update")
            
            # Wait for next interval or stop event
            if stop_event.wait(interval_seconds):
                break
        
        except Exception as e:
            log.error(f"[{camera_name}] Ping worker error: {e}")
            # Wait a bit before retry
            if stop_event.wait(5):
                break
    
    log.info(f"[{camera_name}] Camera ping worker stopped")


__all__ = ['camera_ping_worker', 'ping_host']

