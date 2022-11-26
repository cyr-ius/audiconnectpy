# -*- coding:utf-8 -*-

"""audiconnectpy package."""
from .api import AudiConnect
from .exceptions import AudiException, AuthorizationError
from .util import addLoggingLevel

__all__ = ["AudiConnect", "AudiException", "AuthorizationError"]

addLoggingLevel("advanced", 9)
addLoggingLevel("expert", 8)
