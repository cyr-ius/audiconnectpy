"""Helper functions."""
from __future__ import annotations

import functools
import json
import logging
import random
import time
from collections.abc import Callable
from datetime import datetime
from functools import reduce
from hashlib import sha512
from typing import Any

from .exceptions import TimeoutExceededError

_LOGGER = logging.getLogger(__name__)


class ExtendedDict(dict[Any, Any]):
    """Extend dictionary class."""

    def getr(self, keys: str, default: Any = None) -> Any:
        """Get recursive attribute."""
        reduce_value: Any = reduce(
            lambda d, key: d.get(key, default) if isinstance(d, dict) else default,
            keys.split("."),
            self,
        )
        if isinstance(reduce_value, dict):
            return ExtendedDict(reduce_value)
        return reduce_value


def to_byte_array(hex_string: str) -> list[int]:
    """Return byte array."""
    result = []
    for i in range(0, len(hex_string), 2):
        result.append(int(hex_string[i : i + 2], 16))

    return result


def obj_parser(obj: dict[str, Any]) -> dict[str, Any]:
    """Parse datetime."""
    for key, val in obj.items():
        try:
            obj[key] = datetime.strptime(val, "%Y-%m-%dT%H:%M:%S%z")
        except (TypeError, ValueError):
            pass
    return obj


def json_loads(jsload: str | bytes) -> Any:
    """Json load."""
    data_dict = json.loads(jsload, object_hook=obj_parser)
    return ExtendedDict(data_dict)


def retry(
    exceptions: Any = Exception,
    tries: int = -1,
    delay: float = 0,
    max_delay: int | None = None,
    backoff: int = 1,
    jitter: int | tuple[int, int] = 0,
    logger: Any = _LOGGER,
) -> Callable[..., Any]:
    """Retry Decorator.

    :param exceptions: an exception or a tuple of exceptions to catch. default: Exception.
    :param tries: the maximum number of attempts. default: -1 (infinite).
    :param delay: initial delay between attempts. default: 0.
    :param max_delay: the maximum value of delay. default: None (no limit).
    :param backoff: multiplier applied to delay between attempts. default: 1 (no backoff).
    :param jitter: extra seconds added to delay between attempts. default: 0.
                   fixed if a number, random if a range tuple (min, max)
    :param logger: logger.warning(fmt, error, delay) will be called on failed attempts.
                   default: retry.logging_logger. if None, logging is disabled.
    :returns: the result of the f function.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        """Add decorator."""

        @functools.wraps(func)
        async def newfn(*args: Any, **kwargs: Any) -> Any:
            """Load function."""
            _tries, _delay = tries, delay
            while _tries:
                try:
                    return await func(*args, **kwargs)
                except exceptions as error:  # pylint: disable=broad-except
                    _tries -= 1
                    if not _tries:
                        logger.error("%s, timeout exceeded", error)
                        raise TimeoutExceededError(error) from error

                    if logger is not None:
                        logger.warning("%s, trying again in %s seconds", error, _delay)

                    time.sleep(_delay)
                    _delay *= backoff

                    if isinstance(jitter, tuple):
                        _delay += random.uniform(*jitter)
                    else:
                        _delay += jitter

                    if max_delay is not None:
                        _delay = min(_delay, max_delay)

        return newfn

    return decorator


def spin_hash(spin, challenge: str) -> str:
    """Generate security pin hash."""
    pin = to_byte_array(str(spin))
    byte_challenge = to_byte_array(challenge)
    b_pin = bytes(pin + byte_challenge)
    return sha512(b_pin).hexdigest().upper()
