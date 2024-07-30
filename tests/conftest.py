from __future__ import annotations

from collections import namedtuple
from typing import Any

import pytest

from . import load_fixture


@pytest.fixture
def information() -> dict[str, Any]:
    return load_fixture("info_vehicles.json")


@pytest.fixture
def vehicles() -> dict[str, Any]:
    return load_fixture("get_vehicles.json")


@pytest.fixture
def location() -> dict[str, Any]:
    return load_fixture("location.json")


@pytest.fixture
def capabilities() -> dict[str, Any]:
    return load_fixture("capabilities.json")


@pytest.fixture
def vehicle_0() -> dict[str, Any]:
    return load_fixture("audi0.json")


@pytest.fixture
def vehicle_1() -> dict[str, Any]:
    return load_fixture("audi1.json")


@pytest.fixture
def vehicle_2() -> dict[str, Any]:
    return load_fixture("audi2.json")


@pytest.fixture
def vehicle_3() -> dict[str, Any]:
    return load_fixture("audi3.json")


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


@pytest.fixture
def uris():
    return {
        "client_id": "client_id",
        "audi_url": "audi_url",
        "profil_url": "profil_url/v3",
        "mbb_url": "mbb_url",
        "here_url": "URL_HERE_COM",
        "mdk_url": "mdk_url",
        "vdgqs_url": "vdgqs_url",
        "cv_url": "cvvsb_url",
        "user_url": "URL_INFO_USER",
        "authorization_endpoint": "authorization_endpoint_url",
        "token_endpoint": "token_endpoint_url",
        "revocation_endpoint": "revocation_endpoint_url",
        "language": "en",
        "country": "EN",
    }
