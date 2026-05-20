"""Thin HTTP client for the MyCarrier Rating API.

Rating uses no HTTP-level auth — the admin email travels inside the JSON
body as ``customerEmail``. Booking (out of scope) is the only flow that
requires an API key.
"""

import logging

import requests

_logger = logging.getLogger(__name__)


RATING_HOSTS = {
    "prod": "https://app-integration-prod-api.azurewebsites.net",
    "sandbox": "https://app-integration-preprod-api.azurewebsites.net",
}

DEFAULT_TIMEOUT = 30


class MyCarrierRequestError(Exception):
    """Raised when the MyCarrier API returns a non-success response or the
    transport fails. The message is user-safe (never contains credentials).
    """


class MyCarrierRequest:
    def __init__(self, environment="sandbox", timeout=DEFAULT_TIMEOUT):
        self._environment = environment if environment in RATING_HOSTS else "sandbox"
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def rate(self, payload):
        url = f"{RATING_HOSTS[self._environment]}/feature/rating"
        return self._post(url, payload)

    def _post(self, url, payload):
        try:
            response = self._session.post(url, json=payload, timeout=self._timeout)
        except requests.RequestException as exc:
            _logger.warning("MyCarrier transport error for %s: %s", url, exc)
            raise MyCarrierRequestError(
                "Could not reach MyCarrier. Check connectivity and retry."
            ) from exc
        if response.status_code >= 400:
            _logger.warning(
                "MyCarrier %s returned HTTP %s: %s",
                url,
                response.status_code,
                response.text[:500],
            )
            raise MyCarrierRequestError(
                f"MyCarrier API error ({response.status_code}): "
                f"{response.text[:500] or 'no body'}"
            )
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}
