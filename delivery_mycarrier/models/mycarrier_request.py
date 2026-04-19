"""Thin HTTP client for the MyCarrier Rating and Orders APIs.

This module is deliberately free of Odoo ORM dependencies so it can be
unit-tested in isolation and mocked via ``requests.Session``.
"""

import base64
import logging

import requests

_logger = logging.getLogger(__name__)


RATING_HOSTS = {
    "prod": "https://app-integration-prod-api.azurewebsites.net",
    "sandbox": "https://app-integration-prod-api.azurewebsites.net",
}
ORDER_HOSTS = {
    "prod": "https://order-public-api.api.mycarriertms.com",
    "sandbox": "https://order-public-api.api.mycarriertms.com",
}

DEFAULT_TIMEOUT = 30


class MyCarrierRequestError(Exception):
    """Raised when the MyCarrier API returns a non-success response or the
    transport fails. The message is user-safe (never contains credentials).
    """


class MyCarrierRequest:
    def __init__(self, email, api_key, environment="sandbox", timeout=DEFAULT_TIMEOUT):
        if not email or not api_key:
            raise MyCarrierRequestError("MyCarrier credentials are not configured.")
        self._email = email
        self._api_key = api_key
        self._environment = environment if environment in RATING_HOSTS else "sandbox"
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _basic_auth_header(self):
        token = base64.b64encode(
            f"{self._email}:{self._api_key}".encode("utf-8")
        ).decode("ascii")
        return f"Basic {token}"

    def rate(self, payload):
        url = f"{RATING_HOSTS[self._environment]}/feature/rating"
        return self._post(url, payload)

    def create_order(self, payload):
        url = f"{ORDER_HOSTS[self._environment]}/api/Orders"
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
