"""Polite HTTP client: browser-like headers, retries with backoff, per-host rate limiting."""

from __future__ import annotations

import logging
import random
import threading
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


class RobotsDisallowed(Exception):
    pass


class HttpClient:
    def __init__(self, min_delay: float = 1.0, retries: int = 3, timeout: float = 20.0,
                 respect_robots: bool = False, proxy: str | None = None):
        self.min_delay = min_delay
        self.retries = retries
        self.respect_robots = respect_robots
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self._robots: dict[str, RobotFileParser | None] = {}
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            proxy=proxy,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/json,application/xhtml+xml,*/*;q=0.8",
            },
        )

    def _throttle(self, host: str) -> None:
        with self._lock:
            wait = self._last.get(host, 0) + self.min_delay - time.monotonic()
            self._last[host] = time.monotonic() + max(wait, 0)
        if wait > 0:
            time.sleep(wait + random.uniform(0, 0.3))

    def _allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = RobotFileParser()
            try:
                r = self.client.get(f"{base}/robots.txt")
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
                self._robots[base] = rp
            except httpx.HTTPError:
                self._robots[base] = None
        rp = self._robots[base]
        return rp is None or rp.can_fetch(USER_AGENT, url)

    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
        if not self._allowed(url):
            raise RobotsDisallowed(url)
        host = urlparse(url).netloc
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            self._throttle(host)
            try:
                r = self.client.get(url, params=params, headers=headers)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                return r
            except httpx.HTTPError as e:
                last_exc = e
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status and status < 500 and status != 429:
                    break  # 4xx other than 429 won't improve with retries
                backoff = 2 ** attempt + random.random()
                log.debug("GET %s failed (%s), retry in %.1fs", url, e, backoff)
                time.sleep(backoff)
        assert last_exc is not None
        raise last_exc

    def get_text(self, url: str, **kw) -> str:
        return self.get(url, **kw).text

    def get_json(self, url: str, **kw):
        return self.get(url, **kw).json()

    def close(self) -> None:
        self.client.close()
