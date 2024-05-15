from __future__ import annotations

from collections import namedtuple
import json
from typing import Any

import pytest

from . import load_fixture


@pytest.fixture
def information_vehicles() -> dict[str, Any]:
    return json.loads(load_fixture("info_vehicles.json"))


@pytest.fixture
def location() -> dict[str, Any]:
    return json.loads(load_fixture("location.json"))


@pytest.fixture
def capabilities() -> dict[str, Any]:
    return {}


@pytest.fixture
def vehicle_0() -> dict[str, Any]:
    return json.loads(load_fixture("audi0.json"))


@pytest.fixture
def vehicle_1() -> dict[str, Any]:
    return json.loads(load_fixture("audi1.json"))


@pytest.fixture
def vehicle_2() -> dict[str, Any]:
    return json.loads(load_fixture("audi2.json"))


@pytest.fixture
def position():
    return {
        "data": {
            "lon": -10.020479,
            "lat": 87.928315,
            "carCapturedTimestamp": "2024-05-14T17:42:22Z",
        }
    }


@pytest.fixture
def fill_region():
    FillRegion = namedtuple("FillRegion", ("url", "url_setter"))
    return FillRegion("", "")
