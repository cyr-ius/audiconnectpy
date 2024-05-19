"""Vehicle class."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from typing import Any, Iterable, Literal, cast

from mashumaro import DataClassDictMixin, field_options

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
from .exceptions import HttpRequestError, TimeoutExceededError
from .helpers import ExtendedDict, remove_value, spin_hash
from .model import Information, Location, Model, Position

logger = logging.getLogger(__name__)


class Globals:
    """Global variables."""

    def __init__(self, unit: str) -> None:
        """Initilaze."""
        global UNIT_SYSTEM
        UNIT_SYSTEM = f"{unit}"  # type: ignore


@dataclass
class Vehicles(DataClassDictMixin):  # type: ignore
    """Vehicles."""

    user_vehicles: list[Vehicle] = field(
        metadata=field_options(alias="userVehicles"), default_factory=list
    )


@dataclass
class Vehicle(DataClassDictMixin):  # type: ignore
    """Vehicle class."""

    vin: str
    csid: str
    nickname: str | None = None
    last_access: datetime | None = None
    uris: dict[str, str] = field(init=False)
    auth: Any = field(init=False)
    spin: str | None = field(init=False, default=None)
    infos: Information | None = field(
        metadata=field_options(alias="vehicle"), default=None
    )
    capabilities: list[str] | None = field(init=False, default=None)
    position: Position | None = field(init=False, default=None)
    location: Location | None = field(init=False, default=None)

    @property
    def api_level(self) -> dict[str, int]:
        """Return API Level."""
        return {
            "climatisation": 2,  # 2 or 3
            "ventilation": 1,  # 1 or other
            "charger": 1,  # 1 or 2 or 3 (json)
            "windows_heating": 1,  # 1 or 2 (json)
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
        data = await self.async_get_selectivestatus()
        data = remove_value(data)
        vehicle_model = Model.from_dict(data)

        for attr in vehicle_model.to_dict():
            obj = getattr(vehicle_model, attr, None)
            setattr(self, attr, obj)

        self.last_access = vehicle_model.access.access_status.car_captured_timestamp

        # Capabilities
        capabilities = await self.async_get_capabilities()
        self.capabilities = capabilities.get("capabilities")

        # Position
        position = await self.async_get_position()
        self.position = Position.from_dict(position.get("data"))

        # Locations (here.com)
        location = await self.async_get_location()
        self.location = Location.from_dict(
            {
                "proprietaries": [
                    item
                    for item in location.get("data", [])
                    if "proprietaryData" not in item
                ],
                "addresses": [
                    item
                    for item in location.get("data", [])
                    if "proprietaryData" in item
                ],
            }
        )

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
            f"{self.uris['cv_url']}/vehicles/{self.vin}/parkingposition",
            headers=headers,
        )
        return data

    async def async_get_capabilities(self) -> Any:
        """Get capabilities."""
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.request(
            "GET",
            f"{self.uris['cv_url']}/vehicles/{self.vin}/capabilities",
            headers=headers,
        )
        return data

    async def async_get_selectivestatus(self, jobs: Iterable[str] | None = None) -> Any:
        """Get capabilities."""
        if jobs is None:
            headers = await self.auth.async_get_headers(token_type="idk")
            capabilities = await self.auth.request(
                "GET",
                f"{self.uris['cv_url']}/vehicles/{self.vin}/selectivestatus?jobs=userCapabilities",
                headers=headers,
            )
            values: list[dict[str, Any]] = ExtendedDict(capabilities).getr(
                "userCapabilities.capabilitiesStatus.value", []
            )
            self.capabilities: list[str] = [
                str(d) for capability in values if (d := capability.get("id"))
            ]

        str_jobs = ",".join(self.capabilities)  # type: ignore
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.request(
            "GET",
            f"{self.uris['cv_url']}/vehicles/{self.vin}/selectivestatus?jobs={str_jobs},userCapabilities",
            headers=headers,
        )
        return data

    async def async_set_lock(self, lock: bool) -> None:
        """Set lock."""
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
            f"{self.uris['url']}/bs/rlu/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/actions",
            headers=headers,
            data=data,
        )
        request_id = ExtendedDict(rsp).getr("rluActionResponse.requestId", "")
        await self._async_check_request(
            f"{self.uris['url']}/bs/rlu/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/requests/{request_id}/status",
            "lock vehicle" if lock else "unlock vehicle",
            REQUEST_SUCCESSFUL,
            REQUEST_FAILED,
            "requestStatusResponse.status",
        )

    async def async_set_climater(
        self,
        start: bool,
        heater_source: Literal["electric", "auxiliary", "automatic"] = "electric",
    ) -> None:
        """Set Climatisation."""
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
                f'<?xml version="1.0" encoding="UTF-8"?><action><type>{"startClimatisation" if start else "stopClimatisation"}</type><settings><heaterSource>'
                + heater_source
                + "</heaterSource></settings></action>"
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
                if start
                else {"action": {"type": "stopClimatisation"}}
            )
            data = json.dumps(data)

        rsp = await self.auth.request(
            "POST",
            f"{self.uris['url']}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions",
            headers=headers,
            data=data,
        )
        actionid = ExtendedDict(rsp).getr("action.actionId", "")
        await self._async_check_request(
            f"{self.uris['url']}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions/{actionid}",
            "start climatisation" if start else "stop climatisation",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_climater_temp(
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
        rsp = await self.auth.request(
            "POST",
            f"{self.uris['url']}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions",
            headers=headers,
            data=data,
        )
        actionid = ExtendedDict(rsp).getr("action.actionId", "")
        await self._async_check_request(
            f"{self.uris['url']}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions/{actionid}",
            "set target temperature",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_pre_heating(self, start: bool, duration: int = 60) -> None:
        """Set pre heater."""
        security_token = await self._async_get_security_token(
            "rheating_v1/operations/" + ("P_QSACT" if start else "P_QSTOPACT")
        )
        if self.api_level["ventilation"] == 1:
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_0+xml", security_token
            )
            data: str | dict[str, Any] = (
                '<?xml version="1.0" encoding= "UTF-8" ?><performAction xmlns="http://audi.de/connect/rs">'
                + f'<quickstart><active>{"true" if start else "false"}</active></quickstart></performAction>'
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
                if start
                else {"performAction": {"quickstop": {"active": False}}}
            )
            data = json.dumps(data)

        await self.auth.request(
            "POST",
            f"{self.uris['url']}/bs/rs/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/action",
            headers=headers,
            data=data,
        )

    async def async_set_ventilation(self, start: bool, duration: int = 60) -> None:
        """Set ventilation."""
        security_token = await self._async_get_security_token(
            "rheating_v1/operations/" + ("P_QSACT" if start else "P_QSTOPACT")
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
                if start
                else "<active>false</active>"
            )
            data: str | dict[str, Any] = (
                '<?xml version="1.0" encoding="UTF-8" ?><performAction xmlns="http://audi.de/connect/rs">'
                f"<quickstart>{content}</quickstart></performAction>"
            )
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
                if start
                else {"performAction": {"quickstop": {"active": False}}}
            )
            data = json.dumps(data)

        await self.auth.request(
            "POST",
            f"{self.uris['url']}/bs/rs/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/action",
            headers=headers,
            data=data,
        )

    async def async_set_battery_charger(self, start: bool, timer: bool = False) -> None:
        """Set battery charger."""
        if self.api_level["charger"] == 2:
            headers = await self.auth.async_get_action_headers("application/json", None)
            if start and timer:
                data: str | dict[str, Any] = {
                    "action": {
                        "type": "selectChargingMode",
                        "settings": {
                            "chargeModeSelection": {"value": "timerBasedCharging"},
                        },
                    }
                }
            elif start:
                data = {"action": {"type": "start"}}
            else:
                data = {"action": {"type": "stop"}}
            data = json.dumps(data)
        elif self.api_level["charger"] == 3:
            headers = await self.auth.async_get_action_headers("application/json", None)
            data = {
                "action": {
                    "type": "startBatteryCharging" if start else "stopBatteryCharging"
                }
            }
            data = json.dumps(data)
        else:
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.ChargerAction_v1_0_0+xml", None
            )
            data = f'<?xml version="1.0" encoding="UTF-8" ?><action><type>{"start" if start else "stop"}</type></action>'

        rsp = await self.auth.request(
            "POST",
            f"{self.uris['url']}/bs/batterycharge/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/charger/actions",
            headers=headers,
            data=data,
        )
        actionid = ExtendedDict(rsp).getr("action.actionId", "")
        await self._async_check_request(
            f"{self.uris['url']}/bs/batterycharge/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/charger/actions/{actionid}",
            "start charger" if start else "stop charger",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_charger_max(self, current: float = 32) -> None:
        """Set max current."""
        if self.api_level["charger"] == 2:
            headers = await self.auth.async_get_action_headers("application/json", None)
            data: str | dict[str, Any] = {
                "action": {
                    "settings": {"maxChargeCurrent": int(current)},
                    "type": "setSettings",
                }
            }
            data = json.dumps(data)

        else:
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.ChargerAction_v1_0_0+xml", None
            )
            data = (
                '<?xml version="1.0" encoding="UTF-8" ?><action><type>setSettings</type>'
                + f"<settings><maxChargeCurrent>{current}</maxChargeCurrent></settings></action>"
            )

        rsp = await self.auth.request(
            "POST",
            f"{self.uris['url']}/bs/batterycharge/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/charger/actions",
            headers=headers,
            data=data,
        )
        actionid = ExtendedDict(rsp).getr("action.actionId", "")
        await self._async_check_request(
            f"{self.uris['url']}/bs/batterycharge/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/charger/actions/{actionid}",
            "set charger max current",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_window_heating(self, start: bool) -> None:
        """Set window heating."""
        if self.api_level["windows_heating"] == 2:
            headers = await self.auth.async_get_action_headers("application/json", None)
            data: str | dict[str, Any] = {
                "action": {
                    "type": "startWindowHeating" if start else "stopWindowHeating"
                }
            }
            data = json.dumps(data)
        else:
            headers = await self.auth.async_get_action_headers(
                "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml", None
            )
            data = (
                '<?xml version="1.0" encoding= "UTF-8" ?>'
                + f"<action><type>{'startWindowHeating' if start else 'stopWindowHeating'}</type></action>"
            )
        rsp = await self.auth.request(
            "POST",
            f"{self.uris['url']}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions",
            headers=headers,
            data=data,
        )
        actionid = ExtendedDict(rsp).getr("action.actionId", "")
        await self._async_check_request(
            f"{self.uris['url']}/bs/climatisation/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/climater/actions/{actionid}",
            "start window heating" if start else "stop window heating",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

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
                        "latitude": self.position.latitude,
                        "longitude": self.position.longitude,
                    },
                }
            }
            await self.auth.request(
                "POST",
                f"{self.uris['url']}/bs/rhf/v1/{BRAND}/{self.uris['country']}/vehicles/{self.vin}/honkAndFlash",
                headers=headers,
                json=data,
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
        stauts_good = False
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
                raise HttpRequestError(("Cannot %s, return code '%s'", action, status))

            if status == success:
                stauts_good = True
                break

        if stauts_good is False:
            raise TimeoutExceededError(("Cannot %s, operation timed out", action))

    async def _async_check_request(
        self, url: str, action: str, success: str, failed: str, path: str
    ) -> None:
        """Check request succeeded."""
        stauts_good = False
        for _ in range(MAX_RESPONSE_ATTEMPTS):
            await asyncio.sleep(REQUEST_STATUS_SLEEP)

            headers = await self.auth.async_get_headers(token_type="mbb")
            rsp = await self.auth.request("GET", url, headers=headers)

            status = ExtendedDict(rsp).getr(path)

            if status is None or (failed is not None and status == failed):
                raise HttpRequestError(("Cannot %s, return code '%s'", action, status))

            if status == success:
                stauts_good = True
                break

        if stauts_good is False:
            raise TimeoutExceededError(("Cannot %s, operation timed out", action))

    async def _async_get_security_token(self, action: str) -> str:
        """Get security token."""
        if self.spin is None:
            logger.error("Security PIN not found")
            return ""

        # Challenge
        headers = await self.auth.async_get_headers(token_type="mbb", okhttp=True)
        rsp = await self.auth.request(
            "GET",
            f"{self.uris['url_setter']}/rolesrights/authorization/v2/vehicles/{self.vin}/services/{action}/security-pin-auth-requested",
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
            f"{self.uris['url_setter']}/rolesrights/authorization/v2/security-pin-auth-completed",
            headers=headers,
            json=data,
        )
        return cast(str, response.get("securityToken", ""))
