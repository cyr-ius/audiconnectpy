"""Exceptions for Audi connect."""
from __future__ import annotations

import logging
from typing import Tuple

from aiohttp import ClientResponse, RequestInfo  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class AudiException(Exception):
    """General exception."""


class RequestError(AudiException):
    """Not open url."""

    def __init__(
        self,
        request_info: RequestInfo,
        history: Tuple["ClientResponse", ...] | None = None,
        status: int | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize."""
        self.request_info = request_info
        self.history = history
        self.status = status
        self.message = message

        if status is not None:
            self.status = status
        else:
            self.status = 0

        self.message = message
        self.history = history
        self.args = (request_info, history)

    def __str__(self) -> str:
        """Set string object."""
        return "{}, message={!r}, url={!r}".format(  # pylint: disable=consider-using-f-string
            self.status,
            self.message,
            self.request_info.real_url,
        )


class AuthorizationError(AudiException):
    """Authentification error."""


class HttpRequestError(AudiException):
    """Requests error."""


class TimeoutExceededError(AudiException):
    """Timeout exceeded."""


class InvalidFormatError(AudiException):
    """Timeout exceeded."""
