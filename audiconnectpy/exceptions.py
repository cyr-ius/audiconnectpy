"""Exceptions for Audi connect."""


class AudiException(Exception):
    """General exception."""


class AuthorizationError(AudiException):
    """Authentification error."""


class HttpRequestError(AudiException):
    """HTTP Requests error."""


class TimeoutExceededError(AudiException):
    """Timeout exceeded."""


class ServiceNotFoundError(AudiException):
    """Service not found."""
