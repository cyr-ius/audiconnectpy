"""Tests analytics."""

from __future__ import annotations

import logging
from unittest.mock import patch

from aiohttp import ClientSession
import pytest
from syrupy.assertion import SnapshotAssertion

from audiconnectpy import AudiConnect, AudiException

USR = "x.y@z.zz"
PWD = "password"
COUNTRY = "FR"
SPIN = 1234

_LOGGER = logging.getLogger(__name__)


@patch("audiconnectpy.auth.Auth.async_connect")
@patch("audiconnectpy.api.AudiConnect._async_fill_url")
async def test_vehicle_0(
    connect,
    fill_url,
    snapshot: SnapshotAssertion,
    information,
    vehicles,
    vehicle_0,
    position,
    location,
    capabilities,
    uris,
) -> None:
    """Test connection."""
    api = AudiConnect(
        session=ClientSession(), username=USR, password=PWD, country=COUNTRY, spin=SPIN
    )

    with (
        patch(
            "audiconnectpy.api.AudiConnect.async_get_vehicles",
            return_value=vehicles,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_selectivestatus",
            return_value=vehicle_0,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_information",
            return_value=information,
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
        api.auth.uris = uris
        await api.async_login()
        my_vehicle = api.vehicles[0]
        assert api.vehicles is not None
        assert my_vehicle.infos == snapshot
        assert my_vehicle.access == snapshot
        assert my_vehicle.fuel_status == snapshot
        assert my_vehicle.vehicle_health_inspection == snapshot
        assert my_vehicle.vehicle_lights == snapshot
        assert my_vehicle.measurements == snapshot
        assert my_vehicle.oil_level == snapshot
        assert my_vehicle.vehicle_health_warnings == snapshot


@patch("audiconnectpy.auth.Auth.async_connect")
@patch("audiconnectpy.api.AudiConnect._async_fill_url")
async def test_vehicle_1(
    connect,
    fill_url,
    snapshot: SnapshotAssertion,
    information,
    vehicles,
    vehicle_1,
    position,
    location,
    capabilities,
    uris,
) -> None:
    """Test connection."""
    api = AudiConnect(
        session=ClientSession(), username=USR, password=PWD, country=COUNTRY, spin=SPIN
    )

    with (
        patch(
            "audiconnectpy.api.AudiConnect.async_get_vehicles",
            return_value=vehicles,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_selectivestatus",
            return_value=vehicle_1,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_information",
            return_value=information,
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
        api.auth.uris = uris
        await api.async_login()
        my_vehicle = api.vehicles[0]

        assert api.vehicles is not None
        assert my_vehicle.infos == snapshot
        assert my_vehicle.user_capabilities == snapshot
        assert my_vehicle.access == snapshot
        assert my_vehicle.charging == snapshot
        assert my_vehicle.climatisation_timers == snapshot
        assert my_vehicle.climatisation == snapshot
        assert my_vehicle.fuel_status == snapshot
        assert my_vehicle.vehicle_health_inspection == snapshot
        assert my_vehicle.vehicle_lights == snapshot
        assert my_vehicle.measurements == snapshot
        # assert my_vehicle.oil_level == snapshot
        # assert my_vehicle.vehicle_health_warnings == snapshot


@patch("audiconnectpy.auth.Auth.async_connect")
@patch("audiconnectpy.api.AudiConnect._async_fill_url")
async def test_vehicle_2(
    connect,
    fill_url,
    snapshot: SnapshotAssertion,
    information,
    vehicles,
    vehicle_2,
    position,
    location,
    capabilities,
    uris,
) -> None:
    """Test connection."""
    api = AudiConnect(
        session=ClientSession(), username=USR, password=PWD, country=COUNTRY, spin=SPIN
    )

    with (
        patch(
            "audiconnectpy.api.AudiConnect.async_get_vehicles",
            return_value=vehicles,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_selectivestatus",
            return_value=vehicle_2,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_information",
            return_value=information,
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
        api.auth.uris = uris
        await api.async_login()
        my_vehicle = api.vehicles[0]

        assert api.vehicles is not None
        assert my_vehicle.infos == snapshot
        assert my_vehicle.user_capabilities == snapshot
        assert my_vehicle.access == snapshot
        assert my_vehicle.charging == snapshot
        assert my_vehicle.climatisation_timers == snapshot
        assert my_vehicle.climatisation == snapshot
        assert my_vehicle.fuel_status == snapshot
        assert my_vehicle.vehicle_health_inspection == snapshot
        assert my_vehicle.vehicle_lights == snapshot
        assert my_vehicle.measurements == snapshot
        # assert my_vehicle.oil_level == snapshot
        # assert my_vehicle.vehicle_health_warnings == snapshot


@pytest.mark.asyncio
@patch("audiconnectpy.auth.Auth.async_connect")
@patch("audiconnectpy.api.AudiConnect._async_fill_url")
async def test_vehicle_3(
    connect,
    fill_url,
    snapshot: SnapshotAssertion,
    information,
    vehicles,
    vehicle_3,
    position,
    location,
    capabilities,
    uris,
) -> None:
    """Test connection."""
    api = AudiConnect(
        session=ClientSession(), username=USR, password=PWD, country=COUNTRY, spin=SPIN
    )

    with (
        patch(
            "audiconnectpy.api.AudiConnect.async_get_vehicles",
            return_value=vehicles,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_selectivestatus",
            return_value=vehicle_3,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_information",
            return_value=information,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_position",
            side_effect=AudiException(),
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_location",
            side_effect=AudiException(),
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_capabilities",
            return_value=capabilities,
        ),
    ):
        api.auth.uris = uris
        await api.async_login()
        my_vehicle = api.vehicles[0]

        assert api.vehicles is not None
        assert my_vehicle.climatisation_timers == snapshot
        assert my_vehicle.climatisation == snapshot
        assert my_vehicle.charging == snapshot
        assert my_vehicle.position_supported is False
        assert my_vehicle.locations_supported is False
        assert my_vehicle.capabilities_supported is True
