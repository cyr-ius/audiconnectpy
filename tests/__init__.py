"""Tests for audiconnect.

Run tests with `pytest`
and to update snapshots `pytest --snapshot-update`
"""

from collections.abc import Generator
import json
from pathlib import Path
from unittest.mock import AsyncMock

from multidict import CIMultiDict


def load_fixture(filename: str) -> str:
    """Load a fixture."""
    path = Path(__package__) / "fixtures" / filename
    return json.loads(path.read_text(encoding="utf-8"))


def mock_response(resp_data=None, status_code=200) -> Generator[AsyncMock, None, None]:
    """Mock aiohttp session request."""
    mock = AsyncMock()
    mock.return_value.headers = CIMultiDict({("Content-Type", "application/json")})
    mock.return_value.status = status_code
    mock.return_value.json = AsyncMock(return_value=resp_data)
    return mock
