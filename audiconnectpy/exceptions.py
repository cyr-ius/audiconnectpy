"""Exceptions for Audi connect."""


class AudiException(Exception):
    """General exception."""


class AuthorizationError(AudiException):
    """Authentication error."""


class HttpRequestError(AudiException):
    """HTTP Requests error."""


class TimeoutExceededError(AudiException):
    """Timeout exceeded."""


class ServiceNotFoundError(AudiException):
    """Service not found."""
