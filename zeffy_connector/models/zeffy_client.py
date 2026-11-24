# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Read-only client for the Zeffy public API (https://api.zeffy.com/api/docs).

Only ``GET`` requests are ever issued.
"""

import logging
import time

import requests

_logger = logging.getLogger(__name__)

BASE_URL = "https://api.zeffy.com/api/v1"
PAGE_SIZE = 100
MAX_RATE_LIMIT_RETRIES = 5
DEFAULT_RETRY_AFTER = 60.0


class ZeffyError(Exception):
    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


class ZeffyAuthError(ZeffyError):
    pass


class ZeffyClient:
    def __init__(self, api_key, timeout=30, sleep=time.sleep):
        self.api_key = api_key
        self.timeout = timeout
        self._sleep = sleep

    def _request(self, path, params=None):
        return requests.get(
            f"{BASE_URL}/{path}",
            params=params,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
            timeout=self.timeout,
        )

    def get(self, path, params=None):
        for _attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            try:
                response = self._request(path, params)
            except requests.RequestException as exc:
                raise ZeffyError(f"Could not reach Zeffy: {exc}") from exc
            if response.status_code != 429:
                break
            try:
                delay = float(response.headers.get("Retry-After"))
            except (TypeError, ValueError):
                delay = DEFAULT_RETRY_AFTER
            _logger.info("Zeffy rate limit reached, retrying in %ss", delay)
            self._sleep(delay)
        else:
            raise ZeffyError("Zeffy rate limit still exceeded after retries.", 429)
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.status_code >= 400:
            error = (payload.get("error") or {}) if isinstance(payload, dict) else {}
            message = error.get("message") or f"HTTP {response.status_code}"
            cls = ZeffyAuthError if response.status_code == 401 else ZeffyError
            raise cls(message, response.status_code, error.get("code"))
        return payload

    def iter_list(self, resource, params=None):
        """Yield every object of a list endpoint, following the cursor."""
        params = dict(params or {}, limit=PAGE_SIZE)
        while True:
            page = self.get(resource, params)
            yield from page.get("data") or []
            if not page.get("has_more") or not page.get("next_cursor"):
                return
            params["starting_after"] = page["next_cursor"]

    def test_connection(self):
        self.get("campaigns", {"limit": 1})
