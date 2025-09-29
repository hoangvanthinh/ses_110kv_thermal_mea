import json
import os
from typing import Dict, Any
from utils.types import AppConfig


DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> AppConfig:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if "pollers" not in config:
        config["pollers"] = [
            {
                "name": "default",
                "url": config.get("url"),
                "username": config.get("username"),
                "password": config.get("password"),
                "interval_seconds": int(config.get("interval_seconds", 10)),
            }
        ]

    config.setdefault(
        "mqtt",
        {
            "enabled": False,
            "host": "localhost",
            "port": 1883,
            "topic": "camera/areaTemperature",
            "username": "",
            "password": "",
        },
    )

    return config  # type: ignore[return-value]


__all__ = ["load_config", "DEFAULT_CONFIG_PATH"]


