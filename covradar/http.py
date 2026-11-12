"""Minimal HTTP client: retries, a real user agent, an on-disk cache."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional

USER_AGENT = (
    "coverage-radar/1.0 (+https://github.com/sadok-ayari/coverage-radar) "
    "python-urllib"
)


class FetchError(RuntimeError):
    pass


def _cache_file(cache_dir: Optional[str], url: str, method: str, body: Optional[bytes]) -> Optional[str]:
    if not cache_dir:
        return None
    digest = hashlib.sha256((method + url + (body or b"").decode("utf-8", "replace")).encode()).hexdigest()[:16]
    return os.path.join(cache_dir, digest + ".json")


def request(
    url: str,
    *,
    method: str = "GET",
    body: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    retries: int = 2,
    cache_dir: Optional[str] = None,
    offline: bool = False,
    backoff: float = 1.5,
) -> str:
    """Return the body as text. Cached when a cache directory is given."""
    cache_path = _cache_file(cache_dir, url, method, body)
    if offline:
        if cache_path and os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as handle:
                return json.load(handle)["body"]
        raise FetchError(f"offline and no cached response for {url}")

    all_headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip", "Accept": "*/*"}
    all_headers.update(headers or {})

    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            request_obj = urllib.request.Request(url, data=body, headers=all_headers, method=method)
            with urllib.request.urlopen(request_obj, timeout=timeout) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            text = raw.decode("utf-8", "replace")
            if cache_path:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as handle:
                    json.dump({"url": url, "body": text}, handle)
            return text
        except urllib.error.HTTPError as error:
            # Providers often explain themselves in the body; keep that text.
            detail = ""
            try:
                detail = error.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            last_error = FetchError(f"HTTP {error.code} for {url}. {detail}".strip())
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
        if attempt < retries:
            time.sleep(backoff * (attempt + 1))
    raise FetchError(f"{method} {url} failed after {retries + 1} attempts: {last_error}")


def with_query(url: str, params: Dict[str, str]) -> str:
    joiner = "&" if urllib.parse.urlparse(url).query else "?"
    return url + joiner + urllib.parse.urlencode(params)
