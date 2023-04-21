"""Call url service."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from hashlib import sha512
from typing import Any, Literal

from .auth import Auth
from .exceptions import AudiException, HttpRequestError, TimeoutExceededError
from .models import (
    ChargerDataResponse,
    ClimaterDataResponse,
    DestinationDataResponse,
    HistoryDataResponse,
    PositionDataResponse,
    PreheaterDataResponse,
    TripDataResponse,
    UsersDataResponse,
    VehicleDataResponse,
)
from .util import get_attr, to_byte_array

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
        self._target_temp: int = 1950
        self._heater_source: str = "electric"
        self._control_duration: int = 60

    async def async_get_vehicles(self) -> Any:
        """Get all vehicles."""
        url = await self._async_get_home_region("")
        data = await self._auth.get(
            f"{url}/usermanagement/users/v1/{self._type}/{self._country}/vehicles"
        )
        _LOGGER.debug("VEHICLES: %s", data)
        return data

    async def async_get_vehicle_details(self, vin: str) -> Any:
        """Get vehicle data."""
        url = await self._async_get_home_region(vin.upper())
        headers = await self._auth.async_get_headers()
        headers.update(
            {
                "Accept": "application/vnd.vwg.mbb.vehicleDataDetail_v2_1_0+json, application/vnd.vwg.mbb.genericError_v1_0_2+json"
            }
        )
        data = await self._auth.get(
            f"{url}/vehicleMgmt/vehicledata/v2/{self._type}/{self._country}/vehicles/{vin.upper()}/",
            headers=headers,
        )
        _LOGGER.debug("DETAILS: %s", data)
        return data

    async def async_get_vehicle(self, vin: str) -> VehicleDataResponse:
        """Get store data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/vsr/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/status"
        )
        _LOGGER.debug("STORED: %s", data)
        return VehicleDataResponse(data, self._spin is not None)

    async def async_refresh_vehicle_data(self, vin: str) -> None:
        """Refresh vehicle data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.post(
            f"{url}/bs/vsr/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/requests"
        )

        request_id: str = get_attr(data, "CurrentVehicleDataResponse.requestId")
        vin = get_attr(data, "CurrentVehicleDataResponse.vin")

        await self.async_check_request_succeeded(
            f"{url}/bs/vsr/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/requests/{request_id}/jobstatus",
            "refresh vehicle data",
            REQUEST_SUCCESSFUL,
            REQUEST_FAILED,
            "requestStatusResponse.status",
        )

    async def async_get_stored_position(self, vin: str) -> PositionDataResponse:
        """Get position data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/cf/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/position"
        )
        _LOGGER.debug("POSITION: %s", data)
        return PositionDataResponse(data)

    async def async_get_destinations(self, vin: str) -> DestinationDataResponse:
        """Get destination data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/destinationfeedservice/mydestinations/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/destinations"
        )
        _LOGGER.debug("DESTINATION: %s", data)
        return DestinationDataResponse(data)

    async def async_get_history(self, vin: str) -> HistoryDataResponse:
        """Get history data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/dwap/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/history"
        )
        _LOGGER.debug("HISTORY: %s", data)
        return HistoryDataResponse(data)

    async def async_get_vehicule_users(self, vin: str) -> UsersDataResponse:
        """Get ufers of vehicle."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(f"{url}/bs/uic/v1/{vin.upper()}/users")
        _LOGGER.debug("USERS: %s", data)
        return UsersDataResponse(data)

    async def async_get_charger(self, vin: str) -> ChargerDataResponse:
        """Get charger data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/batterycharge/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/charger"
        )
        _LOGGER.debug("CHARGER: %s", data)
        return ChargerDataResponse(data)

    async def async_get_tripdata(
        self, vin: str, kind: str
    ) -> tuple[TripDataResponse, TripDataResponse]:
        """Get trip data."""
        url = await self._async_get_home_region(vin.upper())
        headers = await self._auth.async_get_headers()
        td_reqdata = {
            "type": "list",
            "from": "1970-01-01T00:00:00Z",
            # "from":(datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": (datetime.utcnow() + timedelta(minutes=90)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }
        data = await self._auth.get(
            f"{url}/bs/tripstatistics/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/tripdata/{kind}",
            params=td_reqdata,
            headers=headers,
        )
        td_sorted = sorted(
            get_attr(data, "tripDataList.tripData"),
            key=lambda k: k["overallMileage"],  # type: ignore[no-any-return]
            reverse=True,
        )
        td_current = td_sorted[0]
        td_reset_trip = {}

        for trip in td_sorted:
            if (td_current["startMileage"] - trip["startMileage"]) > 2:
                td_reset_trip = trip
                break
            td_current["tripID"] = trip["tripID"]
            td_current["startMileage"] = trip["startMileage"]

        _LOGGER.debug("TRIP: %s", td_current)
        _LOGGER.debug("TRIP: %s", td_reset_trip)

        return TripDataResponse(td_current), TripDataResponse(td_reset_trip)

    async def async_get_operations_list(self, vin: str) -> Any:
        """Get operation data."""
        url = await self._async_get_home_region_setter(vin.upper())
        data = await self._auth.get(
            f"{url}/rolesrights/operationlist/v3/vehicles/{vin.upper()}"
        )
        _LOGGER.debug("OPERATIONS: %s", data)
        return data

    async def async_get_climater(self, vin: str) -> ClimaterDataResponse:
        """Get climater data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater"
        )
        _LOGGER.debug("CLIMATER: %s", data)
        return ClimaterDataResponse(data)

    async def async_get_preheater(self, vin: str) -> PreheaterDataResponse:
        """Get Heater/Ventilation data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/rs/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/status"
        )
        _LOGGER.debug("PREHEATER: %s", data)
        return PreheaterDataResponse(data)

    async def async_get_climater_timer(self, vin: str) -> Any:
        """Get timer."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/departuretimer/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/timer"
        )
        _LOGGER.debug("TIMER: %s", data)
        return data

    async def async_get_capabilities(self, vin: str) -> VehicleDataResponse:
        """Get capabilities."""
        url = "https://emea.bff.cariad.digital"
        headers = await self._auth.async_get_simple_headers()
        data = await self._auth.get(
            f"{url}/vehicle/v1/vehicles/{vin.upper()}/capabilities", headers=headers
        )
        _LOGGER.debug("CAPABILITES: %s", data)
        return VehicleDataResponse(data, self._spin is not None)

    async def async_get_vehicle_information(self) -> Any:
        """Get vehicle information."""
        headers = await self._auth.async_get_information_headers()
        data = {
            "query": "query vehicleList {\n userVehicles {\n vin\n mappingVin\n vehicle { core { modelYear\n }\n media { shortName\n longName }\n }\n csid\n commissionNumber\n type\n devicePlatform\n mbbConnect\n userRole {\n role\n }\n vehicle {\n classification {\n driveTrain\n }\n }\n nickname\n }\n}"
        }
        resp = await self._auth.post(
            "https://app-api.live-my.audi.com/vgql/v1/graphql",
            data=data,
            headers=headers,
            allow_redirects=False,
        )
        if "data" not in resp:
            raise AudiException("Invalid json in vehicle information")
        _LOGGER.debug("INFO: %s", resp["data"])
        return resp["data"]

    async def async_get_honkflash(self, vin: str) -> Any:
        """Get Honk & Flash status."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/rhf/v1/{self._type}/{self._country}/configuration"
        )
        _LOGGER.debug("HONK & FLash: %s", data)
        return data

    async def async_get_personal_data(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self._auth.profil_url}/customers/{self._auth.user_id}"
        headers = await self._auth.async_get_simple_headers()
        data = await self._auth.get(f"{url}/personalData", headers=headers)
        _LOGGER.debug("personalData: %s", data)
        return data

    async def async_get_real_car_data(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self._auth.profil_url}/customers/{self._auth.user_id}"
        headers = await self._auth.async_get_simple_headers()
        data = await self._auth.get(f"{url}/realCarData", headers=headers)
        _LOGGER.debug("realCarData: %s", data)
        return data

    async def async_get_mbb_status(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self._auth.profil_url}/customers/{self._auth.user_id}"
        headers = await self._auth.async_get_simple_headers()
        data = await self._auth.get(f"{url}/mbbStatusData", headers=headers)
        _LOGGER.debug("mbbStatusData: %s", data)
        return data

    async def async_get_identity_data(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self._auth.profil_url}/customers/{self._auth.user_id}"
        headers = await self._auth.async_get_simple_headers()
        data = await self._auth.get(f"{url}/identityData", headers=headers)
        _LOGGER.debug("identityData: %s", data)
        return data

    # async def async_get_users(self, vin: str) -> Any:
    #     """Get users."""
    #     url = "https://userinformationservice.apps.emea.vwapps.io/iaa"
    #     headers = await self._auth.async_get_simple_headers()
    #     data = await self._auth.get(f"{url}/uic/v1/vin/{vin.upper()}/users", headers=headers)
    #     _LOGGER.debug("Users: %s", data)
    #     return data

    async def async_get_fences(self, vin: str) -> Any:
        """Get fences."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/geofencing/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/geofencingAlerts"
        )
        _LOGGER.debug("geofencing: %s", data)
        return data

    async def async_get_fences_config(self, vin: str) -> Any:
        """Get fences configuration."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/geofencing/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/geofencingConfiguration"
        )
        _LOGGER.debug("geofencing: %s", data)
        return data

    async def async_get_speed_alert(self, vin: str) -> Any:
        """Get speed alert."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/speedalert/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/speedAlerts"
        )
        _LOGGER.debug("geofencing: %s", data)
        return data

    async def async_get_speed_config(self, vin: str) -> Any:
        """Get speed alert configuration."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/speedalert/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/speedAlertConfiguration"
        )
        _LOGGER.debug("geofencing: %s", data)
        return data

    async def async_lock(self, vin: str, lock: bool) -> None:
        """Set lock."""
        # OpenHab "lock","unlock"
        url = await self._async_get_home_region(vin.upper())
        security_token = await self._async_get_security_token(
            vin, "rlu_v1/operations/" + ("LOCK" if lock else "UNLOCK")
        )
        input_xml = f'<rluAction xmlns="http://audi.de/connect/rlu"><action>{"lock" if lock else "unlock"}</action></rluAction>'
        data = f'<?xml version="1.0" encoding= "UTF-8" ?>{input_xml}'
        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.RemoteLockUnlock_v1_0_0+xml", security_token
        )

        res = await self._auth.post(
            f"{url}/bs/rlu/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/actions",
            headers=headers,
            data=data,
            use_json=False,
        )

        request_id = get_attr(res, "rluActionResponse.requestId")
        await self.async_check_request_succeeded(
            f"{url}/bs/rlu/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/requests/{request_id}/status",
            "lock vehicle" if lock else "unlock vehicle",
            REQUEST_SUCCESSFUL,
            REQUEST_FAILED,
            "requestStatusResponse.status",
        )

    async def async_climater(self, vin: str, start: bool) -> None:
        """Set Climatisation."""
        # OpenHab "startClimater","stopClimater"
        url = await self._async_get_home_region(vin.upper())
        action = (
            "P_START_CLIMA_EL"
            if self._heater_source == "electric"
            else "P_START_CLIMA_AU"
        )
        security_token = await self._async_get_security_token(
            vin, "rclima_v1/operations/" + (action if start else "P_QSTOPACT")
        )
        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml", security_token
        )
        input_xml = f"<action><type>startClimatisation</type><settings><heaterSource>{self._heater_source}</heaterSource></settings></action>"
        data = f'<?xml version="1.0" encoding="UTF-8"?>{input_xml}'

        # headers = await self._auth.async_get_action_headers(
        #     "application/vnd.vwg.mbb.ClimaterAction_v1_0_2+json", security_token
        # )
        # data = (
        #     {
        #         "action": {
        #             "type": "startClimatisation",
        #             "settings": {
        #                 "climatisationWithoutHVpower": "without_hv_power",
        #                 "heaterSource": self._heater_source,
        #             },
        #         }
        #     }
        #     if start
        #     else {"action": {"type": "stopClimatisation"}}
        # )

        res = await self._auth.post(
            f"{url}/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        actionid = get_attr(res, "action.actionId")
        await self.async_check_request_succeeded(
            f"{url}/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater/actions/{actionid}",
            "start climatisation" if start else "stop climatisation",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_climater_temp(
        self,
        vin: str,
        temperature: float,
        source: Literal["electric", "auxiliary", "automatic"],
    ) -> None:
        """Set Climatisation temperature."""
        temperature = int(round(temperature, 1) * 10 + 2731)
        url = await self._async_get_home_region(vin.upper())
        # input_xml = f"<action><type>setSettings</type><settings><targetTemperature>{current}</targetTemperature>\
        # <climatisationWithoutHVpower>false</climatisationWithoutHVpower>\
        # <heaterSource>{self._heater_source}</heaterSource></settings></action>"
        # data = f'<?xml version="1.0" encoding= "UTF-8" ?>{input_xml}'
        # headers = await self._auth.async_get_action_headers(
        #     "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml", None
        # )
        data = json.dumps(
            {
                "action": {
                    "type": "setSettings",
                    "settings": {
                        "targetTemperature": temperature,
                        "climatisationWithoutHVpower": True,
                        "heaterSource": source,
                        "climaterElementSettings": {
                            "isClimatisationAtUnlock": False,
                            "isMirrorHeatingEnabled": True,
                        },
                    },
                }
            }
        )
        headers = await self._auth.async_get_action_headers("application/json", None)
        res = await self._auth.post(
            f"{url}/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater/actions",
            headers=headers,
            data=data,
        )
        actionid = get_attr(res, "action.actionId")
        await self.async_check_request_succeeded(
            f"{url}/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater/actions/{actionid}",
            "set target temperature",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_pre_heating(self, vin: str, start: bool) -> None:
        """Set pre heater."""
        # OpenHab "startPreHeat","stopPreHeat"
        url = await self._async_get_home_region(vin.upper())
        security_token = await self._async_get_security_token(
            vin, "rheating_v1/operations/" + ("P_QSACT" if start else "P_QSTOPACT")
        )
        # input_xml = f'<performAction xmlns="http://audi.de/connect/rs">\
        #     <quickstart><active>{"true" if start else "false"}</active></quickstart></performAction>'
        # data = f'<?xml version="1.0" encoding= "UTF-8" ?>{input_xml}'
        # headers = await self._auth.async_get_action_headers(
        #     "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_0+xml", security_token
        # )

        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_2+json", security_token
        )
        data = (
            {
                "performAction": {
                    "quickstart": {
                        "startMode": "heating",
                        "active": True,
                        "climatisationDuration": self._control_duration,
                    }
                }
            }
            if start
            else {"performAction": {"quickstop": {"active": False}}}
        )

        await self._auth.post(
            f"{url}/bs/rs/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/action",
            headers=headers,
            data=data,
        )

    async def async_ventilation(self, vin: str, start: bool) -> None:
        """Set ventilation."""
        # OpenHab "startVentilation","stopVentilation"
        url = await self._async_get_home_region(vin.upper())
        security_token = await self._async_get_security_token(
            vin, "rheating_v1/operations/" + ("P_QSACT" if start else "P_QSTOPACT")
        )
        # input_xml = f'<performAction xmlns="http://audi.de/connect/rs"><quickstart><active>{"true" if start else "false"}</active>\
        #     <climatisationDuration>{self._control_duration}</climatisationDuration>\
        #     <startMode>ventilation</startMode></quickstart></performAction>'
        # data = f'<?xml version="1.0" encoding= "UTF-8" ?>{input_xml}'
        # headers = await self._auth.async_get_action_headers(
        #     "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_0+xml", security_token
        # )

        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_2+json", security_token
        )
        data = (
            {
                "performAction": {
                    "quickstart": {
                        "startMode": "ventilation",
                        "active": True,
                        "climatisationDuration": self._control_duration,
                    }
                }
            }
            if start
            else {"performAction": {"quickstop": {"active": False}}}
        )

        await self._auth.post(
            f"{url}/bs/rs/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/action",
            headers=headers,
            data=data,
        )

    async def async_charger(self, vin: str, start: bool) -> None:
        """Set charger."""
        # OpenHab "startCharging","stopCharging"
        url = await self._async_get_home_region(vin.upper())
        action = "true" if start else "false"
        input_xml = f"<action><type>{action}</type></action>"
        data = f'<?xml version="1.0" encoding= "UTF-8" ?>{input_xml}'
        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.ChargerAction_v1_0_0+xml", None
        )
        res = await self._auth.post(
            f"{url}/bs/batterycharge/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/charger/actions",
            headers=headers,
            data=data,
            use_json=False,
        )

        actionid = get_attr(res, "action.actionId")
        await self.async_check_request_succeeded(
            f"{url}/bs/batterycharge/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/charger/actions/{actionid}",
            "start charger" if start else "stop charger",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_charger_max(self, vin: str, current: int = 32) -> None:
        """Set max current."""
        _LOGGER.debug("Setting max charging current to %sA", current)
        url = await self._async_get_home_region(vin.upper())
        input_xml = f"<action><type>setSettings</type><settings><maxChargeCurrent>{current}</maxChargeCurrent></settings></action>"
        data = f'<?xml version="1.0" encoding= "UTF-8" ?>{input_xml}'

        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.ChargerAction_v1_0_0+xml", None
        )
        res = await self._auth.post(
            f"{url}/bs/batterycharge/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/charger/action",
            headers=headers,
            data=data,
            use_json=False,
        )
        actionid = get_attr(res, "action.actionId")
        await self.async_check_request_succeeded(
            f"{url}/bs/batterycharge/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/charger/actions/{actionid}",
            "set charger max current",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def set_heater_source(
        self, mode: Literal["electric", "auxiliary", "automatic"]
    ) -> None:
        """Set max current."""
        _LOGGER.debug("Set heater source for climatisation to %s", mode)
        if mode in ["electric", "auxiliary", "automatic"]:
            self._heater_source = mode

    async def async_window_heating(self, vin: str, start: bool) -> None:
        """Set window heating."""
        # OpenHab "startWindowHeating","stopWindowHeating"
        url = await self._async_get_home_region(vin.upper())
        input_xml = f"<action><type>{'startWindowHeating' if start else 'stopWindowHeating'}</type></action>"
        data = f'<?xml version="1.0" encoding= "UTF-8" ?>{input_xml}'

        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml", None
        )
        res = await self._auth.post(
            f"{url}/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        actionid = get_attr(res, "action.actionId")
        await self.async_check_request_succeeded(
            f"{url}/bs/climatisation/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/climater/actions/{actionid}",
            "start window heating" if start else "stop window heating",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def set_control_duration(self, current: int) -> None:
        """Set max current."""
        _LOGGER.debug("Set ventilation/pre-heat duration to %s", current)
        self._control_duration = current

    async def async_honkflash(
        self, vin: str, mode: Literal["honk", "flash"], duration: int = 15
    ) -> None:
        """Set honk and flash light."""
        # OpenHab "flash","honk"
        url = await self._async_get_home_region(vin.upper())

        rsp_position = await self._auth.get(
            f"{url}/bs/cf/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/position"
        )
        position = (
            rsp_position.get("findCarResponse", {})
            .get("Position", {})
            .get("carCoordinate")
        )

        headers = await self._auth.async_get_action_headers("application/json", None)
        data = {
            "honkAndFlashRequest": {
                "serviceOperationCode": mode == "honk",
                "serviceDuration": duration,
                "userPosition": {
                    "latitude": position["latitude"],
                    "longitude": position["longitude"],
                },
            }
        }
        await self._auth.post(
            f"{url}/bs/rhf/v1/{self._type}/{self._country}/vehicles/{vin.upper()}/honkAndFlash",
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

    async def _async_fill_home_region(self, vin: str) -> None:
        """Fill region."""
        self._home_region[vin] = "https://msg.volkswagen.de/fs-car"
        self._home_region_setter[vin] = "https://mal-1a.prd.ece.vwg-connect.com/api"
        try:
            res = await self._auth.get(
                f"{self._home_region_setter[vin]}/cs/vds/v1/vehicles/{vin}/homeRegion"
            )
            uri = get_attr(res, "homeRegion.baseUri.content")
            if uri and uri != self._home_region_setter[vin]:
                self._home_region[vin] = uri.replace("mal-", "fal-").replace(
                    "/api", "/fs-car"
                )
                self._home_region_setter[vin] = uri
        except Exception:  # pylint: disable=broad-except
            pass
        _LOGGER.debug(
            "Url changed: %s - %s",
            self._home_region[vin],
            self._home_region_setter[vin],
        )

    async def _async_get_home_region(self, vin: str) -> str:
        """Get region."""
        if self._home_region.get(vin):
            return self._home_region[vin]
        await self._async_fill_home_region(vin)
        return self._home_region[vin]

    async def _async_get_home_region_setter(self, vin: str) -> str:
        """Get region setter."""
        if self._home_region_setter.get(vin):
            return self._home_region_setter[vin]
        await self._async_fill_home_region(vin)
        return self._home_region_setter[vin]

    async def _async_get_security_token(self, vin: str, action: str) -> Any:
        """Get security token."""
        self._spin = "" if self._spin is None else self._spin
        url = await self._async_get_home_region_setter(vin.upper())

        # Challenge
        headers = await self._auth.async_get_security_headers()
        body = await self._auth.request(
            "GET",
            f"{url}/rolesrights/authorization/v2/vehicles/{vin.upper()}/services/{action}/security-pin-auth-requested",
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
            f"{url}/rolesrights/authorization/v2/security-pin-auth-completed",
            headers=headers,
            data=json.dumps(data),
        )
        return body["securityToken"]
