"""Tests analytics."""

from __future__ import annotations

import logging
from unittest.mock import patch

from aiohttp import ClientSession
import pytest

from audiconnectpy import AudiConnect, AudiException

USR = "x.y@z.zz"
PWD = "password"
COUNTRY = "FR"
SPIN = 1234

_LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
@patch("audiconnectpy.auth.Auth.async_connect")
@patch("audiconnectpy.api.AudiConnect._async_fill_url")
async def test_vehicle_1(
    connect, fill_url, information_vehicles, vehicle_1, position, location, capabilities
) -> None:
    """Test connection."""
    api = AudiConnect(
        session=ClientSession(), username=USR, password=PWD, country=COUNTRY, spin=SPIN
    )

    with (
        patch(
            "audiconnectpy.api.AudiConnect.async_get_information_vehicles",
            return_value=information_vehicles,
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
@patch("audiconnectpy.auth.Auth.async_connect")
@patch("audiconnectpy.api.AudiConnect._async_fill_url")
async def test_vehicle_2(
    connect, fill_url, information_vehicles, vehicle_2, position, location, capabilities
) -> None:
    """Test connection."""
    api = AudiConnect(
        session=ClientSession(), username=USR, password=PWD, country=COUNTRY, spin=SPIN
    )

    with (
        patch(
            "audiconnectpy.api.AudiConnect.async_get_information_vehicles",
            return_value=information_vehicles,
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
        my_vehicle = api.vehicles[0]

        assert api.vehicles is not None
        assert my_vehicle.infos is not None
        assert my_vehicle.climatisation.window_heating_status.state.front is False
        assert my_vehicle.vehicle_lights.lights_status.lights.status is False
        assert my_vehicle.measurements.range_status.electric_range == 212
        assert my_vehicle.measurements.odometer_status.odometer == 10329
        assert (
            my_vehicle.vehicle_health_inspection.maintenance_status.mileage_km == 10329
        )
        assert my_vehicle.fuel_status.range_status.total_range_km == 212
        assert my_vehicle.climatisation.window_heating_status.state.front is False
        assert (
            my_vehicle.climatisation.climatisation_status.climatisation_state is False
        )
        assert (
            my_vehicle.climatisation.climatisation_status.climatisation_state is False
        )
        assert (
            my_vehicle.climatisation.climatisation_settings.climatization_at_unlock
            is True
        )
        assert my_vehicle.charging.battery_status.cruising_range_electric_km == 212
        assert my_vehicle.charging.charge_mode.preferred_charge_mode == "manual"
        assert my_vehicle.charging.charging_settings.max_charge_current_ac == "maximum"
        assert my_vehicle.charging.charging_status.remaining == 400
        assert my_vehicle.charging.plug_status.led_color == "green"


@pytest.mark.asyncio
@patch("audiconnectpy.auth.Auth.async_connect")
@patch("audiconnectpy.api.AudiConnect._async_fill_url")
async def test_vehicle_3(
    connect, fill_url, information_vehicles, vehicle_3, position, location, capabilities
) -> None:
    """Test connection."""
    api = AudiConnect(
        session=ClientSession(), username=USR, password=PWD, country=COUNTRY, spin=SPIN
    )

    with (
        patch(
            "audiconnectpy.api.AudiConnect.async_get_information_vehicles",
            return_value=information_vehicles,
        ),
        patch(
            "audiconnectpy.vehicle.Vehicle.async_get_selectivestatus",
            return_value=vehicle_3,
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
        await api.async_login()
        my_vehicle = api.vehicles[0]

        assert api.vehicles is not None
        assert my_vehicle.infos is not None
        assert my_vehicle.climatisation.window_heating_status.state.front is False
        assert my_vehicle.climatisation.window_heating_status.state.front is False
        assert (
            "start_local"
            in my_vehicle.climatisation_timers.climatisation_timers_status.timers[
                0
            ].single_timer.to_dict()
        )
        assert my_vehicle.position_supported is False
        assert my_vehicle.locations_supported is False
        assert my_vehicle.capabilities_supported is True
