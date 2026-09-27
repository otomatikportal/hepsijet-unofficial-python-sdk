"""Getting and caching the auth token. HepsiJET tokens expire after 60 minutes."""

import base64
import time
from collections.abc import Callable
from http import HTTPStatus

import httpx

from hepsijet.config import HepsijetConfig
from hepsijet.errors import AuthenticationError

TOKEN_PATH = "/auth/getToken"
TOKEN_LIFETIME_SECONDS = 55 * 60
"""Refresh 5 minutes before HepsiJET's 60-minute expiry, so a token never dies mid-request."""


class TokenCache:
    """Holds one token and forgets it when it gets too old."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    def get(self) -> str | None:
        if self._token is not None and self._clock() < self._expires_at:
            return self._token
        return None

    def store(self, token: str) -> None:
        self._token = token
        self._expires_at = self._clock() + TOKEN_LIFETIME_SECONDS

    def clear(self) -> None:
        self._token = None


def token_request(config: HepsijetConfig) -> httpx.Request:
    credentials = f"{config.username}:{config.password.get_secret_value()}".encode()
    return httpx.Request(
        "GET",
        config.base_url + TOKEN_PATH,
        headers={
            "Accept": "application/json",
            "Authorization": "Basic " + base64.b64encode(credentials).decode(),
        },
    )


def read_token(response: httpx.Response) -> str:
    """Pull the token out of the getToken reply: `{"data": {"token": ...}}` or `{"token": ...}`."""
    if response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        raise AuthenticationError("HepsiJET rejected the username or password.")
    if response.is_error:
        raise AuthenticationError(f"Getting a token failed with HTTP {response.status_code}.")

    try:
        body = response.json()
    except ValueError as error:
        raise AuthenticationError("The token reply was not JSON.") from error

    token = None
    if isinstance(body, dict):
        data = body.get("data")
        token = data.get("token") if isinstance(data, dict) else body.get("token")

    if not isinstance(token, str) or not token:
        raise AuthenticationError(f"Couldn't find a token in HepsiJET's reply: {body!r}")
    return token
