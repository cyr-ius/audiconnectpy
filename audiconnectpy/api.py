"""Audi connect."""
from __future__ import annotations

import logging

from aiohttp import ClientSession

from .auth import Auth
from .exceptions import HttpRequestError, ServiceNotFoundError
from .models import Vehicle
from .services import AudiService
from .util import Globals

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
        """Initilaze."""
        Globals(unit_system)
        self._audi_vehicles: list[Vehicle] = []
        self._auth = Auth(session)
        self._connect_delay = 10
        self._connect_retries = 3
        self._country = country
        self._excluded_refresh: set[str] = set()
        self._password = password
        self._unit_system = unit_system
        self._username = username
        self.is_connected: bool = False
        self.services = AudiService(self._auth, country, spin)
        self.vehicles: dict[str, Vehicle] = {}

    async def async_login(self) -> bool:
        """Login and retrieve tokens."""
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
            if len(self._audi_vehicles) > 0:
                for vehicle in self._audi_vehicles:
                    await self.async_add_or_update_vehicle(vehicle, vinlist)

            else:
                vehicles_response = await self.services.async_get_vehicle_information()
                if vehicles_response.get("userVehicles") is None:
                    return False
                for response in vehicles_response.get("userVehicles"):
                    self._audi_vehicles.append(Vehicle(response, self.services))

                self.vehicles = {}
                for vehicle in self._audi_vehicles:
                    await self.async_add_or_update_vehicle(vehicle, vinlist)

            return True

        except IOError as exception:
            # Force a re-login in case of failure/exception
            self.is_connected = False
            _LOGGER.exception(exception)
            return False

    async def async_add_or_update_vehicle(
        self, vehicle: Vehicle, vinlist: list[str] | None
    ) -> None:
        """Add or Update vehicle."""
        if vehicle.vin is not None:
            if vinlist is None or vehicle.vin.lower() in vinlist:
                vupd = [
                    x for vin, x in self.vehicles.items() if vin == vehicle.vin.lower()
                ]
                if len(vupd) > 0:
                    if await vupd[0].async_fetch_data(self._connect_retries) is False:
                        self.is_connected = False
                else:
                    try:
                        if (
                            await vehicle.async_fetch_data(self._connect_retries)
                            is False
                        ):
                            self.is_connected = False
                        self.vehicles.update({vehicle.vin: vehicle})
                    except Exception:  # pylint: disable=broad-except
                        pass

    async def async_refresh_vehicle_data(self, vin: str) -> bool:
        """Refresh vehicle data."""
        if not await self.async_login():
            return False

        try:
            if vin not in self._excluded_refresh:
                _LOGGER.debug("Sending command to refresh data to vehicle %s", vin)
                await self.services.async_refresh_vehicle_data(vin)
                _LOGGER.debug("Successfully refreshed data of vehicle %s", vin)
                return True
        except ServiceNotFoundError as error:
            if error.args[0] in (403, 502):
                _LOGGER.debug("Refresh vehicle not supported")
                self._excluded_refresh.add(vin)
            elif error.args[0] == 401:
                _LOGGER.debug("Request unauthorized. Update and retry refresh")
                try:
                    self.is_connected = False
                    await self.async_login()
                    await self.services.async_refresh_vehicle_data(vin)
                except ServiceNotFoundError as err:
                    _LOGGER.error(
                        "Unable to refresh vehicle data of %s, despite trying again (%s)",
                        vin,
                        err,
                    )
            else:
                _LOGGER.error("Unable to refresh vehicle data of %s: %s", vin, error)
        except HttpRequestError as error:
            _LOGGER.error(
                "Unable to refresh vehicle data of %s: %s", vin, str(error).rstrip("\n")
            )
        return False

    async def async_refresh_vehicles(self) -> bool:
        """Refresh all vehicles data."""
        for vin in self.vehicles:
            await self.async_refresh_vehicle_data(vin)

        return True
