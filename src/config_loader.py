import json
import os
import re
from typing import Dict, Any, List
from utils.types import AppConfig


DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _substitute_variables(obj: Any, variables: Dict[str, str]) -> Any:
    """
    Recursively substitute ${variable} in strings with actual values.
    
    Args:
        obj: Object to process (dict, list, str, or other)
        variables: Dictionary of variable name -> value
        
    Returns:
        Object with variables substituted
    """
    if isinstance(obj, dict):
        return {k: _substitute_variables(v, variables) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_variables(item, variables) for item in obj]
    elif isinstance(obj, str):
        # Replace ${variable_name} with actual value
        def replacer(match):
            var_name = match.group(1)
            return variables.get(var_name, match.group(0))  # Keep original if not found
        return re.sub(r'\$\{([^}]+)\}', replacer, obj)
    else:
        return obj


def _build_urls_from_templates(camera: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build URLs from templates for preset_thermals configuration.
    
    Converts new compact format (preset_id, area_id) to full URLs using url_templates.
    Also handles legacy format (url_presetID, url_areaTemperature) for backward compatibility.
    
    Args:
        camera: Camera configuration dictionary
        
    Returns:
        Camera configuration with URLs built from templates
    """
    # Get templates from camera (old format) - will be overridden by global templates if provided
    url_templates = camera.get("url_templates", {})
    
    # If no url_templates, return as-is (legacy format)
    if not url_templates:
        return camera
    
    # Build common URLs from templates
    camera_ip = camera.get("camera_ip", "")
    
    if url_templates.get("snapshot"):
        camera["url_snapshot"] = url_templates["snapshot"].replace("${camera_ip}", camera_ip)
    
    if url_templates.get("ptz_base"):
        camera["url_ptz_base"] = url_templates["ptz_base"].replace("${camera_ip}", camera_ip)
    
    if url_templates.get("rtsp"):
        camera["url_get_rtsp_url"] = url_templates["rtsp"].replace("${camera_ip}", camera_ip)
    
    # Process preset_thermals
    preset_thermals = camera.get("preset_thermals", [])
    for preset in preset_thermals:
        # Build preset URL if preset_id exists and url_presetID doesn't
        if "preset_id" in preset and "url_presetID" not in preset:
            preset_template = url_templates.get("preset", "")
            if preset_template:
                preset_url = preset_template.replace("${camera_ip}", camera_ip)
                preset_url = preset_url.replace("${preset_id}", str(preset["preset_id"]))
                preset["url_presetID"] = preset_url
        
        # Build node URLs
        nodes = preset.get("nodes", [])
        for node in nodes:
            # Build area temperature URL if area_id exists and url_areaTemperature doesn't
            if "area_id" in node and "url_areaTemperature" not in node:
                area_template = url_templates.get("area_temperature", "")
                if area_template:
                    area_url = area_template.replace("${camera_ip}", camera_ip)
                    area_url = area_url.replace("${area_id}", str(node["area_id"]))
                    node["url_areaTemperature"] = area_url
    
    return camera


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> AppConfig:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if "cameras" not in config:
        config["cameras"] = [
            {
                "camera_sid": "default",
                "url": config.get("url"),
                "username": config.get("username"),
                "password": config.get("password"),
                "interval_seconds": int(config.get("interval_seconds", 10)),
            }
        ]

    # Get global settings from root level (if exists)
    global_url_templates = config.get("url_templates", {})
    global_img_server_host = config.get("img_server_host", "")
    
    # Normalize cameras: ensure each has a cameras list
    normalized_cameras: List[Dict[str, Any]] = []
    for p in config.get("cameras", []) or []:
        p = dict(p)
        
        # Inject global url_templates if camera doesn't have its own
        if global_url_templates and "url_templates" not in p:
            p["url_templates"] = global_url_templates
        
        # Inject global img_server_host if camera doesn't have its own
        if global_img_server_host and "img_server_host" not in p:
            p["img_server_host"] = global_img_server_host
        
        # Build variables dictionary for this camera
        variables = {}
        for key, value in p.items():
            if isinstance(value, str) and not value.startswith("http"):
                # Potential variable (e.g., cameara_ip, camera_ip)
                variables[key] = value
        
        # Build URLs from templates (new compact format)
        p = _build_urls_from_templates(p)
        
        # Substitute variables in all URLs
        p = _substitute_variables(p, variables)
        
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
