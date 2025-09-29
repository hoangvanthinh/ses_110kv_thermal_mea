import threading
import time
import base64
import json
import os
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def fetch_text(
    url: str,
    timeout_seconds: float = 5.0,
    username: str | None = None,
    password: str | None = None,
) -> str:
    headers: dict[str, str] = {"User-Agent": "Mozilla/5.0"}
    if username and password:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout_seconds) as response:
        raw_bytes = response.read()
        return raw_bytes.decode("utf-8", errors="replace")


def poll_area_temperature(
    url: str,
    interval_seconds: int = 10,
    stop_event: threading.Event | None = None,
    username: str | None = None,
    password: str | None = None,
) -> None:
    if stop_event is None:
        stop_event = threading.Event()

    while not stop_event.is_set():
        try:
            data = fetch_text(url, username=username, password=password)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] areaTemperature response:\n{data}\n", flush=True)
        except HTTPError as e:
            print(f"HTTP error: {e.code} {e.reason}", flush=True)
        except URLError as e:
            print(f"URL error: {e.reason}", flush=True)
        except Exception as e:
            print(f"Unexpected error: {e}", flush=True)

        # Sleep with stop support
        if stop_event.wait(interval_seconds):
            break


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    stop_event = threading.Event()
    config = load_config()
    url = config.get("url")
    interval_seconds = int(config.get("interval_seconds", 10))
    username = config.get("username") or None
    password = config.get("password") or None

    worker = threading.Thread(
        target=poll_area_temperature,
        args=(url, interval_seconds, stop_event, username, password),
        daemon=True,
    )
    worker.start()

    print(f"Started polling every {interval_seconds}s. Press Ctrl+C to stop.")

    try:
        while worker.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
        stop_event.set()
        worker.join(timeout=5)
        print("Stopped.")


if __name__ == "__main__":
    main()
