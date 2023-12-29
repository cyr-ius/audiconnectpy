"""Vehicle class."""
from __future__ import annotations

import logging
from typing import Literal

from .auth import Auth
from .exceptions import HttpRequestError, ServiceNotFoundError, TimeoutExceededError
from .helpers import ExtendedDict, retry
from .services import AudiService

_LOGGER = logging.getLogger(__name__)


class Vehicle(AudiService):
    """Vehicle class."""

    def __init__(
        self,
        auth: Auth,
        data: ExtendedDict,
        url: str,
        url_setter: str,
        country: str = "DE",
        spin: str | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(auth, country, spin, url, url_setter)
        self.vin: str = data.get("vin", "").upper()
        self.csid: str = data.get("csid", "")
        self.model = data.getr("vehicle.media.longName", "")
        self.model_year = data.getr("vehicle.core.modelYear")
        if (nickname := data.get("nickname")) is not None and len(nickname) > 0:
            self.title = nickname
        else:
            self.title = data.getr("vehicle.media.shortName", self.vin)

        self.api_level_climatisation: int = 2  # 2 or 3
        self.api_level_ventilation: int = 1  # 1 or other
        self.api_level_charger: int = 1  # 1 or other
        self.states: ExtendedDict = ExtendedDict()
        self.support_charger: bool | None = None
        self.support_climater: bool | None = None
        self.support_position: bool | None = None
        self.support_preheater: bool | None = None
        self.support_trip_cyclic: bool | None = None
        self.support_trip_long: bool | None = None
        self.support_trip_short: bool | None = None
        self.support_vehicle: bool | None = None

    async def async_fetch_data(self) -> bool:
        """Update."""
        info = ""
        try:
            info = "status"
            await self.async_update_vehicle()
            info = "position"
            await self.async_update_position()
            info = "climater"
            await self.async_update_climater()
            info = "charger"
            await self.async_update_charger()
            info = "preheater"
            await self.async_update_preheater()
            for kind in ["short", "long", "cyclic"]:
                info = kind
                await self.async_update_tripdata(kind)
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error(
                "Unable to update vehicle data %s of %s: %s",
                info,
                self.vin,
                str(error).rstrip("\n"),
            )
            return False
        return True

    @retry(exceptions=TimeoutExceededError, tries=3, delay=2)
    async def async_update_vehicle(self) -> None:
        """Update vehicle status."""
        if self.support_vehicle is not False:
            try:
                result = await self.async_get_vehicle()
                if result.is_supported:
                    self.support_vehicle = result.is_supported
                    self.states.update(result.attributes)
            except ServiceNotFoundError as error:
                if error.args[0] in (401, 403, 502):
                    self.support_vehicle = False
                else:
                    _LOGGER.error(
                        "Unable to obtain the vehicle  status report of %s: %s",
                        self.vin,
                        str(error).rstrip("\n"),
                    )
            except HttpRequestError as error:
                _LOGGER.error(
                    "Unable to obtain the vehicle  status report of %s: %s",
                    self.vin,
                    str(error).rstrip("\n"),
                )

    @retry(exceptions=TimeoutExceededError, tries=3, delay=2)
    async def async_update_position(self) -> None:
        """Update vehicle position."""
        if self.support_position is not False:
            try:
                result = await self.async_get_stored_position()
                if result.is_supported:
                    self.support_position = result.is_supported
                    self.states.update(result.attributes)
            except ServiceNotFoundError as error:
                if error.args[0] in (401, 403, 502):
                    self.support_position = False
                # If error is 204 is returned, the position is currently not available
                elif error.args[0] != 204:
                    _LOGGER.error(
                        "Unable to update the vehicle position of %s: %s",
                        self.vin,
                        str(error).rstrip("\n"),
                    )
            except HttpRequestError as error:
                _LOGGER.error(
                    "Unable to obtain the vehicle position of %s: %s",
                    self.vin,
                    str(error).rstrip("\n"),
                )

    @retry(exceptions=TimeoutExceededError, tries=3, delay=2)
    async def async_update_climater(self) -> None:
        """Update vehicle climater."""
        if self.support_climater is not False:
            try:
                result = await self.async_get_climater()
                if result.is_supported:
                    self.support_climater = result.is_supported
                    self.states.update(result.attributes)
            except ServiceNotFoundError as error:
                if error.args[0] in (401, 403, 502):
                    self.support_climater = False
                else:
                    _LOGGER.error(
                        "Unable to obtain the vehicle climatisation state for %s: %s",
                        self.vin,
                        str(error).rstrip("\n"),
                    )
            except HttpRequestError as error:
                _LOGGER.error(
                    "Unable to obtain the vehicle climatisation state for %s: %s",
                    self.vin,
                    str(error).rstrip("\n"),
                )

    @retry(exceptions=TimeoutExceededError, tries=3, delay=2)
    async def async_update_preheater(self) -> None:
        """Update vehicle preheater."""
        if self.support_preheater is not False:
            try:
                result = await self.async_get_preheater()
                if result.is_supported:
                    self.support_preheater = result.is_supported
                    self.states.update(result.attributes)
            except ServiceNotFoundError as error:
                if error.args[0] in (401, 403, 502):
                    self.support_preheater = False
                else:
                    _LOGGER.error(
                        "Unable to obtain the vehicle preheater state for %s: %s",
                        self.vin,
                        str(error).rstrip("\n"),
                    )
            except HttpRequestError as error:
                _LOGGER.error(
                    "Unable to obtain the vehicle preheater state for %s: %s",
                    self.vin,
                    str(error).rstrip("\n"),
                )

    @retry(exceptions=TimeoutExceededError, tries=3, delay=2)
    async def async_update_charger(self) -> None:
        """Update vehicle charger."""
        if self.support_charger is not False:
            try:
                result = await self.async_get_charger()
                if result.is_supported:
                    self.support_charger = result.is_supported
                    self.states.update(result.attributes)
            except ServiceNotFoundError as error:
                if error.args[0] in (401, 403, 502):
                    self.support_charger = False
                else:
                    _LOGGER.error(
                        "Unable to obtain the vehicle charger state for %s: %s",
                        self.vin,
                        str(error).rstrip("\n"),
                    )
            except HttpRequestError as error:
                _LOGGER.error(
                    "Unable to obtain the vehicle charger state for %s: %s",
                    self.vin,
                    str(error).rstrip("\n"),
                )

    @retry(exceptions=TimeoutExceededError, tries=3, delay=2)
    async def async_update_tripdata(
        self, kind: Literal["short", "long", "cyclic"]
    ) -> None:
        """Update vehicle trip."""
        if getattr(self, f"support_trip_{kind}") is not False:
            try:
                td_cur, td_rst = await self.async_get_tripdata(kind)
                if td_cur.is_supported:
                    self.states.update({f"trip_{kind}_current": td_cur.attributes})

                if td_rst.is_supported:
                    setattr(self, f"support_trip_{kind}", td_rst.is_supported)
                    self.states.update({f"trip_{kind}_reset": td_rst.attributes})
            except ServiceNotFoundError as error:
                if error.args[0] in (400, 401, 403, 502):
                    setattr(self, f"support_trip_{kind}", False)
                else:
                    _LOGGER.error(
                        "Unable to obtain the vehicle %s tripdata of %s: %s",
                        kind,
                        self.vin,
                        str(error).rstrip("\n"),
                    )
            except HttpRequestError as error:
                _LOGGER.error(
                    "Unable to obtain the vehicle %s tripdata of %s: %s",
                    kind,
                    self.vin,
                    str(error).rstrip("\n"),
                )
            else:
                setattr(self, f"support_trip_{kind}", True)

    def set_api_level(
        self, mode: Literal["climatisation", "ventilation"], value: int
    ) -> None:
        """Set API Level for Climatisation and Ventilation."""
        setattr(self, f"api_level_{mode}", value)
