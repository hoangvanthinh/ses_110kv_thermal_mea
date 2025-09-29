import base64
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


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


__all__ = ["fetch_text", "HTTPError", "URLError"]


