"""Vehicle class."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from typing import Any, Iterable, Literal, cast

from pydantic import ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel
from pydantic.dataclasses import dataclass

from .const import (
    BRAND,
    FAILED,
    MAX_RESPONSE_ATTEMPTS,
    REQUEST_FAILED,
    REQUEST_STATUS_SLEEP,
    REQUEST_SUCCESSFUL,
    SUCCEEDED,
    SUCCESSFUL,
)
from .exceptions import AudiException, HttpRequestError, TimeoutExceededError
from .helpers import ExtendedDict, spin_hash
from .model import ClimatisationTimers, Model, Position

logger = logging.getLogger(__name__)


class Globals:
    """Global variables."""

    def __init__(self, unit: str) -> None:
        """Initilaze."""
        global UNIT_SYSTEM
        UNIT_SYSTEM = f"{unit}"  # type: ignore


@dataclass(config=ConfigDict(alias_generator=to_camel))
class Vehicle:
    """Vehicle class."""

    vin: str
    uris: dict[str, Any]
    auth: Any
    fill_region: Any = Field(alias="fill_region")
    spin: str | None = None
    last_access: datetime | None = None
    last_update: datetime | None = None
    is_moving: bool | None = None
    capabilities_supported: bool | None = None
    position_supported: bool | None = None
    locations_supported: bool | None = None
    trips_supported: bool | None = None
    position: Position | None = None
    climatisation_timers: ClimatisationTimers = Field(default_factory=list)

    @property
    def api_level(self) -> dict[str, int]:
        """Return API Level."""
        return {
            "climatisation": 2,  # 2 or 3
            "ventilation": 1,  # 1 or other
            "charger": 1,  # 1 or 2 or 3 (json)
            "windows_heating": 1,  # 1 or 2 (json)
            "lock": 2,  # 1 or 2 (json)
        }

    def set_api_level(
        self,
        mode: Literal["climatisation", "ventilation", "charger", "window_heating"],
        value: int,
    ) -> None:
        """Set API Level."""
        if mode in self.api_level.keys():
            self.api_level[mode] = int(value)

    async def async_update(self) -> None:
        """Update data vehicle."""

        # Selective status
        try:
            data = await self.async_get_selectivestatus()
        except (AttributeError, AudiException) as error:
            raise AudiException(error) from error

        # Get information
        try:
            infos = await self.async_get_information()
            data.update({"infos": infos})
        except (AttributeError, AudiException) as error:
            raise AudiException(error) from error

        # Capabilities
        try:
            if self.capabilities_supported is not False:
                capabilities = await self.async_get_capabilities()
                data.update({"capabilities": capabilities})
                self.capabilities_supported = capabilities is not None
        except AttributeError:
            logger.warning("Capabilities failed: format is incorrect")
            self.capabilities_supported = None
        except AudiException:
            self.capabilities_supported = False

        # Position
        try:
            if self.position_supported is not False:
                position = await self.async_get_position()
                if "data" in position:
                    data.update({"position": position})
                    self.is_moving = False
                else:
                    self.is_moving = True
                self.position_supported = position is not None
        except AttributeError:
            logger.warning("Position failed: format is incorrect")
            self.position_supported = None
        except AudiException as error:
            logger.debug(error)
            self.position_supported = False

        # Locations (here.com)
        try:
            if self.locations_supported is not False:
                if location := await self.async_get_location():
                    data.update({"location": location})
                    self.locations_supported = location is not None
        except AttributeError:
            logger.warning("Locations failed: format is incorrect")
            self.locations_supported = None
        except AudiException as error:
            logger.debug(error)
            self.locations_supported = False

        # Trips
        try:
            await self.async_get_trip_last()
            self.trips_supported = True
        except AudiException as error:
            logger.debug(error)
            self.trips_supported = False

        # Load data model
        try:
            vehicle_model = Model(**data)
        except ValidationError as error:
            raise AudiException(error) from error
        else:
            model = dict(vehicle_model.model_dump())
            for attr in model:
                obj = model.get(attr)
                setattr(self, attr, obj)

    async def async_get_information(self) -> Any:
        """Get information vehicles."""
        language = self.uris["language"]
        country = self.uris["country"]
        # url = URL_INFO_VEHICLE if country != "US" else URL_INFO_VEHICLE_US
        headers = await self.auth.async_get_headers(
            token_type="audi",
            headers={
                "Accept-Language": f"{language}-{country}",
                "Content-Type": "application/json",
                "X-User-Country": country,
            },
        )
        # data = {
        #     "query": "query vehicleList {userVehicles {vin mappingVin vehicle { core {modelYear} media { shortName longName }} csid commissionNumber type devicePlatform mbbConnect userRole {role} vehicle {classification {driveTrain}} nickname}}"
        # }
        data = {
            "query": 'query ($vin: String!) {userVehicle(vehicleCoreId: $vin) {vehicle {core {modelYear} classification {modelRange} media {shortName longName} renderPictures(mediaTypes: "MYAPN1NB") { mediaType url}}}}',
            "variables": {"vin": f"{self.vin}"},
        }

        data = await self.auth.request(
            "POST",
            f"{self.uris['vdgqs_url']}/graphql",
            json=data,
            headers=headers,
            allow_redirects=False,
        )
        if (infos := ExtendedDict(data).getr("data.userVehicle.vehicle")) is None:
            raise AudiException("Invalid json in vehicle information")

        return infos

    async def async_get_location(self) -> Any:
        """Get destination data."""
        headers = await self.auth.async_get_headers(token_type="here")
        data = await self.auth.request(
            "GET", f"{self.uris['here_url']}/location", headers=headers
        )
        return data

    async def async_get_position(self) -> Any:
        """Get position data."""
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.request(
            "GET",
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/parkingposition",
            headers=headers,
        )
        return data

    async def async_get_capabilities(self) -> Any:
        """Get capabilities."""
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.request(
            "GET",
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/capabilities",
            headers=headers,
        )
        return data

    async def async_get(self, path: str) -> Any:
        """Get data."""
        try:
            headers = await self.auth.async_get_headers(token_type="idk")
            data = await self.auth.request(
                "GET",
                f"{self.uris['mdk_url']}vehicle/v1/{path}",
                headers=headers,
            )
            return data
        except AudiException as error:
            logger.debug(error)

    async def async_get_selectivestatus(
        self, capabilities: Iterable[str] | None = None
    ) -> Any:
        """Get capabilities."""
        if capabilities is None:
            headers = await self.auth.async_get_headers(token_type="idk")
            response = await self.auth.request(
                "GET",
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/selectivestatus?jobs=userCapabilities",
                headers=headers,
            )
            caps = ExtendedDict(response).getr(
                "userCapabilities.capabilitiesStatus.value", []
            )

            self.capabilities = [str(d) for cap in caps if (d := cap.get("id"))]

        caps = ",".join(self.capabilities)
        str_jobs = f"{caps},userCapabilities" if caps != "" else caps

        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.request(
            "GET",
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/selectivestatus?jobs={str_jobs}",
            headers=headers,
        )
        return data

    async def async_get_trip_last(self) -> Any:
        """Get trip information."""
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.request(
            "GET",
            f"{self.uris['mdk_url']}vehicle/v1/trips/{self.vin}/shortterm/last",
            headers=headers,
        )
        return data

    async def async_wakeup(self) -> Any:
        """Waek up vehicle."""
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.request(
            "POST",
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/vehiclewakeuptrigger",
            headers=headers,
        )
        return data

    async def async_set_lock(self, lock: bool) -> None:
        """Set lock."""
        if self.api_level["lock"] == 1:
            security_token = await self._async_get_security_token(
                "rlu_v1/operations/" + ("LOCK" if lock else "UNLOCK")
            )
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.RemoteLockUnlock_v1_0_0+xml",
                security_token,
            )
            data: str | dict[str, Any] = (
                '<?xml version="1.0" encoding= "UTF-8" ?>'
                + f'<rluAction xmlns="http://audi.de/connect/rlu"><action>{"lock" if lock else "unlock"}</action></rluAction>'
            )

            rsp = await self.auth.request(
                "POST",
                f"{self.fill_region.url}/bs/rlu/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/actions",
                headers=headers,
                data=data,
            )
            request_id: str = ExtendedDict(rsp).getr("rluActionResponse.requestId", "")
            await self._async_check_request(
                f"{self.fill_region.url}/bs/rlu/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/requests/{request_id}/status",
                "lock vehicle" if lock else "unlock vehicle",
                REQUEST_SUCCESSFUL,
                REQUEST_FAILED,
                "requestStatusResponse.status",
            )
        elif self.api_level["lock"] == 2:
            b_action = "lock" if lock else "unlock"
            headers = await self.auth.async_get_headers(token_type="idk")
            data = await self.auth.request(
                "POST",
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/access/{b_action}",
                headers=headers,
                json={"spin": self.spin},
            )
            if isinstance(data, dict):
                request_id = ExtendedDict(data).getr("data.requestID", "")
                await self._async_pending_request(
                    f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
                    "refresh vehicle data",
                    SUCCESSFUL,
                    FAILED,
                    request_id,
                )

    async def async_set_climatisation(
        self,
        action: bool,
        heater_source: Literal["electric", "auxiliary", "automatic"] = "electric",
        temperature: float = 19.5,
    ) -> None:
        """Set Climatisation."""

        async def post_req(headers: dict[str, Any], data: Any) -> None:
            rsp = await self.auth.request(
                "POST",
                f"{self.fill_region.url}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions",
                headers=headers,
                data=data,
            )
            actionid = ExtendedDict(rsp).getr("action.actionId", "")
            await self._async_check_request(
                f"{self.fill_region.url}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions/{actionid}",
                "start climatisation" if action else "stop climatisation",
                SUCCEEDED,
                FAILED,
                "action.actionState",
            )

        security_token = await self._async_get_security_token(
            "rclima_v1/operations/"
            + (
                "P_START_CLIMA_EL"
                if heater_source == "electric"
                else "P_START_CLIMA_AU"
            )
        )

        if self.api_level["climatisation"] == 3:
            # standard format with header source, e.g. E-Tron
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml;charset=utf-8",
                security_token,
                heater_source != "electric",
            )
            data: str | dict[str, Any] = (
                f'<?xml version="1.0" encoding="UTF-8"?><action><type>{"startClimatisation" if action else "stopClimatisation"}</type><settings><heaterSource>'
                + heater_source
                + "</heaterSource></settings></action>"
            )
            await post_req(headers, data)

        elif self.api_level["climatisation"] == 4:
            b_action = "start" if action else "stop"
            data = {
                "targetTemperature": temperature,
                "targetTemperatureUnit": "celsius",
                "climatisationWithoutExternalPower": True,
                "climatizationAtUnlock": True,
                "windowHeatingEnabled": True,
                "zoneFrontLeftEnabled": True,
                "zoneFrontRightEnabled": True,
            }
            headers = await self.auth.async_get_headers(token_type="idk")
            rsp = await self.auth.request(
                "POST",
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/climatisation/{b_action}",
                headers=headers,
                json=data,
            )
            request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
            await self._async_pending_request(
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
                "refresh vehicle data",
                SUCCESSFUL,
                FAILED,
                request_id,
            )

        else:
            headers = await self.auth.async_get_action_headers(
                "application/json",
                security_token,
                heater_source != "electric",
            )
            data = (
                {
                    "action": {
                        "type": "startClimatisation",
                        "settings": {
                            "targetTemperature": 2940,
                            "climatisationWithoutHVpower": True,
                            "heaterSource": heater_source,
                            "climaterElementSettings": {
                                "isClimatisationAtUnlock": False,
                                "isMirrorHeatingEnabled": True,
                            },
                        },
                    }
                }
                if action
                else {"action": {"type": "stopClimatisation"}}
            )
            data = json.dumps(data)
            await post_req(headers, data)

    async def async_set_climatisation_settings(
        self,
        temperature: float = 19.5,
        heater_source: Literal["electric", "auxiliary", "automatic"] = "electric",
        glass_heating: bool = True,
        seat_fl: bool = False,
        seat_fr: bool = False,
        seat_rl: bool = False,
        seat_rr: bool = False,
    ) -> None:
        """Set Climatisation temperature."""

        async def post_req(headers: dict[str, Any], data: Any) -> None:
            rsp = await self.auth.request(
                "POST",
                f"{self.fill_region.url}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions",
                headers=headers,
                data=data,
            )
            actionid = ExtendedDict(rsp).getr("action.actionId", "")
            await self._async_check_request(
                f"{self.fill_region.url}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions/{actionid}",
                "set target temperature",
                SUCCEEDED,
                FAILED,
                "action.actionState",
            )

        # Default Temp
        temperature = int(round(temperature, 1) * 10 + 2731)

        # Construct Zone Settings
        zone_settings = [
            {"value": {"isEnabled": seat_fl, "position": "frontLeft"}},
            {"value": {"isEnabled": seat_fr, "position": "frontRight"}},
            {"value": {"isEnabled": seat_rl, "position": "rearLeft"}},
            {"value": {"isEnabled": seat_rr, "position": "rearRight"}},
        ]

        if self.api_level["climatisation"] == 3:
            # standard format with header source, e.g. E-Tron
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml;charset=utf-8", None
            )
            data: str | dict[str, Any] = (
                '<?xml version="1.0" encoding="UTF-8"?><action><type>setSettings</type><settings>'
                + f"<targetTemperature>{temperature}</targetTemperature>"
                + "<climatisationWithoutHVpower>false</climatisationWithoutHVpower>"
                + f"<heaterSource>{heater_source}</heaterSource>"
                + "</settings></action>"
            )
            await post_req(headers, data)

        elif self.api_level["climatisation"] == 4:
            data = {
                "targetTemperature": temperature,
                "targetTemperatureUnit": "celsius",
                "climatisationWithoutExternalPower": True,
                "climatizationAtUnlock": True,
                "windowHeatingEnabled": True,
                "zoneFrontLeftEnabled": True,
                "zoneFrontRightEnabled": True,
            }
            headers = await self.auth.async_get_headers(token_type="idk")
            rsp = await self.auth.request(
                "POST",
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/climatisation/settings",
                headers=headers,
                json=data,
            )
            request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
            await self._async_pending_request(
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
                "refresh vehicle data",
                SUCCESSFUL,
                FAILED,
                request_id,
            )

        else:
            headers = await self.auth.async_get_action_headers("application/json", None)
            data = {
                "action": {
                    "type": "setSettings",
                    "settings": {
                        "targetTemperature": temperature,
                        "climatisationWithoutHVpower": True,
                        "heaterSource": heater_source,
                        "climaterElementSettings": {
                            "isClimatisationAtUnlock": False,
                            "isMirrorHeatingEnabled": glass_heating,
                            "zoneSettings": {"zoneSetting": zone_settings},
                        },
                    },
                }
            }
            data = json.dumps(data)
            await post_req(headers, data)

    async def set_auxiliary_climatisation(
        self, action: bool, duration: int = 60
    ) -> None:
        """Set pre heater."""

        async def post_req(headers: dict[str, Any], data: Any) -> None:
            await self.auth.request(
                "POST",
                f"{self.fill_region.url}/bs/rs/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/action",
                headers=headers,
                data=data,
            )

        security_token = await self._async_get_security_token(
            "rheating_v1/operations/" + ("P_QSACT" if action else "P_QSTOPACT")
        )

        if self.api_level["ventilation"] == 1:
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_0+xml", security_token
            )
            data: str | dict[str, Any] = (
                '<?xml version="1.0" encoding= "UTF-8" ?><performAction xmlns="http://audi.de/connect/rs">'
                + f'<quickstart><active>{"true" if action else "false"}</active></quickstart></performAction>'
            )
            await post_req(headers, data)

        elif self.api_level["ventilation"] == 2:
            b_action = "start" if action else "stop"
            data = {"spin": self.spin, "duration_min": duration} if b_action else {}
            headers = await self.auth.async_get_headers(token_type="idk")
            rsp = await self.auth.request(
                "POST",
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/auxiliaryheating/{b_action}",
                headers=headers,
                json=data,
            )
            request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
            await self._async_pending_request(
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
                "refresh vehicle data",
                SUCCESSFUL,
                FAILED,
                request_id,
            )

        else:
            headers = await self.auth.async_get_action_headers(
                "application/json", security_token
            )
            data = (
                {
                    "performAction": {
                        "quickstart": {
                            "startMode": "heating",
                            "active": True,
                            "climatisationDuration": duration,
                        }
                    }
                }
                if action
                else {"performAction": {"quickstop": {"active": False}}}
            )
            data = json.dumps(data)
            await post_req(headers, data)

    async def async_set_ventilation(self, action: bool, duration: int = 60) -> None:
        """Set ventilation."""

        async def post_req(headers: dict[str, Any], data: Any) -> None:
            await self.auth.request(
                "POST",
                f"{self.fill_region.url}/bs/rs/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/action",
                headers=headers,
                data=data,
            )

        security_token = await self._async_get_security_token(
            "rheating_v1/operations/" + ("P_QSACT" if action else "P_QSTOPACT")
        )
        if self.api_level["ventilation"] == 1:
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_0+xml", security_token
            )
            content = (
                (
                    "<active>true</active>"
                    + f"<climatisationDuration>{duration}</climatisationDuration>"
                    + "<startMode>ventilation</startMode>"
                )
                if action
                else "<active>false</active>"
            )
            data: str | dict[str, Any] = (
                '<?xml version="1.0" encoding="UTF-8" ?><performAction xmlns="http://audi.de/connect/rs">'
                f"<quickstart>{content}</quickstart></performAction>"
            )
            await post_req(headers, data)

        else:
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_2+json", security_token
            )
            data = (
                {
                    "performAction": {
                        "quickstart": {
                            "startMode": "ventilation",
                            "active": True,
                            "climatisationDuration": duration,
                        }
                    }
                }
                if action
                else {"performAction": {"quickstop": {"active": False}}}
            )
            data = json.dumps(data)
            await post_req(headers, data)

    async def async_set_charger(self, action: bool, timer: bool = False) -> None:
        """Set battery charger."""

        async def post_req(headers: dict[str, Any], data: Any) -> None:
            rsp = await self.auth.request(
                "POST",
                f"{self.fill_region.url}/bs/batterycharge/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/charger/actions",
                headers=headers,
                data=data,
            )

            actionid = ExtendedDict(rsp).getr("action.actionId", "")
            await self._async_check_request(
                f"{self.fill_region.url}/bs/batterycharge/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/charger/actions/{actionid}",
                "start charger" if action else "stop charger",
                SUCCEEDED,
                FAILED,
                "action.actionState",
            )

        if self.api_level["charger"] == 2:
            headers = await self.auth.async_get_action_headers("application/json", None)
            if action and timer:
                data: str | dict[str, Any] = {
                    "action": {
                        "type": "selectChargingMode",
                        "settings": {
                            "chargeModeSelection": {"value": "timerBasedCharging"},
                        },
                    }
                }
            elif action:
                data = {"action": {"type": "start"}}
            else:
                data = {"action": {"type": "stop"}}
            data = json.dumps(data)
            await post_req(headers, data)
        elif self.api_level["charger"] == 3:
            headers = await self.auth.async_get_action_headers("application/json", None)
            data = {
                "action": {
                    "type": "startBatteryCharging" if action else "stopBatteryCharging"
                }
            }
            data = json.dumps(data)
            await post_req(headers, data)

        elif self.api_level["charger"] == 4:
            b_action = "start" if action else "stop"
            headers = await self.auth.async_get_headers(token_type="idk")
            rsp = await self.auth.request(
                "POST",
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/charging/{b_action}",
                headers=headers,
            )
            request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
            await self._async_pending_request(
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
                "refresh vehicle data",
                SUCCESSFUL,
                FAILED,
                request_id,
            )

        else:
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.ChargerAction_v1_0_0+xml", None
            )
            data = f'<?xml version="1.0" encoding="UTF-8" ?><action><type>{"start" if action else "stop"}</type></action>'
            await post_req(headers, data)

    async def async_set_charging_settings(self, current: float = 32) -> None:
        """Set max current."""

        async def post_req(headers: dict[str, Any], data: Any) -> None:
            rsp = await self.auth.request(
                "POST",
                f"{self.fill_region.url}/bs/batterycharge/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/charger/actions",
                headers=headers,
                data=data,
            )
            actionid = ExtendedDict(rsp).getr("action.actionId", "")
            await self._async_check_request(
                f"{self.fill_region.url}/bs/batterycharge/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/charger/actions/{actionid}",
                "set charger max current",
                SUCCEEDED,
                FAILED,
                "action.actionState",
            )

        if self.api_level["charger"] == 2:
            headers = await self.auth.async_get_action_headers("application/json", None)
            data: str | dict[str, Any] = {
                "action": {
                    "settings": {"maxChargeCurrent": int(current)},
                    "type": "setSettings",
                }
            }
            data = json.dumps(data)
            await post_req(headers, data)

        elif self.api_level["charger"] == 4:
            data = {
                "maxChargeCurrentAC": current,
                "autoUnlockPlugWhenChargedAC": True,
                "targetSOC_pct": 100,
                "maxChargeCurrentAC_A": current,
            }
            headers = await self.auth.async_get_headers(token_type="idk")
            rsp = await self.auth.request(
                "PUT",
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/charging/settings",
                headers=headers,
                json=data,
            )
            request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
            await self._async_pending_request(
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
                "refresh vehicle data",
                SUCCESSFUL,
                FAILED,
                request_id,
            )

        else:
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.ChargerAction_v1_0_0+xml", None
            )
            data = (
                '<?xml version="1.0" encoding="UTF-8" ?><action><type>setSettings</type>'
                + f"<settings><maxChargeCurrent>{current}</maxChargeCurrent></settings></action>"
            )
            await post_req(headers, data)

    async def async_set_window_heating(self, action: bool) -> None:
        """Set window heating."""

        async def post_req(headers: dict[str, Any], data: Any) -> None:
            rsp = await self.auth.request(
                "POST",
                f"{self.fill_region.url}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions",
                headers=headers,
                data=data,
            )
            actionid = ExtendedDict(rsp).getr("action.actionId", "")
            await self._async_check_request(
                f"{self.fill_region.url}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions/{actionid}",
                "start window heating" if action else "stop window heating",
                SUCCEEDED,
                FAILED,
                "action.actionState",
            )

        if self.api_level["windows_heating"] == 2:
            headers = await self.auth.async_get_action_headers("application/json", None)
            data: str | dict[str, Any] = {
                "action": {
                    "type": "startWindowHeating" if action else "stopWindowHeating"
                }
            }
            data = json.dumps(data)
            await post_req(headers, data)
        elif self.api_level["windows_heating"] == 3:
            b_action = "start" if action else "stop"
            headers = await self.auth.async_get_headers(token_type="idk")
            rsp = await self.auth.request(
                "POST",
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/windowheating/{b_action}",
                headers=headers,
            )
            request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
            await self._async_pending_request(
                f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
                "refresh vehicle data",
                SUCCESSFUL,
                FAILED,
                request_id,
            )
        else:
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml", None
            )
            data = (
                '<?xml version="1.0" encoding= "UTF-8" ?>'
                + f"<action><type>{'startWindowHeating' if action else 'stopWindowHeating'}</type></action>"
            )
            await post_req(headers, data)

    async def async_set_honkflash(
        self, mode: Literal["honk", "flash"], duration: int = 15
    ) -> None:
        """Set honk and flash light."""
        if self.position:
            headers = await self.auth.async_get_action_headers("application/json", None)
            data: dict[str, Any] = {
                "honkAndFlashRequest": {
                    "serviceOperationCode": "HONK_AND_FLASH"
                    if mode == "honk"
                    else "FLASH_ONLY",
                    "serviceDuration": duration,
                    "userPosition": {
                        "latitude": self.position["latitude"],
                        "longitude": self.position["longitude"],
                    },
                }
            }
            await self.auth.request(
                "POST",
                f"{self.fill_region.url}/bs/rhf/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/honkAndFlash",
                headers=headers,
                json=data,
            )

    async def async_set_care_mode_setttings(
        self, data: Literal["activated", "deactivated"]
    ) -> None:
        """Execute battery care mode actions."""
        headers = await self.auth.async_get_headers(token_type="idk")
        rsp = await self.auth.request(
            "PUT",
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/charging/care/settings",
            headers=headers,
            json={"batteryCareMode": data},
        )
        request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
        await self._async_pending_request(
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
            "refresh vehicle data",
            SUCCESSFUL,
            FAILED,
            request_id,
        )

    async def async_set_readiness_battery_support(self, action: bool) -> None:
        """Execute readiness battery support actions."""
        headers = await self.auth.async_get_headers(token_type="idk")
        rsp = await self.auth.request(
            "PUT",
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/readiness/batterysupport",
            headers=headers,
            json={"batterySupportEnabled": action is True},
        )
        request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
        await self._async_pending_request(
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
            "refresh vehicle data",
            SUCCESSFUL,
            FAILED,
            request_id,
        )

    async def async_set_climatisation_timers(self, timer_id: int, enable: bool) -> None:
        """Execute climatisation timers actions."""

        timers = self.climatisation_timers.get("climatisation_timers_status", [])
        for index, timer in enumerate(timers):
            if timer.get("id", 0) == timer_id:
                timers[index]["enabled"] = enable

        data = {"timers": timers}
        headers = await self.auth.async_get_headers(token_type="idk")
        rsp = await self.auth.request(
            "PUT",
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/climatisation/timers",
            headers=headers,
            json=data,
        )
        request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
        await self._async_pending_request(
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
            "refresh vehicle data",
            SUCCESSFUL,
            FAILED,
            request_id,
        )

    async def async_set_auxiliary_heating_timers(self, data: Any) -> None:
        """ "Execute auxiliary heating timers actions."""
        headers = await self.auth.async_get_headers(token_type="idk")
        rsp = await self.auth.request(
            "PUT",
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/auxiliaryheating/timers",
            headers=headers,
            json=data,
        )
        request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
        await self._async_pending_request(
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
            "refresh vehicle data",
            SUCCESSFUL,
            FAILED,
            request_id,
        )

    async def async_set_departure_profiles(self, data: Any) -> None:
        """Execute departure timers actions."""
        headers = await self.auth.async_get_headers(token_type="idk")
        rsp = await self.auth.request(
            "PUT",
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/departure/profiles",
            headers=headers,
            json=data,
        )
        request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
        await self._async_pending_request(
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
            "refresh vehicle data",
            SUCCESSFUL,
            FAILED,
            request_id,
        )

    async def async_set_departure_timer(self, timer_id: int, enable: bool) -> None:
        """Execute departure timers actions."""

        # TO DO
        timers = ""
        profiles = ""

        data = {"timers": timers, "profiles": profiles}
        headers = await self.auth.async_get_headers(token_type="idk")
        rsp = await self.auth.request(
            "PUT",
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/departure/timers",
            headers=headers,
            json=data,
        )
        request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
        await self._async_pending_request(
            f"{self.uris['mdk_url']}vehicle/v1/vehicles/{self.vin}/pendingrequests",
            "refresh vehicle data",
            SUCCESSFUL,
            FAILED,
            request_id,
        )

    async def async_refresh_vehicle_data(self) -> None:
        """Refresh vehicle data."""
        headers = await self.auth.async_get_headers(token_type="idk")
        rsp = await self.auth.request(
            "POST",
            f"{self.uris['cv_url']}/vehicles/{self.vin}/vehiclewakeup",
            headers=headers,
        )
        request_id: str = ExtendedDict(rsp).getr("data.requestID", "")
        await self._async_pending_request(
            f"{self.uris['cv_url']}/vehicles/{self.vin}/pendingrequests",
            "refresh vehicle data",
            SUCCESSFUL,
            FAILED,
            request_id,
        )

    async def _async_pending_request(
        self, url: str, action: str, success: str, failed: str, request_id: str
    ) -> None:
        """Check request succeeded."""
        status_good = False
        for _ in range(MAX_RESPONSE_ATTEMPTS):
            await asyncio.sleep(REQUEST_STATUS_SLEEP)

            headers = await self.auth.async_get_headers(token_type="idk")
            rsp = await self.auth.request("GET", url, headers=headers)

            status = None
            if rsp and (data := rsp.get("data")):
                for item in data:
                    if item.get("id") == request_id:
                        status = item.get("status")
                        break

            if status is None or (failed is not None and status == failed):
                raise HttpRequestError(f"Cannot {action}, return code '{status}'")

            if status == success:
                status_good = True
                break

        if status_good is False:
            raise TimeoutExceededError(f"Cannot {action}, operation timed out")

    async def async_check_spin(self) -> bool:
        """Determine SPIN state to prevent lockout due to wrong SPIN."""
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.request(
            "GET",
            f"{self.uris['mdk_url']}vehicle/v1/spin/state",
            headers=headers,
        )
        remainingTries = data.get("remainingTries")
        if remainingTries is None:
            raise AudiException("Couldn't determine S-PIN state.")

        if remainingTries < 3:
            raise AudiException(
                "Remaining tries for S-PIN is < 3. Bailing out for security reasons. "
                "To resume operation, please make sure the correct S-PIN has been set in the integration "
                "and then use the correct S-PIN once via the Volkswagen app."
            )

        return True

    async def _async_check_request(
        self, url: str, action: str, success: str, failed: str, path: str
    ) -> None:
        """Check request succeeded."""
        status_good = False
        for _ in range(MAX_RESPONSE_ATTEMPTS):
            await asyncio.sleep(REQUEST_STATUS_SLEEP)

            headers = await self.auth.async_get_headers(token_type="mbb")
            rsp = await self.auth.request("GET", url, headers=headers)

            status = ExtendedDict(rsp).getr(path)

            if status is None or (failed is not None and status == failed):
                raise HttpRequestError(f"Cannot {action}, return code '{status}'")

            if status == success:
                status_good = True
                break

        if status_good is False:
            raise TimeoutExceededError(f"Cannot {action}, operation timed out")

    async def _async_get_security_token(self, action: str) -> str:
        """Get security token."""
        if self.spin is None:
            logger.error("Security PIN not found")
            return ""

        # Challenge
        headers = await self.auth.async_get_headers(token_type="mbb", okhttp=True)
        rsp = await self.auth.request(
            "GET",
            f"{self.fill_region.url_setter}/rolesrights/authorization/v2/vehicles/{self.vin}/services/{action}/security-pin-auth-requested",
            headers=headers,
        )
        rsp = ExtendedDict(rsp)
        sec_token: str = rsp.getr("securityPinAuthInfo.securityToken")
        challenge: str = rsp.getr(
            "securityPinAuthInfo.securityPinTransmission.challenge"
        )

        # Response
        headers["Content-Type"] = "application/json"
        data = {
            "securityPinAuthentication": {
                "securityPin": {
                    "challenge": challenge,
                    "securityPinHash": spin_hash(self.spin, challenge),
                },
                "securityToken": sec_token,
            }
        }
        response = await self.auth.request(
            "POST",
            f"{self.fill_region.url_setter}/rolesrights/authorization/v2/security-pin-auth-completed",
            headers=headers,
            json=data,
        )
        return cast(str, response.get("securityToken", ""))
