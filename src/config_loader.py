import json
import os
from typing import Dict, Any, List
from utils.types import AppConfig


DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> AppConfig:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if "cameras" not in config:
        config["cameras"] = [
            {
                "camera_name": "default",
                "url": config.get("url"),
                "username": config.get("username"),
                "password": config.get("password"),
                "interval_seconds": int(config.get("interval_seconds", 10)),
            }
        ]

    # Normalize cameras: ensure each has a cameras list
    normalized_cameras: List[Dict[str, Any]] = []
    for p in config.get("cameras", []) or []:
        p = dict(p)
        if "presets" not in p or not p.get("presets"):
            preset: Dict[str, Any] = {}
            if p.get("url_presetID") or p.get("url_areaTemperature"):
                if p.get("url_presetID"):
                    preset["url_presetID"] = p.get("url_presetID")
                if p.get("url_areaTemperature"):
                    preset["url_areaTemperature"] = p.get(
                        "url_areaTemperature")
            elif p.get("url"):
                preset["url_areaTemperature"] = p.get("url")
            if preset:
                if p.get("name"):
                    preset.setdefault("name", str(p.get("name")))
                p["presets"] = [preset]
            # Clean legacy keys to avoid ambiguity
            p.pop("url", None)
            p.pop("url_presetID", None)
            p.pop("url_areaTemperature", None)
        normalized_cameras.append(p)
    config["cameras"] = normalized_cameras

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
