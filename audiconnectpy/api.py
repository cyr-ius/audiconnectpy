"""Audi connect."""

from __future__ import annotations

from collections import namedtuple
import logging
from typing import Any, Literal, NamedTuple, Self

from aiohttp import ClientSession

from .auth import Auth
from .const import CLIENT_IDS, URL_HOME_REGION, URL_HOME_REGION_SETTER
from .exceptions import AudiException
from .helpers import ExtendedDict
from .vehicle import Globals, Vehicle

MODELS = list(CLIENT_IDS)

_LOGGER = logging.getLogger(__name__)


class AudiConnect:
    """Representation of an Audi Connect Account."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        country: str = "DE",
        spin: str | None = None,
        *,
        unit_system: str = "metric",
        model: Literal["standard", "e-tron"] = "standard",
    ) -> None:
        """Initialize."""
        Globals(unit_system)
        self.auth = Auth(session, username, password, country.upper(), model)
        self._spin = str(spin)
        self.vehicles: list[Vehicle] = []

    @property
    def is_connected(self) -> bool:
        """Is connected."""
        return self.auth.binded

    @property
    def uri_services(self) -> dict[str, str]:
        return self.auth.uris

    async def async_login(self, vinlist: list[str] | None = None) -> None:
        """Login and retrieve tokens."""
        if self.is_connected:
            return

        await self.auth.async_connect()

        if len(self.vehicles) == 0:
            await self.async_fetch_data(vinlist=vinlist)

    async def async_fetch_data(self, vinlist: list[str] | None = None) -> None:
        """Update the state of all vehicles."""
        try:
            loaded_vehicles = await self.async_get_vehicles()
            if "data" not in loaded_vehicles:
                raise AudiException("Vehicle(s) not found")
        except AudiException as error:
            raise AudiException(
                f"Error to get information vehicles ({error})"
            ) from error

        self.vehicles = []
        for item in loaded_vehicles["data"]:
            try:
                fill_region = await self._async_fill_url(item["vin"])
            except AudiException as error:
                raise AudiException(f"Error to fill urls ({error})") from error

            vehicle = Vehicle(  # type: ignore
                vin=item["vin"],
                auth=self.auth,
                spin=self._spin,
                uris=self.uri_services,
                fill_region=fill_region,
            )

            if vinlist is None or vehicle.vin.upper() in vinlist:
                # Fetch data for a vehicle
                try:
                    await vehicle.async_update()
                except AudiException as error:
                    _LOGGER.error(
                        "Error while updating - %s - (%s)", vehicle.vin, error
                    )
            self.vehicles.append(vehicle)

    async def async_get_vehicles(self) -> Any:
        """Fetch vehicles."""
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.request(
            "GET",
            f"{self.uri_services['mdk_url']}/vehicle/v2/vehicles",
            headers=headers,
        )
        return data

    async def _async_fill_url(self, vin: str) -> NamedTuple:
        """Fill region."""
        url = URL_HOME_REGION
        url_setter = URL_HOME_REGION_SETTER
        headers = await self.auth.async_get_headers(token_type="mbb")
        rsp = await self.auth.request(
            "GET", f"{url_setter}/cs/vds/v1/vehicles/{vin}/homeRegion", headers=headers
        )
        uri = ExtendedDict(rsp).getr("homeRegion.baseUri.content")
        if uri and uri != url_setter:
            url = uri.replace("mal-", "fal-").replace("/api", "/fs-car")
            url_setter = uri

        FillRegion = namedtuple("FillRegion", ("url", "url_setter"))

        return FillRegion(url, url_setter)

    async def async_close(self) -> None:
        """Close open client (WebSocket) session."""
        if self.auth._session:
            await self.auth._session.close()

    async def __aenter__(self) -> Self:
        """Async enter."""
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Async exit."""
        await self.async_close()
