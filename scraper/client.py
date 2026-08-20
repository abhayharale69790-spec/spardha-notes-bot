"""Resilient HTTP Client with Tenacity Retries, User-Agent Rotation, and SSL Bypass."""

import asyncio
from collections import defaultdict
import logging
from pathlib import Path
import random
import time
from typing import Dict, Optional
from urllib.parse import urlparse

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ResilientHttpClient:
    """Production-grade asynchronous HTTP client for scraping government and exam portals."""

    def __init__(self, min_domain_interval_sec: float = 2.0) -> None:
        self.min_domain_interval_sec = min_domain_interval_sec
        self._last_domain_request: Dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()

    def _get_random_headers(self) -> Dict[str, str]:
        """Generate browser-like headers with rotating User-Agent."""
        ua = random.choice(settings.user_agents) if settings.user_agents else "Mozilla/5.0"
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "mr,en-US,en;q=0.9,hi;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _throttle_domain(self, url: str) -> None:
        """Enforce domain-specific polite rate limiting."""
        domain = urlparse(url).netloc
        if not domain:
            return

        async with self._lock:
            now = time.monotonic()
            last_req = self._last_domain_request[domain]
            elapsed = now - last_req
            if elapsed < self.min_domain_interval_sec:
                sleep_time = self.min_domain_interval_sec - elapsed
                await asyncio.sleep(sleep_time)
            self._last_domain_request[domain] = time.monotonic()

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _fetch_with_retry(self, url: str, timeout: float = 25.0, verify_ssl: bool = True) -> httpx.Response:
        """Internal worker with exponential backoff retries."""
        await self._throttle_domain(url)
        headers = self._get_random_headers()

        async with httpx.AsyncClient(
            verify=verify_ssl,
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            response = await client.get(url, headers=headers)
            # Raise error on 5xx server errors for retry triggering
            if response.status_code in (500, 502, 503, 504):
                response.raise_for_status()
            return response

    async def get_text(self, url: str, timeout: float = 12.0) -> str:
        """Fetch webpage HTML text safely with SSL fallback and fast timeout."""
        await self._throttle_domain(url)
        headers = self._get_random_headers()

        for verify_ssl in (True, False):
            try:
                async with httpx.AsyncClient(
                    verify=verify_ssl,
                    follow_redirects=True,
                    timeout=timeout,
                ) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        return resp.text
            except Exception as e:
                logger.debug(f"Fetch attempt (verify={verify_ssl}) for {url} failed: {e}")
                continue

        logger.warning(f"Could not fetch {url} after secure and fallback attempts.")
        return ""


    async def download_file(self, url: str, destination_path: Path, timeout: float = 60.0) -> bool:
        """Download remote PDF file to disk cache with SSL fallback."""
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            await self._throttle_domain(url)
            headers = self._get_random_headers()

            for verify in (True, False):
                try:
                    async with httpx.AsyncClient(verify=verify, follow_redirects=True, timeout=timeout) as client:
                        async with client.stream("GET", url, headers=headers) as response:
                            response.raise_for_status()
                            with open(destination_path, "wb") as f:
                                async for chunk in response.aiter_bytes(chunk_size=65536):
                                    f.write(chunk)
                    return True
                except (httpx.ConnectError, httpx.RequestError):
                    if verify:
                        continue  # Retry with verify=False
                    raise
            return False
        except Exception as e:
            logger.error(f"Failed to download file from {url} to {destination_path}: {e}")
            return False
