import threading
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


AREA_TEMPERATURE_URL = (
    "http://admin:thinh0702@192.168.1.171/cgi-bin/param.cgi?action=get&type=areaTemperature&cameraID=1&areaID=1"
)


def fetch_text(url: str, timeout_seconds: float = 5.0) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        raw_bytes = response.read()
        return raw_bytes.decode("utf-8", errors="replace")


def poll_area_temperature(
    url: str,
    interval_seconds: int = 10,
    stop_event: threading.Event | None = None,
) -> None:
    if stop_event is None:
        stop_event = threading.Event()

    while not stop_event.is_set():
        try:
            data = fetch_text(url)
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


def main() -> None:
    stop_event = threading.Event()

    worker = threading.Thread(
        target=poll_area_temperature,
        args=(AREA_TEMPERATURE_URL, 10, stop_event),
        daemon=True,
    )
    worker.start()

    print("Started polling every 10s. Press Ctrl+C to stop.")

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
