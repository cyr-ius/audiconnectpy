"""Audi actions."""
from __future__ import annotations

import asyncio
from typing import Any, Literal

from .const import (
    BRAND,
    FAILED,
    MAX_RESPONSE_ATTEMPTS,
    REQUEST_FAILED,
    REQUEST_STATUS_SLEEP,
    REQUEST_SUCCESSFUL,
    SUCCEEDED,
)
from .exceptions import HttpRequestError, TimeoutExceededError
from .helpers import ExtendedDict, spin_hash


class AudiActions:
    """Actions on vehicle."""

    async def async_set_lock(self, lock: bool) -> None:
        """Set lock."""
        data = '<?xml version="1.0" encoding= "UTF-8" ?>'
        data += f'<rluAction xmlns="http://audi.de/connect/rlu"><action>{"lock" if lock else "unlock"}</action></rluAction>'
        headers = await self.auth.async_get_headers(
            token_type="idk",
            headers={
                "Content-Type": "application/vnd.vwg.mbb.RemoteLockUnlock_v1_0_0+xml"
            },
            security_token=await self._async_get_security_token(
                "rlu_v1/operations/" + ("LOCK" if lock else "UNLOCK")
            ),
        )

        rsp = await self.auth.post(
            f"{self.url}/bs/rlu/v1/{BRAND}/{self.country}/vehicles/{self.vin}/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        rsp = rsp if rsp else ExtendedDict()
        request_id = rsp.getr("rluActionResponse.requestId")
        await self._async_check_request(
            f"{self.url}/bs/rlu/v1/{BRAND}/{self.country}/vehicles/{self.vin}/requests/{request_id}/status",
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
        headers = await self.auth.async_get_action_headers("application/json", None)
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

        rsp = await self.auth.post(
            f"{self.url}/bs/climatisation/v1/{BRAND}/{self.country}/vehicles/{self.vin}/climater/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        rsp = rsp if rsp else ExtendedDict()
        actionid = rsp.getr("action.actionId")
        await self._async_check_request(
            f"{self.url}/bs/climatisation/v1/{BRAND}/{self.country}/vehicles/{self.vin}/climater/actions/{actionid}",
            "start climatisation" if start else "stop climatisation",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_climater_temp(
        self,
        temperature: float = 19.5,
        heater_source: Literal["electric", "auxiliary", "automatic"] = "electric",
    ) -> None:
        """Set Climatisation temperature."""
        temperature = int(round(temperature, 1) * 10 + 2731)
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
                        "isMirrorHeatingEnabled": True,
                    },
                },
            }
        }
        rsp = await self.auth.post(
            f"{self.url}/bs/climatisation/v1/{BRAND}/{self.country}/vehicles/{self.vin}/climater/actions",
            headers=headers,
            data=data,
        )
        rsp = rsp if rsp else ExtendedDict()
        actionid = rsp.getr("action.actionId")
        await self._async_check_request(
            f"{self.url}/bs/climatisation/v1/{BRAND}/{self.country}/vehicles/{self.vin}/climater/actions/{actionid}",
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
        data = '<?xml version="1.0" encoding= "UTF-8" ?>'
        data += '<performAction xmlns="http://audi.de/connect/rs">'
        data += f'<quickstart><active>{"true" if start else "false"}</active></quickstart></performAction>'
        headers = await self.auth.async_get_action_headers(
            "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_0+xml", security_token
        )

        # headers = await self.auth.async_get_action_headers(
        #     "application/json", security_token
        # )
        # data = (
        #     {
        #         "performAction": {
        #             "quickstart": {
        #                 "startMode": "heating",
        #                 "active": True,
        #                 "climatisationDuration": duration,
        #             }
        #         }
        #     }
        #     if start
        #     else {"performAction": {"quickstop": {"active": False}}}
        # )

        await self.auth.post(
            f"{self.url}/bs/rs/v1/{BRAND}/{self.country}/vehicles/{self.vin}/action",
            headers=headers,
            data=data,
            use_json=False,
        )

    async def async_set_ventilation(self, start: bool, duration: int = 60) -> None:
        """Set ventilation."""
        security_token = await self._async_get_security_token(
            "rheating_v1/operations/" + ("P_QSACT" if start else "P_QSTOPACT")
        )
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

        await self.auth.post(
            f"{self.url}/bs/rs/v1/{BRAND}/{self.country}/vehicles/{self.vin}/action",
            headers=headers,
            data=data,
        )

    async def async_set_battery_charger(self, start: bool, timer: bool = False) -> None:
        """Set battery charger."""
        headers = await self.auth.async_get_action_headers("application/json", None)
        if start and timer:
            data = {
                "action": {
                    "type": "selectChargingMode",
                    "settings": {
                        "chargeModeSelection": {
                            "value": "timerBasedCharging",
                            "isMirrorHeatingEnabled": True,
                        },
                    },
                }
            }
        elif start:
            data = {"action": {"type": "start"}}
        else:
            data = {"action": {"type": "stop"}}

        rsp = await self.auth.post(
            f"{self.url}/bs/batterycharge/v1/{BRAND}/{self.country}/vehicles/{self.vin}/charger/actions",
            headers=headers,
            data=data,
        )
        rsp = rsp if rsp else ExtendedDict()
        actionid = rsp.getr("action.actionId")
        await self._async_check_request(
            f"{self.url}/bs/batterycharge/v1/{BRAND}/{self.country}/vehicles/{self.vin}/charger/actions/{actionid}",
            "start charger" if start else "stop charger",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_charger_max(self, current: float = 32) -> None:
        """Set max current."""
        data = {
            "action": {
                "settings": {"maxChargeCurrent": int(current)},
                "type": "setSettings",
            }
        }
        headers = await self.auth.async_get_action_headers("application/json", None)
        rsp = await self.auth.post(
            f"{self.url}/bs/batterycharge/v1/{BRAND}/{self.country}/vehicles/{self.vin}/charger/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        rsp = rsp if rsp else ExtendedDict()
        actionid = rsp.getr("action.actionId")
        await self._async_check_request(
            f"{self.url}/bs/batterycharge/v1/{BRAND}/{self.country}/vehicles/{self.vin}/charger/actions/{actionid}",
            "set charger max current",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_window_heating(self, start: bool) -> None:
        """Set window heating."""
        data = '<?xml version="1.0" encoding= "UTF-8" ?>'
        data += f"<action><type>{'startWindowHeating' if start else 'stopWindowHeating'}</type></action>"
        headers = await self.auth.async_get_action_headers(
            "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml", None
        )
        rsp = await self.auth.post(
            f"{self.url}/bs/climatisation/v1/{BRAND}/{self.country}/vehicles/{self.vin}/climater/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        rsp = rsp if rsp else ExtendedDict()
        actionid = rsp.getr("action.actionId")
        await self._async_check_request(
            f"{self.url}/bs/climatisation/v1/{BRAND}/{self.country}/vehicles/{self.vin}/climater/actions/{actionid}",
            "start window heating" if start else "stop window heating",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_honkflash(
        self, mode: Literal["honk", "flash"], duration: int = 15
    ) -> None:
        """Set honk and flash light."""
        # OpenHab "FLASH_ONLY","HONK_AND_FLASH"
        rsp_position = await self.auth.get(
            f"{self.url}/bs/cf/v1/{BRAND}/{self.country}/vehicles/{self.vin}/position"
        )
        rsp_position = rsp_position if rsp_position else ExtendedDict()
        position = rsp_position.get("findCarResponse.Position.carCoordinate")
        headers = await self.auth.async_get_action_headers("application/json", None)
        data = {
            "honkAndFlashRequest": {
                "serviceOperationCode": "HONK_AND_FLASH"
                if mode == "honk"
                else "FLASH_ONLY",
                "serviceDuration": duration,
                "userPosition": {
                    "latitude": position["latitude"],
                    "longitude": position["longitude"],
                },
            }
        }
        await self.auth.post(
            f"{self.url}/bs/rhf/v1/{BRAND}/{self.country}/vehicles/{self.vin}/honkAndFlash",
            headers=headers,
            data=data,
        )

    async def async_refresh_vehicle_data(self) -> None:
        """Refresh vehicle data."""
        data = await self.auth.post(
            f"{self.url}/bs/vsr/v1/{BRAND}/{self.country}/vehicles/{self.vin}/requests"
        )
        data = data if data else ExtendedDict()
        request_id: str = data.getr("CurrentVehicleDataResponse.requestId")
        await self._async_check_request(
            f"{self.url}/bs/vsr/v1/{BRAND}/{self.country}/vehicles/{self.vin}/requests/{request_id}/jobstatus",
            "refresh vehicle data",
            REQUEST_SUCCESSFUL,
            REQUEST_FAILED,
            "requestStatusResponse.status",
        )

    async def _async_check_request(
        self, url: str, action: str, success: str, failed: str, path: str
    ) -> None:
        """Check request succeeded."""
        stauts_good = False
        for _ in range(MAX_RESPONSE_ATTEMPTS):
            await asyncio.sleep(REQUEST_STATUS_SLEEP)

            rsp = await self.auth.get(url)

            status = rsp.getr(path)

            if status is None or (failed is not None and status == failed):
                raise HttpRequestError(("Cannot %s, return code '%s'", action, status))

            if status == success:
                stauts_good = True
                break

        if stauts_good is False:
            raise TimeoutExceededError(("Cannot %s, operation timed out", action))

    async def _async_get_security_token(self, action: str) -> Any:
        """Get security token."""
        self.spin = "" if self.spin is None else self.spin

        # Challenge
        headers = await self.auth.async_get_headers(token_type="mbb", okhttp=True)
        rsp = await self.auth.get(
            f"{self.url_setter}/rolesrights/authorization/v2/vehicles/{self.vin}/services/{action}/security-pin-auth-requested",
            headers=headers,
        )
        rsp = rsp if rsp else ExtendedDict()
        sec_token = rsp.getr("securityPinAuthInfo.securityToken")
        challenge: str = rsp.getr(
            "securityPinAuthInfo.securityPinTransmission.challenge"
        )

        # Response
        security_pin_hash = spin_hash(self.spin, challenge)
        data = {
            "securityPinAuthentication": {
                "securityPin": {
                    "challenge": challenge,
                    "securityPinHash": security_pin_hash,
                },
                "securityToken": sec_token,
            }
        }

        headers["Content-Type"] = "application/json"
        body = await self.auth.post(
            f"{self.url_setter}/rolesrights/authorization/v2/security-pin-auth-completed",
            headers=headers,
            data=data,
        )
        return body["securityToken"]
