"""Call url service."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from hashlib import sha512
from typing import Any, Literal

from .auth import Auth
from .exceptions import AudiException, HttpRequestError, TimeoutExceededError
from .helpers import ExtendedDict, to_byte_array
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

MAX_RESPONSE_ATTEMPTS = 10
REQUEST_STATUS_SLEEP = 10

SUCCEEDED = "succeeded"
FAILED = "failed"
REQUEST_SUCCESSFUL = "request_successful"
REQUEST_FAILED = "request_failed"

_LOGGER = logging.getLogger(__name__)


class AudiService:
    """Audi service."""

    brand = "Audi"
    _home_region: dict[str, str] = {}
    _home_region_setter: dict[str, str] = {}
    _heater_source: dict[str, Literal["electric", "auxiliary", "automatic"]] = {}
    _control_duration: dict[str, int] = {}

    def __init__(self, auth: Auth, country: str, spin: int) -> None:
        """Initialize."""
        self._auth = auth
        self.country: str = "DE" if country is None else country
        self._spin = spin

    async def async_get_vehicles(self) -> Any:
        """Get all vehicles."""
        url = await self._async_get_home_region("")
        data = await self._auth.get(
            f"{url}/usermanagement/users/v1/{self.brand}/{self.country}/vehicles"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_vehicle_details(self, vin: str) -> Any:
        """Get vehicle data."""
        url = await self._async_get_home_region(vin.upper())
        accept = {
            "Accept": "application/vnd.vwg.mbb.vehicleDataDetail_v2_1_0+json, application/vnd.vwg.mbb.genericError_v1_0_2+json"
        }
        headers = await self._auth.async_get_headers(token_type="mbb", headers=accept)
        data = await self._auth.get(
            f"{url}/vehicleMgmt/vehicledata/v2/{self.brand}/{self.country}/vehicles/{vin.upper()}/",
            headers=headers,
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_vehicle(self, vin: str) -> VehicleDataResponse:
        """Get store data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/vsr/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/status"
        )
        data = data if data else ExtendedDict()
        return VehicleDataResponse(data, self._spin is not None)

    async def async_refresh_vehicle_data(self, vin: str) -> None:
        """Refresh vehicle data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.post(
            f"{url}/bs/vsr/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/requests"
        )
        data = data if data else ExtendedDict()
        request_id: str = data.getr("CurrentVehicleDataResponse.requestId")
        await self.async_check_request_succeeded(
            f"{url}/bs/vsr/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/requests/{request_id}/jobstatus",
            "refresh vehicle data",
            REQUEST_SUCCESSFUL,
            REQUEST_FAILED,
            "requestStatusResponse.status",
        )

    async def async_get_stored_position(self, vin: str) -> PositionDataResponse:
        """Get position data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/cf/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/position"
        )
        data = data if data else ExtendedDict()
        return PositionDataResponse(data)

    async def async_get_destinations(self, vin: str) -> DestinationDataResponse:
        """Get destination data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/destinationfeedservice/mydestinations/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/destinations"
        )
        data = data if data else ExtendedDict()
        return DestinationDataResponse(data)

    async def async_get_history(self, vin: str) -> HistoryDataResponse:
        """Get history data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/dwap/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/history"
        )
        data = data if data else ExtendedDict()
        return HistoryDataResponse(data)

    async def async_get_vehicule_users(self, vin: str) -> UsersDataResponse:
        """Get ufers of vehicle."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(f"{url}/bs/uic/v1/{vin.upper()}/users")
        data = data if data else ExtendedDict()
        return UsersDataResponse(data)

    async def async_get_charger(self, vin: str) -> ChargerDataResponse:
        """Get charger data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/batterycharge/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/charger"
        )
        data = data if data else ExtendedDict()
        return ChargerDataResponse(data)

    async def async_get_tripdata(
        self, vin: str, kind: Literal["short", "long", "cyclic"]
    ) -> tuple[TripDataResponse, TripDataResponse]:
        """Get trip data."""
        if kind not in ["short", "long", "cyclic"]:
            raise AudiException(f"Syntax error, {kind} must be 'short'|'long|'cyclic'")
        kind.replace("short", "shortTerm").replace("long", "longTerm")
        url = await self._async_get_home_region(vin.upper())
        params = {
            "type": "list",
            "from": "1970-01-01T00:00:00Z",
            # "from":(datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": (datetime.utcnow() + timedelta(minutes=90)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }
        data = await self._auth.get(
            f"{url}/bs/tripstatistics/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/tripdata/{kind}",
            params=params,
        )
        data = data if data else ExtendedDict()
        td_sorted = sorted(
            data.getr("tripDataList.tripData"),
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

        return TripDataResponse(ExtendedDict(td_current)), TripDataResponse(
            ExtendedDict(td_reset_trip)
        )

    async def async_get_operations_list(self, vin: str) -> Any:
        """Get operation data."""
        url = await self._async_get_home_region_setter(vin.upper())
        data = await self._auth.get(
            f"{url}/rolesrights/operationlist/v3/vehicles/{vin.upper()}"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_climater(self, vin: str) -> ClimaterDataResponse:
        """Get climater data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/climatisation/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/climater"
        )
        data = data if data else ExtendedDict()
        return ClimaterDataResponse(data)

    async def async_get_preheater(self, vin: str) -> PreheaterDataResponse:
        """Get Heater/Ventilation data."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/rs/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/status"
        )
        data = data if data else ExtendedDict()
        return PreheaterDataResponse(data)

    async def async_get_climater_timer(self, vin: str) -> Any:
        """Get timer."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/departuretimer/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/timer"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_capabilities(self, vin: str) -> VehicleDataResponse:
        """Get capabilities."""
        url = "https://emea.bff.cariad.digital"
        headers = await self._auth.async_get_headers(token_type="idk")
        data = await self._auth.get(
            f"{url}/vehicle/v1/vehicles/{vin.upper()}/capabilities", headers=headers
        )
        data = data if data else ExtendedDict()
        return VehicleDataResponse(data, self._spin is not None)

    async def async_get_vehicle_information(self) -> Any:
        """Get vehicle information."""
        headers = await self._auth.async_get_headers(
            token_type="audi",
            headers={
                "Accept-Language": f"{self._auth.language}-{self.country.upper()}",
                "Content-Type": "application/json",
                "X-User-Country": self.country.upper(),
            },
        )
        data = {
            "query": "query vehicleList {\n userVehicles {\n vin\n mappingVin\n vehicle { core { modelYear\n }\n media { shortName\n longName }\n }\n csid\n commissionNumber\n type\n devicePlatform\n mbbConnect\n userRole {\n role\n }\n vehicle {\n classification {\n driveTrain\n }\n }\n nickname\n }\n}"
        }
        resp = await self._auth.post(
            "https://app-api.live-my.audi.com/vgql/v1/graphql",
            data=data,
            headers=headers,
            allow_redirects=False,
        )
        resp = resp if resp else ExtendedDict()
        if "data" not in resp:
            raise AudiException("Invalid json in vehicle information")
        return resp

    async def async_get_honkflash(self, vin: str) -> Any:
        """Get Honk & Flash status."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/rhf/v1/{self.brand}/{self.country}/configuration"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_personal_data(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self._auth.profil_url}/customers/{self._auth.user_id}"
        headers = await self._auth.async_get_headers(token_type="idk")
        data = await self._auth.get(f"{url}/personalData", headers=headers)
        data = data if data else ExtendedDict()
        return data

    async def async_get_real_car_data(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self._auth.profil_url}/customers/{self._auth.user_id}"
        headers = await self._auth.async_get_headers(token_type="idk")
        data = await self._auth.get(f"{url}/realCarData", headers=headers)
        data = data if data else ExtendedDict()
        return data

    async def async_get_mbb_status(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self._auth.profil_url}/customers/{self._auth.user_id}"
        headers = await self._auth.async_get_headers(token_type="idk")
        data = await self._auth.get(f"{url}/mbbStatusData", headers=headers)
        data = data if data else ExtendedDict()
        return data

    async def async_get_identity_data(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self._auth.profil_url}/customers/{self._auth.user_id}"
        headers = await self._auth.async_get_headers(token_type="idk")
        data = await self._auth.get(f"{url}/identityData", headers=headers)
        data = data if data else ExtendedDict()
        return data

    # async def async_get_users(self, vin: str) -> Any:
    #     """Get users."""
    #     url = "https://userinformationservice.apps.emea.vwapps.io/iaa"
    #     headers = await self._auth.async_get_headers(token_type="idk")
    #     data = await self._auth.get(f"{url}/uic/v1/vin/{vin.upper()}/users", headers=headers)
    #     data = data if data else ExtendedDict()
    #     return data

    async def async_get_fences(self, vin: str) -> Any:
        """Get fences."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/geofencing/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/geofencingAlerts"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_fences_config(self, vin: str) -> Any:
        """Get fences configuration."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/geofencing/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/geofencingConfiguration"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_speed_alert(self, vin: str) -> Any:
        """Get speed alert."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/speedalert/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/speedAlerts"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_speed_config(self, vin: str) -> Any:
        """Get speed alert configuration."""
        url = await self._async_get_home_region(vin.upper())
        data = await self._auth.get(
            f"{url}/bs/speedalert/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/speedAlertConfiguration"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_lock(self, vin: str, lock: bool) -> None:
        """Set lock."""
        # OpenHab "lock","unlock"
        url = await self._async_get_home_region(vin.upper())
        data = '<?xml version="1.0" encoding= "UTF-8" ?>'
        data += f'<rluAction xmlns="http://audi.de/connect/rlu"><action>{"lock" if lock else "unlock"}</action></rluAction>'
        headers = await self._auth.async_get_headers(
            token_type="idk",
            headers={
                "Content-Type": "application/vnd.vwg.mbb.RemoteLockUnlock_v1_0_0+xml"
            },
            security_token=await self._async_get_security_token(
                vin, "rlu_v1/operations/" + ("LOCK" if lock else "UNLOCK")
            ),
        )

        rsp = await self._auth.post(
            f"{url}/bs/rlu/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        rsp = rsp if rsp else ExtendedDict()
        request_id = rsp.getr("rluActionResponse.requestId")
        await self.async_check_request_succeeded(
            f"{url}/bs/rlu/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/requests/{request_id}/status",
            "lock vehicle" if lock else "unlock vehicle",
            REQUEST_SUCCESSFUL,
            REQUEST_FAILED,
            "requestStatusResponse.status",
        )

    async def async_climater(self, vin: str, start: bool) -> None:
        """Set Climatisation."""
        # OpenHab "startClimatisation","stopClimatisation"
        url = await self._async_get_home_region(vin.upper())
        heater_source = self._heater_source.get(vin, "electric")
        action = (
            "P_START_CLIMA_EL" if heater_source == "electric" else "P_START_CLIMA_AU"
        )
        security_token = await self._async_get_security_token(
            vin, "rclima_v1/operations/" + (action if start else "P_QSTOPACT")
        )
        data = '<?xml version="1.0" encoding= "UTF-8" ?>'
        data += f'<action><type>{"startClimatisation" if start else "stopClimatisation"}</type>'
        data += f"<settings><heaterSource>{heater_source}</heaterSource></settings></action>"
        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml", security_token
        )

        # headers = await self._auth.async_get_action_headers(
        #     "application/vnd.vwg.mbb.ClimaterAction_v1_0_2+json", security_token
        # )
        # data = (
        #     {
        #         "action": {
        #             "type": "startClimatisation",
        #             "settings": {
        #                 "climatisationWithoutHVpower": "without_hv_power",
        #                 "heaterSource": heater_source,
        #             },
        #         }
        #     }
        #     if start
        #     else {"action": {"type": "stopClimatisation"}}
        # )

        rsp = await self._auth.post(
            f"{url}/bs/climatisation/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/climater/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        rsp = rsp if rsp else ExtendedDict()
        actionid = rsp.getr("action.actionId")
        await self.async_check_request_succeeded(
            f"{url}/bs/climatisation/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/climater/actions/{actionid}",
            "start climatisation" if start else "stop climatisation",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_climater_temp(self, vin: str, temperature: float = 19.5) -> None:
        """Set Climatisation temperature."""
        temperature = int(round(temperature, 1) * 10 + 2731)
        url = await self._async_get_home_region(vin.upper())
        heater_source = self._heater_source.get(vin, "electric")
        data = '<?xml version="1.0" encoding= "UTF-8" ?>'
        data += f"<action><type>setSettings</type><settings><targetTemperature>{temperature}</targetTemperature>"
        data += "<climatisationWithoutHVpower>false</climatisationWithoutHVpower>"
        data += f"<heaterSource>{heater_source}</heaterSource></settings></action>"
        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml", None
        )
        # data = json.dumps(
        #     {
        #         "action": {
        #             "type": "setSettings",
        #             "settings": {
        #                 "targetTemperature": temperature,
        #                 "climatisationWithoutHVpower": True,
        #                 "heaterSource": heater_source,
        #                 "climaterElementSettings": {
        #                     "isClimatisationAtUnlock": False,
        #                     "isMirrorHeatingEnabled": True,
        #                 },
        #             },
        #         }
        #     }
        # )
        # headers = await self._auth.async_get_action_headers("application/json", None)
        rsp = await self._auth.post(
            f"{url}/bs/climatisation/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/climater/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        rsp = rsp if rsp else ExtendedDict()
        actionid = rsp.getr("action.actionId")
        await self.async_check_request_succeeded(
            f"{url}/bs/climatisation/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/climater/actions/{actionid}",
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
        # duration = self._control_duration.get(vin, 60)
        data = '<?xml version="1.0" encoding= "UTF-8" ?>'
        data += '<performAction xmlns="http://audi.de/connect/rs">'
        data += f'<quickstart><active>{"true" if start else "false"}</active></quickstart></performAction>'
        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_0+xml", security_token
        )

        # headers = await self._auth.async_get_action_headers(
        #     "application/vnd.vwg.mbb.RemoteStandheizung_v2_0_2+json", security_token
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

        await self._auth.post(
            f"{url}/bs/rs/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/action",
            headers=headers,
            data=data,
            use_json=False,
        )

    async def async_ventilation(self, vin: str, start: bool) -> None:
        """Set ventilation."""
        # OpenHab "startVentilation","stopVentilation"
        url = await self._async_get_home_region(vin.upper())
        duration = self._control_duration.get(vin, 60)
        security_token = await self._async_get_security_token(
            vin, "rheating_v1/operations/" + ("P_QSACT" if start else "P_QSTOPACT")
        )
        # data = '<?xml version="1.0" encoding= "UTF-8" ?>'
        # data += '<performAction xmlns="http://audi.de/connect/rs">'
        # data += f'<quickstart><active>{"true" if start else "false"}</active>'
        # data += (
        #     f"<climatisationDuration>{self._control_duration}</climatisationDuration>"
        # )
        # data += " <startMode>ventilation</startMode></quickstart></performAction>"
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
                        "climatisationDuration": duration,
                    }
                }
            }
            if start
            else {"performAction": {"quickstop": {"active": False}}}
        )

        await self._auth.post(
            f"{url}/bs/rs/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/action",
            headers=headers,
            data=data,
            use_json=True,
        )

    async def async_charger(self, vin: str, start: bool) -> None:
        """Set charger."""
        # OpenHab "startCharging","stopCharging"
        url = await self._async_get_home_region(vin.upper())
        data = '<?xml version="1.0" encoding= "UTF-8" ?>'
        data += f'<action><type>{"true" if start else "false"}</type></action>'
        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.ChargerAction_v1_0_0+xml", None
        )
        rsp = await self._auth.post(
            f"{url}/bs/batterycharge/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/charger/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        rsp = rsp if rsp else ExtendedDict()
        actionid = rsp.getr("action.actionId")
        await self.async_check_request_succeeded(
            f"{url}/bs/batterycharge/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/charger/actions/{actionid}",
            "start charger" if start else "stop charger",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def async_set_charger_max(self, vin: str, current: float = 32) -> None:
        """Set max current."""
        url = await self._async_get_home_region(vin.upper())
        data = '<?xml version="1.0" encoding= "UTF-8" ?>'
        data += f"<action><type>setSettings</type><settings><maxChargeCurrent>{int(current)}</maxChargeCurrent></settings></action>"
        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.ChargerAction_v1_0_0+xml", None
        )
        rsp = await self._auth.post(
            f"{url}/bs/batterycharge/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/charger/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        rsp = rsp if rsp else ExtendedDict()
        actionid = rsp.getr("action.actionId")
        await self.async_check_request_succeeded(
            f"{url}/bs/batterycharge/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/charger/actions/{actionid}",
            "set charger max current",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def set_heater_source(
        self, vin: str, mode: Literal["electric", "auxiliary", "automatic"]
    ) -> None:
        """Set max current."""
        if mode in ["electric", "auxiliary", "automatic"]:
            self._heater_source[vin] = mode

    async def async_window_heating(self, vin: str, start: bool) -> None:
        """Set window heating."""
        # OpenHab "startWindowHeating","stopWindowHeating"
        url = await self._async_get_home_region(vin.upper())
        data = '<?xml version="1.0" encoding= "UTF-8" ?>'
        data += f"<action><type>{'startWindowHeating' if start else 'stopWindowHeating'}</type></action>"
        headers = await self._auth.async_get_action_headers(
            "application/vnd.vwg.mbb.ClimaterAction_v1_0_0+xml", None
        )
        rsp = await self._auth.post(
            f"{url}/bs/climatisation/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/climater/actions",
            headers=headers,
            data=data,
            use_json=False,
        )
        rsp = rsp if rsp else ExtendedDict()
        actionid = rsp.getr("action.actionId")
        await self.async_check_request_succeeded(
            f"{url}/bs/climatisation/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/climater/actions/{actionid}",
            "start window heating" if start else "stop window heating",
            SUCCEEDED,
            FAILED,
            "action.actionState",
        )

    async def set_control_duration(self, vin: str, duration: int) -> None:
        """Set max current."""
        self._control_duration[vin] = duration

    async def async_set_honkflash(
        self, vin: str, mode: Literal["honk", "flash"], duration: int = 15
    ) -> None:
        """Set honk and flash light."""
        # OpenHab "FLASH_ONLY","HONK_AND_FLASH"
        url = await self._async_get_home_region(vin.upper())
        rsp_position = await self._auth.get(
            f"{url}/bs/cf/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/position"
        )
        position = (
            rsp_position.get("findCarResponse", {})
            .get("Position", {})
            .get("carCoordinate")
        )

        headers = await self._auth.async_get_action_headers("application/json", None)
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
        await self._auth.post(
            f"{url}/bs/rhf/v1/{self.brand}/{self.country}/vehicles/{vin.upper()}/honkAndFlash",
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

            rsp = await self._auth.get(url)

            status = rsp.getr(path)

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
            rsp = await self._auth.get(
                f"{self._home_region_setter[vin]}/cs/vds/v1/vehicles/{vin}/homeRegion"
            )
            rsp = rsp if rsp else ExtendedDict()
            uri = rsp.getr("homeRegion.baseUri.content")
            if uri and uri != self._home_region_setter[vin]:
                self._home_region[vin] = uri.replace("mal-", "fal-").replace(
                    "/api", "/fs-car"
                )
                self._home_region_setter[vin] = uri
        except Exception:  # pylint: disable=broad-except
            pass

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
        headers = await self._auth.async_get_headers(token_type="mbb", okhttp=True)
        rsp = await self._auth.get(
            f"{url}/rolesrights/authorization/v2/vehicles/{vin.upper()}/services/{action}/security-pin-auth-requested",
            headers=headers,
        )
        rsp = rsp if rsp else ExtendedDict()
        sec_token = rsp.getr("securityPinAuthInfo.securityToken")
        challenge: str = rsp.getr(
            "securityPinAuthInfo.securityPinTransmission.challenge"
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
        body = await self._auth.post(
            f"{url}/rolesrights/authorization/v2/security-pin-auth-completed",
            headers=headers,
            data=data,
        )
        return body["securityToken"]
