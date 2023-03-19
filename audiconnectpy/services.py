"""Call url service."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from hashlib import sha512
from typing import Any

from .auth import Auth
from .exceptions import AudiException, HttpRequestError, TimeoutExceededError
from .models import (
    ChargerDataResponse,
    ClimaterDataResponse,
    PositionDataResponse,
    PreheaterDataResponse,
    TripDataResponse,
    VehicleDataResponse,
)
from .util import get_attr, jload, to_byte_array

MAX_RESPONSE_ATTEMPTS = 10
REQUEST_STATUS_SLEEP = 10

SUCCEEDED = "succeeded"
FAILED = "failed"
REQUEST_SUCCESSFUL = "request_successful"
REQUEST_FAILED = "request_failed"

_LOGGER = logging.getLogger(__name__)


class AudiService:
    """Audi service."""

    def __init__(self, auth: Auth, country: str, spin: int) -> None:
        """Initialize."""
        self._auth = auth
        self._country: str = "DE" if country is None else country
        self._type = "Audi"
        self._spin = spin
        self._home_region: dict[str, str] = {}
        self._home_region_setter: dict[str, str] = {}

    async def async_refresh_vehicle_data(self, vin: str) -> None:
        """Refresh vehicle data."""
        home_region = await self._async_get_home_region(vin.upper())
        data = await self._auth.post(
            f"{home_region}/fs-car/bs/vsr/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/requests"
        )

        request_id: str = get_attr(data, "CurrentVehicleDataResponse.requestId")
        vin = get_attr(data, "CurrentVehicleDataResponse.vin")

        await self.async_check_request_succeeded(
            f"{home_region}/fs-car/bs/vsr/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/requests/{request_id}/jobstatus",
            "refresh vehicle data",
            REQUEST_SUCCESSFUL,
            REQUEST_FAILED,
            "requestStatusResponse.status",
        )

    async def async_get_preheater(self, vin: str) -> PreheaterDataResponse:
        """Get preheater data."""
        home_region = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{home_region}/fs-car/bs/rs/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/status"
        )
        _LOGGER.debug("PREHEATER: %s", data)
        return PreheaterDataResponse(data)

    async def async_get_stored_vehicle_data(self, vin: str) -> VehicleDataResponse:
        """Get store data."""
        home_region = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{home_region}/fs-car/bs/vsr/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/status"
        )
        _LOGGER.debug("STORED: %s", data)
        return VehicleDataResponse(data, self._spin is not None)

    async def async_get_stored_vehicle_data_v2(self, vin: str) -> VehicleDataResponse:
        """Get store data v2."""
        home_region = "https://emea.bff.cariad.digital"
        headers = await self._auth.async_get_simple_headers()
        data = await self._auth.request(
            "GET",
            f"{home_region}/vehicle/v1/vehicles/{vin.upper()}/selectivestatus?jobs=all",
            headers=headers,
            data=None,
        )
        _LOGGER.debug("STORED: %s", data)
        return VehicleDataResponse(data, self._spin is not None)

    async def async_get_charger(self, vin: str) -> ChargerDataResponse:
        """Get charger data."""
        home_region = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{home_region}/fs-car/bs/batterycharge/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/charger"
        )
        _LOGGER.debug("CHARGER: %s", data)
        return ChargerDataResponse(data)

    async def async_get_climater(self, vin: str) -> ClimaterDataResponse:
        """Get climater data."""
        home_region = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{home_region}/fs-car/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater"
        )
        _LOGGER.debug("CLIMATER: %s", data)
        return ClimaterDataResponse(data)

    async def async_get_stored_position(self, vin: str) -> PositionDataResponse:
        """Get position data."""
        home_region = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{home_region}/fs-car/bs/cf/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/position"
        )
        _LOGGER.debug("POSITION: %s", data)
        return PositionDataResponse(data)

    async def async_get_stored_position_v2(self, vin: str) -> VehicleDataResponse:
        """Get position data v2."""
        home_region = "https://emea.bff.cariad.digital"
        headers = await self._auth.async_get_simple_headers()
        data = await self._auth.request(
            "GET",
            f"{home_region}/vehicle/v1/vehicles/{vin.upper()}/parkingposition",
            headers=headers,
            data=None,
        )
        _LOGGER.debug("POSITION: %s", data)
        return VehicleDataResponse(data, self._spin is not None)

    async def async_get_capabilities(self, vin: str) -> VehicleDataResponse:
        """Get capabilities."""
        home_region = "https://emea.bff.cariad.digital"
        headers = await self._auth.async_get_simple_headers()
        data = await self._auth.request(
            "GET",
            f"{home_region}/vehicle/v1/vehicles/{vin.upper()}/capabilities",
            headers=headers,
            data=None,
        )
        _LOGGER.debug("CAPABILITES: %s", data)
        return VehicleDataResponse(data, self._spin is not None)

    async def async_get_operations_list(self, vin: str) -> Any:
        """Get operation data."""
        home_region_setter = await self._async_get_home_region_setter(vin.upper())
        data = await self._auth.get(
            f"{home_region_setter}/api/rolesrights/operationlist/v3/vehicles/{vin.upper()}"
        )
        _LOGGER.debug("OPERATIONS: %s", data)
        return data

    async def async_get_timer(self, vin: str) -> Any:
        """Get timer."""
        home_region = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{home_region}/fs-car/bs/departuretimer/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/timer"
        )
        _LOGGER.debug("TIMER: %s", data)
        return data

    async def async_get_vehicles(self) -> Any:
        """Get all vehicles."""
        data = await self._auth.get(
            f"https://msg.volkswagen.de/fs-car/usermanagement/users/v1/{self._type}/{self._country}/vehicles"
        )
        _LOGGER.debug("VEHICLES: %s", data)
        return data

    async def async_get_vehicle_information(self) -> Any:
        """Get vehicle information."""
        headers = await self._auth.async_get_information_headers()
        req_data = {
            "query": "query vehicleList {\n userVehicles {\n vin\n mappingVin\n vehicle { core { modelYear\n }\n media { shortName\n longName }\n }\n csid\n commissionNumber\n type\n devicePlatform\n mbbConnect\n userRole {\n role\n }\n vehicle {\n classification {\n driveTrain\n }\n }\n nickname\n }\n}"
        }
        rep_rsptxt = await self._auth.request(
            "POST",
            "https://app-api.live-my.audi.com/vgql/v1/graphql",
            json.dumps(req_data),
            headers=headers,
            allow_redirects=False,
        )
        vins = jload(rep_rsptxt)
        if "data" not in vins:
            raise AudiException("Invalid json in vehicle information")
        _LOGGER.debug("INFO: %s", vins["data"])
        return vins["data"]

    async def async_get_vehicle_data(self, vin: str) -> Any:
        """Get vehicle data."""
        home_region = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{home_region}/fs-car/vehicleMgmt/vehicledata/v2/{self._type}/{self._country}/vehicles/{vin.upper()}/"
        )
        _LOGGER.debug("DATA: %s", data)
        return data

    async def async_get_tripdata(
        self, vin: str, kind: str
    ) -> tuple[TripDataResponse, TripDataResponse]:
        """Get trip data."""
        home_region = await self._async_get_home_region(vin.upper())
        headers = await self._auth.async_get_trip_headers()
        td_reqdata = {
            "type": "list",
            "from": "1970-01-01T00:00:00Z",
            # "from":(datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": (datetime.utcnow() + timedelta(minutes=90)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }
        data = await self._auth.request(
            "GET",
            f"{home_region}/api/bs/tripstatistics/v1/vehicles/{vin.upper()}/tripdata/{kind}",
            None,
            params=td_reqdata,
            headers=headers,
        )
        td_sorted = sorted(
            get_attr(data, "tripDataList.tripData"),
            key=lambda k: k["overallMileage"],  # type: ignore[no-any-return]
            reverse=True,
        )
        td_current = td_sorted[0]
        td_reset_trip = None

        for trip in td_sorted:
            if (td_current["startMileage"] - trip["startMileage"]) > 2:
                td_reset_trip = trip
                break
            td_current["tripID"] = trip["tripID"]
            td_current["startMileage"] = trip["startMileage"]

        _LOGGER.debug("TRIP: %s", td_current)
        _LOGGER.debug("TRIP: %s", td_reset_trip)

        return TripDataResponse(td_current), TripDataResponse(td_reset_trip)

    async def _async_fill_home_region(self, vin: str) -> None:
        """Fill region."""
        self._home_region[vin] = "https://msg.volkswagen.de"
        self._home_region_setter[vin] = "https://mal-1a.prd.ece.vwg-connect.com"
        try:
            res = await self._auth.get(
                f"https://mal-1a.prd.ece.vwg-connect.com/api/cs/vds/v1/vehicles/{vin}/homeRegion"
            )
            if (
                uri := get_attr(res, "homeRegion.baseUri.content")
            ) is not None and uri != "https://mal-1a.prd.ece.vwg-connect.com/api":
                self._home_region_setter[vin] = uri.split("/api")[0]
                self._home_region[vin] = self._home_region_setter[vin].replace(
                    "mal-", "fal-"
                )
        except Exception:  # pylint: disable=broad-except
            pass

    async def _async_get_home_region(self, vin: str) -> str:
        """Get region."""
        if self._home_region.get(vin) is not None:
            return self._home_region[vin]

        await self._async_fill_home_region(vin)

        return self._home_region[vin]

    async def _async_get_home_region_setter(self, vin: str) -> str:
        """Get region setter."""
        if self._home_region_setter.get(vin) is not None:
            return self._home_region_setter[vin]

        await self._async_fill_home_region(vin)

        return self._home_region_setter[vin]

    async def _async_get_security_token(self, vin: str, action: str) -> Any:
        """Get security token."""
        self._spin = "" if self._spin is None else self._spin
        home_region_setter = await self._async_get_home_region_setter(vin.upper())

        # Challenge
        headers = await self._auth.async_get_security_headers()
        body = await self._auth.request(
            "GET",
            f"{home_region_setter}/api/rolesrights/authorization/v2/vehicles/{vin.upper()}/services/{action}/security-pin-auth-requested",
            headers=headers,
            data=None,
        )

        sec_token = get_attr(body, "securityPinAuthInfo.securityToken")
        challenge: str = get_attr(
            body, "securityPinAuthInfo.securityPinTransmission.challenge"
        )

        # Response
        security_pin_hash = self._generate_security_pin_hash(challenge)
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
        body = await self._auth.request(
            "POST",
            f"{home_region_setter}/api/rolesrights/authorization/v2/security-pin-auth-completed",
            headers=headers,
            data=json.dumps(data),
        )
        return body["securityToken"]

    async def async_set_lock(self, vin: str, lock: bool) -> None:
        """Set lock."""
        home_region = await self._async_get_home_region(vin.upper())
        security_token = await self._async_get_security_token(
            vin, "rlu_v1/operations/" + ("LOCK" if lock else "UNLOCK")
        )
        action = "lock" if lock else "unlock"
        data = f'<?xml version="1.0" encoding= "UTF-8" ?><rluAction xmlns="http://audi.de/connect/rlu"><action>{action}</action></rluAction>'
        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.RemoteLockUnlock_v1_0_0+xml", security_token
        )

        res = await self._auth.request(
            "POST",
            f"{home_region}/fs-car/bs/rlu/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/actions",
            headers=headers,
            data=data,
        )

        request_id = get_attr(res, "rluActionResponse.requestId")
        await self.async_check_request_succeeded(
            f"{home_region}/fs-car/bs/rlu/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/requests/{request_id}/status",
            "lock vehicle" if lock else "unlock vehicle",
            REQUEST_SUCCESSFUL,
            REQUEST_FAILED,
            "requestStatusResponse.status",
        )

    async def async_set_battery_charger(
        self, vin: str, start: bool, timer: bool
    ) -> None:
        """Set charger."""
        home_region = await self._async_get_home_region(vin.upper())
        if start and timer:
            data = '{ "action": { "type": "selectChargingMode", "settings": { "chargeModeSelection": { "value": "timerBasedCharging" } } }}'
        elif start:
            data = '{ "action": { "type": "start" }}'
        else:
            data = '{ "action": { "type": "stop" }}'

        headers = await self._auth.async_get_action_headers("application/json", None)
        res = await self._auth.request(
            "POST",
            f"{home_region}/fs-car/bs/batterycharge/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/charger/actions",
            headers=headers,
            data=data,
        )

        actionid = get_attr(res, "action.actionId")
        await self.async_check_request_succeeded(
            f"{home_region}/fs-car/bs/batterycharge/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/charger/actions/{actionid}",
            "start charger" if start else "stop charger",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_climatisation(self, vin: str, start: bool) -> None:
        """Set Climatisation."""
        home_region = await self._async_get_home_region(vin.upper())
        if start:
            data = '{"action":{"type": "startClimatisation","settings": {"targetTemperature": 2940,"climatisationWithoutHVpower": true,"heaterSource": "electric","climaterElementSettings": {"isClimatisationAtUnlock": false, "isMirrorHeatingEnabled": true,}}}}'
        else:
            data = '{"action":{"type": "stopClimatisation"}}'

        headers = await self._auth.async_get_action_headers("application/json", None)
        res = await self._auth.request(
            "POST",
            f"{home_region}/fs-car/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater/actions",
            headers=headers,
            data=data,
        )
        actionid = get_attr(res, "action.actionId")
        await self.async_check_request_succeeded(
            f"{home_region}/fs-car/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater/actions/{actionid}",
            "start climatisation" if start else "stop climatisation",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_window_heating(self, vin: str, start: bool) -> None:
        """Set window heating."""
        home_region = await self._async_get_home_region(vin.upper())
        action = "startWindowHeating" if start else "stopWindowHeating"
        data = f'<?xml version="1.0" encoding= "UTF-8" ?><action><type>{action}</type></action>'

        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml", None
        )
        res = await self._auth.request(
            "POST",
            f"{home_region}/fs-car/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater/actions",
            headers=headers,
            data=data,
        )
        actionid = get_attr(res, "action.actionId")
        await self.async_check_request_succeeded(
            f"{home_region}/fs-car/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater/actions/{actionid}",
            "start window heating" if start else "stop window heating",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_pre_heater(self, vin: str, activate: bool) -> None:
        """Set pre heater."""
        home_region = await self._async_get_home_region(vin.upper())
        security_token = await self._async_get_security_token(
            vin, "rheating_v1/operations/P_QSACT"
        )
        action = "true" if activate else "false"
        input_xml = f'<performAction xmlns="http://audi.de/connect/rs"><quickstart><active>{action}</active></quickstart></performAction>'
        data = f'<?xml version="1.0" encoding= "UTF-8" ?>{input_xml}'

        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_0+xml", security_token
        )
        await self._auth.request(
            "POST",
            f"{home_region}/fs-car/bs/rs/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/action",
            headers=headers,
            data=data,
        )

    async def async_check_request_succeeded(
        self, url: str, action: str, success: str, failed: str, path: str
    ) -> None:
        """Check request succeeded."""
        stauts_good = False
        for _ in range(MAX_RESPONSE_ATTEMPTS):
            await asyncio.sleep(REQUEST_STATUS_SLEEP)

            res = await self._auth.get(url)

            status = get_attr(res, path)

            if status is None or (failed is not None and status == failed):
                raise HttpRequestError(("Cannot %s, return code '%s'", action, status))

            if status == success:
                stauts_good = True
                break

        if stauts_good is False:
            raise TimeoutExceededError(("Cannot %s, operation timed out", action))

    def _generate_security_pin_hash(self, challenge: str) -> str:
        """Generate security pin hash."""
        pin = to_byte_array(str(self._spin))
        byte_challenge = to_byte_array(challenge)
        b_pin = bytes(pin + byte_challenge)
        return sha512(b_pin).hexdigest().upper()
