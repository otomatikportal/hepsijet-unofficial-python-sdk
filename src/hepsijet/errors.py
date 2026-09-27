"""Exceptions raised by the SDK.

Catch `HepsijetError` to handle every failure in one place. Invalid input is caught earlier,
when you build a model, as a regular `pydantic.ValidationError`.
"""

import httpx

_MAX_BODY_IN_MESSAGE = 500


class HepsijetError(Exception):
    """Base class for every error this SDK raises."""


class AuthenticationError(HepsijetError):
    """HepsiJET rejected your username or password, or didn't return a token."""


class ApiError(HepsijetError):
    """HepsiJET answered with an HTTP error (4xx or 5xx)."""

    def __init__(self, response: httpx.Response) -> None:
        self.status_code = response.status_code
        self.body = response.text
        super().__init__(
            f"HepsiJET returned HTTP {self.status_code}: {self.body[:_MAX_BODY_IN_MESSAGE]}"
        )


class UnexpectedResponseError(HepsijetError):
    """HepsiJET answered successfully, but the reply didn't have the documented shape."""

    def __init__(self, message: str, response: httpx.Response) -> None:
        self.body = response.text
        super().__init__(f"{message}. Response body: {self.body[:_MAX_BODY_IN_MESSAGE]}")
