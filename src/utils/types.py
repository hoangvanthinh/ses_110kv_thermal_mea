from typing import TypedDict, Optional, List, Dict, Any


class PollerConfig(TypedDict, total=False):
    name: str
    url: str
    username: str
    password: str
    interval_seconds: int
    timeout_seconds: float


class MQTTConfig(TypedDict, total=False):
    enabled: bool
    host: str
    port: int
    topic: str
    username: str
    password: str


class AppConfig(TypedDict, total=False):
    pollers: List[PollerConfig]
    mqtt: MQTTConfig


class QueueItem(TypedDict):
    poller: str
    url: str
    timestamp: str
    data: str


__all__ = [
    "PollerConfig",
    "MQTTConfig",
    "AppConfig",
    "QueueItem",
]


