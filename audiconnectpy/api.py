"""Audi connect."""
from __future__ import annotations

import logging
from typing import Any, Tuple

from aiohttp import ClientSession

from .auth import Auth
from .const import (
    BRAND,
    URL_HOME_REGION,
    URL_HOME_REGION_SETTER,
    URL_INFO_VEHICLE,
    URL_INFO_VEHICLE_US,
)
from .exceptions import AudiException
from .helpers import ExtendedDict
from .models import Globals
from .vehicle import Vehicle

_LOGGER = logging.getLogger(__name__)


class AudiConnect:
    """Representation of an Audi Connect Account."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        country: str = "DE",
        spin: int | None = None,
        unit_system: str = "metric",
    ) -> None:
        """Initialize."""
        Globals(unit_system)
        self._audi_vehicles: list[Vehicle] = []
        self.auth = Auth(session)
        self.country = country.upper()
        self._excluded_refresh: set[str] = set()
        self._password = password
        self._username = username
        self._spin = spin
        self.is_connected: bool = False
        self.vehicles: dict[str, Vehicle] = {}

    async def async_login(self) -> bool:
        """Login and retrieve tokens."""
        if not self.is_connected:
            self.is_connected = await self.auth.async_connect(
                self._username, self._password, self.country
            )
        return self.is_connected

    async def async_update(self, vinlist: list[str] | None = None) -> bool:
        """Update data."""
        if not await self.async_login():
            return False
        # Update the state of all vehicles.
        try:
            if len(self._audi_vehicles) == 0:
                vehicles_response = await self.async_get_information_vehicles()
                for response in vehicles_response.getr("data.userVehicles", []):
                    (url, url_setter) = await self._async_fill_url(response["vin"])
                    self._audi_vehicles.append(
                        Vehicle(
                            self.auth,
                            ExtendedDict(response),
                            url,
                            url_setter,
                            self._spin,
                            self.country,
                        )
                    )
            for vehicle in self._audi_vehicles:
                await self._async_add_or_update_vehicle(vehicle, vinlist)
            return True
        except OSError as exception:
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

    async def _async_fill_url(self, vin: str) -> Tuple[str, str]:
        """Fill region."""
        url = URL_HOME_REGION
        url_setter = URL_HOME_REGION_SETTER
        try:
            rsp = await self.auth.get(
                f"{url_setter}/cs/vds/v1/vehicles/{vin}/homeRegion"
            )
            rsp = rsp if rsp else ExtendedDict()
            uri = rsp.getr("homeRegion.baseUri.content")
            if uri and uri != url_setter:
                url = uri.replace("mal-", "fal-").replace("/api", "/fs-car")
                url_setter = uri
        except Exception:  # pylint: disable=broad-except
            pass

        return url, url_setter

    async def async_get_information_vehicles(self) -> Any:
        """Get information vehicles."""
        headers = await self.auth.async_get_headers(
            token_type="audi",
            headers={
                "Accept-Language": f"{self.auth.language}-{self.country}",
                "Content-Type": "application/json",
                "X-User-Country": self.country,
            },
        )
        data = {
            "query": "query vehicleList {\n userVehicles {\n vin\n mappingVin\n vehicle { core { modelYear\n }\n media { shortName\n longName }\n }\n csid\n commissionNumber\n type\n devicePlatform\n mbbConnect\n userRole {\n role\n }\n vehicle {\n classification {\n driveTrain\n }\n }\n nickname\n }\n}"
        }
        url = URL_INFO_VEHICLE if self.country != "US" else URL_INFO_VEHICLE_US
        resp = await self.auth.post(
            url, data=data, headers=headers, allow_redirects=False
        )
        resp = resp if resp else ExtendedDict()
        if "data" not in resp:
            raise AudiException("Invalid json in vehicle information")
        return resp

    async def async_get_vehicles(self) -> Any:
        """Get all vehicles."""
        url = URL_HOME_REGION
        data = await self.auth.get(
            f"{url}/usermanagement/users/v1/{BRAND}/{self.country}/vehicles"
        )
        data = data if data else ExtendedDict()
        return data
