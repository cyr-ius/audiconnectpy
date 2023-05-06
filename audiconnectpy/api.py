"""Audi connect."""
from __future__ import annotations

import logging

from aiohttp import ClientSession

from .auth import Auth
from .exceptions import AudiException
from .helpers import ExtendedDict
from .models import Globals, Vehicle
from .services import AudiService

_LOGGER = logging.getLogger(__name__)


class AudiConnect:
    """Representation of an Audi Connect Account."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        country: str,
        spin: int,
        unit_system: str = "metric",
    ) -> None:
        """Initiliaze."""
        Globals(unit_system)
        self._audi_vehicles: list[Vehicle] = []
        self._auth = Auth(session)
        self._country = country
        self._excluded_refresh: set[str] = set()
        self._password = password
        self._unit_system = unit_system
        self._username = username
        self.is_connected: bool = False
        self.services = AudiService(self._auth, country, spin)
        self.vehicles: dict[str, Vehicle] = {}

    async def async_login(self) -> bool:
        """Login and retreive tokens."""
        if not self.is_connected:
            self.is_connected = await self._auth.async_connect(
                self._username, self._password, self._country
            )
        return self.is_connected

    async def async_update(self, vinlist: list[str] | None = None) -> bool:
        """Update data."""
        if not await self.async_login():
            return False
        # Update the state of all vehicles.
        try:
            if len(self._audi_vehicles) == 0:
                vehicles_response = await self.services.async_get_vehicle_information()
                for response in vehicles_response.getr("data.userVehicles", []):
                    self._audi_vehicles.append(
                        Vehicle(ExtendedDict(response), self.services)
                    )
            for vehicle in self._audi_vehicles:
                await self._async_add_or_update_vehicle(vehicle, vinlist)
            return True
        except IOError as exception:
            # Force a re-login in case of failure/exception
            self.is_connected = False
            _LOGGER.exception(exception)
            return False

    async def _async_add_or_update_vehicle(
        self, vehicle: Vehicle, vinlist: list[str] | None
    ) -> None:
        """Add or Update vehicle."""
        if vehicle.vin is not None:
            if vinlist is None or vehicle.vin.upper() in vinlist:
                vupd = [
                    x for vin, x in self.vehicles.items() if vin == vehicle.vin.upper()
                ]
                if len(vupd) > 0:
                    if await vupd[0].async_fetch_data() is False:
                        self.is_connected = False
                else:
                    try:
                        if await vehicle.async_fetch_data() is False:
                            self.is_connected = False
                        self.vehicles.update({vehicle.vin: vehicle})
                    except AudiException:  # pylint: disable=broad-except
                        pass
