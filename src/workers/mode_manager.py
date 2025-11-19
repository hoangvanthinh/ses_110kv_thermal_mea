"""Camera mode manager for Auto/Manual control."""
import threading
from enum import Enum
from typing import Dict, Optional
from datetime import datetime, timedelta

from utils.logging import get_logger


log = get_logger("workers.mode_manager")


class CameraMode(Enum):
    """Camera operation modes."""
    AUTO = "auto"
    MANUAL = "manual"


class ModeManager:
    """
    Manages operation mode (Auto/Manual) for each camera.
    
    - AUTO mode: Thermal poller automatically invokes PTZ presets
    - MANUAL mode: PTZ presets are skipped, user has full manual control
    
    Features:
    - Thread-safe mode switching
    - Auto-revert to AUTO after timeout
    - Per-camera mode tracking
    """
    
    def __init__(self, default_manual_timeout: int = 300):
        """
        Initialize mode manager.
        
        Args:
            default_manual_timeout: Default timeout in seconds for manual mode (default: 300s = 5min)
        """
        self._modes: Dict[str, CameraMode] = {}
        self._manual_timers: Dict[str, datetime] = {}
        self._lock = threading.Lock()
        self._default_manual_timeout = default_manual_timeout
        
        log.info("Mode Manager initialized with default manual timeout: %ds", default_manual_timeout)
    
    def get_mode(self, camera_name: str) -> CameraMode:
        """
        Get current mode of camera.
        
        Args:
            camera_name: Name of camera
            
        Returns:
            Current camera mode (default: AUTO)
        """
        with self._lock:
            return self._modes.get(camera_name, CameraMode.AUTO)
    
    def set_mode(
        self, 
        camera_name: str, 
        mode: CameraMode, 
        duration_seconds: Optional[int] = None
    ) -> None:
        """
        Set operation mode for camera.
        
        Args:
            camera_name: Name of camera
            mode: CameraMode.AUTO or CameraMode.MANUAL
            duration_seconds: If MANUAL mode, auto-revert to AUTO after this duration.
                            If None and mode is MANUAL, use default timeout.
                            If 0, MANUAL mode is permanent until explicitly changed.
        """
        with self._lock:
            old_mode = self._modes.get(camera_name, CameraMode.AUTO)
            self._modes[camera_name] = mode
            
            if mode == CameraMode.MANUAL:
                # Set timeout for auto-revert
                if duration_seconds is None:
                    duration_seconds = self._default_manual_timeout
                
                if duration_seconds > 0:
                    expire_time = datetime.now() + timedelta(seconds=duration_seconds)
                    self._manual_timers[camera_name] = expire_time
                    log.info(
                        "[%s] Mode changed: %s → %s (auto-revert in %ds at %s)",
                        camera_name, old_mode.value, mode.value, duration_seconds,
                        expire_time.strftime("%H:%M:%S")
                    )
                else:
                    # Permanent manual mode
                    if camera_name in self._manual_timers:
                        del self._manual_timers[camera_name]
                    log.info(
                        "[%s] Mode changed: %s → %s (permanent)",
                        camera_name, old_mode.value, mode.value
                    )
            else:
                # AUTO mode - clear any timers
                if camera_name in self._manual_timers:
                    del self._manual_timers[camera_name]
                log.info(
                    "[%s] Mode changed: %s → %s",
                    camera_name, old_mode.value, mode.value
                )
    
    def check_and_revert_manual_timeouts(self) -> None:
        """
        Check all cameras and auto-revert to AUTO if manual timeout expired.
        
        This should be called periodically (e.g., every 1-5 seconds).
        """
        with self._lock:
            now = datetime.now()
            expired_cameras = []
            
            for camera, expire_time in list(self._manual_timers.items()):
                if now >= expire_time:
                    self._modes[camera] = CameraMode.AUTO
                    expired_cameras.append(camera)
            
            # Clean up expired timers
            for camera in expired_cameras:
                del self._manual_timers[camera]
                log.info("[%s] Auto-reverted to AUTO mode (manual timeout expired)", camera)
    
    def can_invoke_preset(self, camera_name: str) -> bool:
        """
        Check if thermal poller can invoke PTZ presets.
        
        Args:
            camera_name: Name of camera
            
        Returns:
            True if in AUTO mode, False if in MANUAL mode
        """
        return self.get_mode(camera_name) == CameraMode.AUTO
    
    def get_mode_info(self, camera_name: str) -> Dict[str, any]:
        """
        Get detailed mode information for camera.
        
        Args:
            camera_name: Name of camera
            
        Returns:
            Dictionary with mode, expires_at (if applicable)
        """
        with self._lock:
            mode = self._modes.get(camera_name, CameraMode.AUTO)
            info = {
                "camera": camera_name,
                "mode": mode.value,
            }
            
            if camera_name in self._manual_timers:
                expire_time = self._manual_timers[camera_name]
                info["expires_at"] = expire_time.isoformat(timespec="seconds")
                info["remaining_seconds"] = int((expire_time - datetime.now()).total_seconds())
            
            return info
    
    def extend_manual_mode(self, camera_name: str, additional_seconds: int) -> bool:
        """
        Extend manual mode duration.
        
        Args:
            camera_name: Name of camera
            additional_seconds: Seconds to add to current timeout
            
        Returns:
            True if extended, False if not in manual mode
        """
        with self._lock:
            if self._modes.get(camera_name) != CameraMode.MANUAL:
                return False
            
            if camera_name in self._manual_timers:
                self._manual_timers[camera_name] += timedelta(seconds=additional_seconds)
                log.info(
                    "[%s] Manual mode extended by %ds (new expire: %s)",
                    camera_name, additional_seconds,
                    self._manual_timers[camera_name].strftime("%H:%M:%S")
                )
            else:
                # Was permanent, now set a timeout
                self._manual_timers[camera_name] = datetime.now() + timedelta(seconds=additional_seconds)
                log.info(
                    "[%s] Manual mode timeout set to %ds",
                    camera_name, additional_seconds
                )
            
            return True


__all__ = ["ModeManager", "CameraMode"]

