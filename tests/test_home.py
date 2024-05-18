"""Tests analytics."""

from __future__ import annotations

import logging
from unittest.mock import patch

from aiohttp import ClientSession
import pytest

from audiconnectpy import AudiConnect

VW_USERNAME = "x.y@z.zz"
VW_PASSWORD = "password"
COUNTRY = "FR"
SPIN = 1234

_LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
@patch("audiconnectpy.api.AudiConnect._async_retrieve_url_service")
async def test_connect(
    uris, fill_region, information_vehicles, vehicle_0, position, location, capabilities
) -> None:
    """Test connection."""
    session = ClientSession()
    api = AudiConnect(
        session=session,
        username=VW_USERNAME,
        password=VW_PASSWORD,
        country=COUNTRY,
        spin=SPIN,
    )

    with (
        patch("audiconnectpy.auth.Auth.async_connect", return_value=None),
        patch(
            "audiconnectpy.api.AudiConnect.async_get_information_vehicles",
            return_value=information_vehicles,
        ),
        patch(
            "audiconnectpy.api.AudiConnect._async_fill_url", return_value=fill_region
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_selectivestatus",
            return_value=vehicle_0,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_position",
            return_value=position,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_location",
            return_value=location,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_capabilities",
            return_value=capabilities,
        ),
    ):
        await api.async_login()

        assert api.vehicles is not None
        assert api.vehicles[0].infos is not None


@pytest.mark.asyncio
@patch("audiconnectpy.api.AudiConnect._async_retrieve_url_service")
async def test_vehicle_1(
    uris, fill_region, information_vehicles, vehicle_1, position, location, capabilities
) -> None:
    """Test connection."""
    session = ClientSession()
    api = AudiConnect(
        session=session,
        username=VW_USERNAME,
        password=VW_PASSWORD,
        country=COUNTRY,
        spin=SPIN,
    )

    with (
        patch("audiconnectpy.auth.Auth.async_connect", return_value=None),
        patch(
            "audiconnectpy.api.AudiConnect.async_get_information_vehicles",
            return_value=information_vehicles,
        ),
        patch(
            "audiconnectpy.api.AudiConnect._async_fill_url", return_value=fill_region
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_selectivestatus",
            return_value=vehicle_1,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_position",
            return_value=position,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_location",
            return_value=location,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_capabilities",
            return_value=capabilities,
        ),
    ):
        await api.async_login()

        assert api.vehicles is not None
        assert api.vehicles[0].infos is not None


@pytest.mark.asyncio
@patch("audiconnectpy.api.AudiConnect._async_retrieve_url_service")
async def test_vehicle_2(
    uris, fill_region, information_vehicles, vehicle_2, position, location, capabilities
) -> None:
    """Test connection."""
    session = ClientSession()
    api = AudiConnect(
        session=session,
        username=VW_USERNAME,
        password=VW_PASSWORD,
        country=COUNTRY,
        spin=SPIN,
    )

    with (
        patch("audiconnectpy.auth.Auth.async_connect", return_value=None),
        patch(
            "audiconnectpy.api.AudiConnect.async_get_information_vehicles",
            return_value=information_vehicles,
        ),
        patch(
            "audiconnectpy.api.AudiConnect._async_fill_url", return_value=fill_region
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_selectivestatus",
            return_value=vehicle_2,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_position",
            return_value=position,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_location",
            return_value=location,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_capabilities",
            return_value=capabilities,
        ),
    ):
        await api.async_login()

        assert api.vehicles is not None
        assert api.vehicles[0].infos is not None
