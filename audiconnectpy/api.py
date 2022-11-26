"""Audi connect."""
from __future__ import annotations

import logging

from aiohttp import ClientSession

from .auth import Auth
from .exceptions import HttpRequestError, RequestError
from .models import Vehicle
from .services import AudiService
from .util import Globals

_LOGGER = logging.getLogger(__name__)

MAX_RESPONSE_ATTEMPTS = 10
REQUEST_STATUS_SLEEP = 5

ACTION_LOCK = "lock"
ACTION_CLIMATISATION = "climatisation"
ACTION_CHARGER = "charger"
ACTION_WINDOW_HEATING = "window_heating"
ACTION_PRE_HEATER = "pre_heater"


class AudiConnect:
    """Representation of an Audi Connect Account."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        country: str,
        spin: str,
        unit_system: str = "metric",
    ) -> None:
        """Initiliaze."""
        Globals(unit_system)
        self._auth = Auth(session)
        self._audi_service = AudiService(self._auth, country, spin)
        self._username = username
        self._password = password
        self._country = country
        self._unit_system = unit_system
        self._connect_retries = 3
        self._connect_delay = 10
        self._audi_vehicles: list[Vehicle] = []
        self._excluded_refresh: set[str] = set()
        self.is_connected: bool = False
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
            if len(self._audi_vehicles) > 0:
                for vehicle in self._audi_vehicles:
                    await self.async_add_or_update_vehicle(vehicle, vinlist)

            else:
                vehicles_response = (
                    await self._audi_service.async_get_vehicle_information()
                )
                for response in vehicles_response.get("userVehicles"):
                    self._audi_vehicles.append(Vehicle(response, self._audi_service))

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
                await self._audi_service.async_refresh_vehicle_data(vin)
                _LOGGER.debug("Successfully refreshed data of vehicle %s", vin)
                return True
        except RequestError as error:
            if error.status in (403, 502):
                _LOGGER.debug("refresh vehicle not supported: %s", error.status)
                self._excluded_refresh.add(vin)
            elif error.status == 401:
                _LOGGER.debug("Request unauthorized. Update and retry refresh")
                try:
                    self.is_connected = False
                    await self.async_login()
                    await self._audi_service.async_refresh_vehicle_data(vin)
                except RequestError as err:
                    _LOGGER.error(
                        "Unable to refresh vehicle data of %s, despite trying again (%s)",
                        vin,
                        err,
                    )
            else:
                _LOGGER.error("Unable to refresh vehicle data of %s: %s", vin, error)
        except HttpRequestError as error:  # pylint: disable=broad-except
            _LOGGER.error(
                "Unable to refresh vehicle data of %s: %s", vin, str(error).rstrip("\n")
            )
        return False

    async def async_refresh_vehicles(self) -> bool:
        """Refresh all vehicles data."""
        if not await self.async_login():
            return False

        for vin in self.vehicles:
            await self.async_refresh_vehicle_data(vin)

        return True

    async def async_set_lock(self, vin: str, lock: bool) -> bool:
        """Set lock."""
        if not await self.async_login():
            return False

        try:
            action = "lock" if lock else "unlock"
            _LOGGER.debug("Sending command to %s to vehicle %s", action, vin)
            await self._audi_service.async_set_lock(vin, lock)
            action = "locked" if lock else "unlocked"
            _LOGGER.debug("Successfully %s vehicle %s", action, vin)
            return True
        except RequestError as error:  # pylint: disable=broad-except
            _LOGGER.error(
                "Unable to %s %s: %s",
                action,
                vin,
                str(error).rstrip("\n"),
            )
            return False

    async def async_set_climatisation(self, vin: str, activate: bool) -> bool:
        """Set climatisation."""
        if not await self.async_login():
            return False

        try:
            action = "start" if activate else "stop"
            _LOGGER.debug(
                "Sending command to %s climatisation to vehicle %s", action, vin
            )
            await self._audi_service.async_set_climatisation(vin, activate)
            action = "started" if activate else "stopped"
            _LOGGER.debug("Successfully %s climatisation of vehicle %s", action, vin)
            return True
        except RequestError as error:  # pylint: disable=broad-except
            _LOGGER.error(
                "Unable to %s climatisation of vehicle %s: %s",
                action,
                vin,
                str(error).rstrip("\n"),
            )
            return False

    async def async_set_battery_charger(
        self, vin: str, activate: bool, timer: bool = False
    ) -> bool:
        """Set charger."""
        if not await self.async_login():
            return False

        try:
            action: str = "start" if activate else "stop"
            timed: str = " timed" if timer else ""
            _LOGGER.debug(
                "Sending command to %s%s charger to vehicle %s",
                action,
                vin,
                timed,
            )
            await self._audi_service.async_set_battery_charger(vin, activate, timer)
            action = "started" if activate else "stopped"
            _LOGGER.debug("Successfully %s%s charger of vehicle %s", action, vin, timed)
            return True
        except RequestError as error:  # pylint: disable=broad-except
            action = "start" if activate else "stop"
            _LOGGER.error(
                "Unable to %s charger of vehicle %s: %s",
                action,
                vin,
                str(error).rstrip("\n"),
            )
            return False

    async def async_set_window_heating(self, vin: str, activate: bool) -> bool:
        """Set window heating."""
        if not await self.async_login():
            return False

        try:
            action = "start" if activate else "stop"
            _LOGGER.debug(
                "Sending command to %s window heating to vehicle %s", action, vin
            )
            await self._audi_service.async_set_window_heating(vin, activate)
            action = "started" if activate else "stopped"
            _LOGGER.debug("Successfully %s window heating of vehicle %s", action, vin)
            return True
        except RequestError as error:  # pylint: disable=broad-except
            _LOGGER.error(
                "Unable to %s window heating of vehicle %s: %s",
                action,
                vin,
                str(error).rstrip("\n"),
            )
            return False

    async def async_set_pre_heater(self, vin: str, activate: bool) -> bool:
        """Set pre heater."""
        if not await self.async_login():
            return False

        try:
            action = "start" if activate else "stop"
            _LOGGER.debug("Sending command to %s pre-heater to vehicle %s", action, vin)
            await self._audi_service.async_set_pre_heater(vin, activate)
            action = "started" if activate else "stopped"
            _LOGGER.debug("Successfully %s pre-heater of vehicle %s", action, vin)
            return True
        except RequestError as error:  # pylint: disable=broad-except
            _LOGGER.error(
                "Unable to %s pre-heater of vehicle %s: %s",
                action,
                vin,
                str(error).rstrip("\n"),
            )
            return False
