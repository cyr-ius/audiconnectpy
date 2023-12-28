"""Call url service."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from .actions import AudiActions
from .auth import Auth
from .const import (
    BRAND,
)
from .exceptions import AudiException
from .helpers import ExtendedDict
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

_LOGGER = logging.getLogger(__name__)


@dataclass
class AudiService(AudiActions):
    """Audi service."""

    auth: Auth
    spin: int
    country: str
    url: str
    url_setter: str

    async def async_get_vehicle_details(self) -> Any:
        """Get vehicle data."""
        accept = {
            "Accept": "application/vnd.vwg.mbb.vehicleDataDetail_v2_1_0+json, application/vnd.vwg.mbb.genericError_v1_0_2+json"
        }
        headers = await self.auth.async_get_headers(token_type="mbb", headers=accept)
        data = await self.auth.get(
            f"{self.url}/vehicleMgmt/vehicledata/v2/{BRAND}/{self.country}/vehicles/{self.vin}/",
            headers=headers,
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_vehicle(self) -> VehicleDataResponse:
        """Get store data."""
        data = await self.auth.get(
            f"{self.url}/bs/vsr/v1/{BRAND}/{self.country}/vehicles/{self.vin}/status"
        )
        data = data if data else ExtendedDict()
        return VehicleDataResponse(data, self.spin is not None)

    async def async_get_stored_position(self) -> PositionDataResponse:
        """Get position data."""
        data = await self.auth.get(
            f"{self.url}/bs/cf/v1/{BRAND}/{self.country}/vehicles/{self.vin}/position"
        )
        data = data if data else ExtendedDict()
        return PositionDataResponse(data)

    async def async_get_destinations(self) -> DestinationDataResponse:
        """Get destination data."""
        data = await self.auth.get(
            f"{self.url}/destinationfeedservice/mydestinations/v1/{BRAND}/{self.country}/vehicles/{self.vin}/destinations"
        )
        data = data if data else ExtendedDict()
        return DestinationDataResponse(data)

    async def async_get_history(self) -> HistoryDataResponse:
        """Get history data."""
        data = await self.auth.get(
            f"{self.url}/bs/dwap/v1/{BRAND}/{self.country}/vehicles/{self.vin}/history"
        )
        data = data if data else ExtendedDict()
        return HistoryDataResponse(data)

    async def async_get_vehicule_users(self) -> UsersDataResponse:
        """Get ufers of vehicle."""
        data = await self.auth.get(f"{self.url}/bs/uic/v1/{self.vin}/users")
        data = data if data else ExtendedDict()
        return UsersDataResponse(data)

    async def async_get_charger(self) -> ChargerDataResponse:
        """Get charger data."""
        data = await self.auth.get(
            f"{self.url}/bs/batterycharge/v1/{BRAND}/{self.country}/vehicles/{self.vin}/charger"
        )
        data = data if data else ExtendedDict()
        return ChargerDataResponse(data)

    async def async_get_tripdata(
        self, kind: Literal["short", "long", "cyclic"]
    ) -> tuple[TripDataResponse, TripDataResponse]:
        """Get trip data."""
        if kind not in ["short", "long", "cyclic"]:
            raise AudiException(f"Syntax error, {kind} must be 'short'|'long|'cyclic'")
        knd = kind.replace("short", "shortTerm").replace("long", "longTerm")
        params = {
            "type": "list",
            "from": "1970-01-01T00:00:00Z",
            # "from":(datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": (datetime.utcnow() + timedelta(minutes=90)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }
        data = await self.auth.get(
            f"{self.url}/bs/tripstatistics/v1/{BRAND}/{self.country}/vehicles/{self.vin}/tripdata/{knd}",
            params=params,
        )
        data = data if data else ExtendedDict()
        td_sorted = sorted(
            data.getr("tripDataList.tripData", []),
            key=lambda k: k["overallMileage"],
            reverse=True,
        )
        td_current = td_sorted[0] if len(td_sorted) > 0 else {}
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

    async def async_get_operations_list(self) -> Any:
        """Get operation data."""
        data = await self.auth.get(
            f"{self.url}/rolesrights/operationlist/v3/vehicles/{self.vin}"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_climater(self) -> ClimaterDataResponse:
        """Get climater data."""
        data = await self.auth.get(
            f"{self.url}/bs/climatisation/v1/{BRAND}/{self.country}/vehicles/{self.vin}/climater"
        )
        data = data if data else ExtendedDict()
        return ClimaterDataResponse(data)

    async def async_get_preheater(self) -> PreheaterDataResponse:
        """Get Heater/Ventilation data."""
        data = await self.auth.get(
            f"{self.url}/bs/rs/v1/{BRAND}/{self.country}/vehicles/{self.vin}/status"
        )
        data = data if data else ExtendedDict()
        return PreheaterDataResponse(data)

    async def async_get_climater_timer(self) -> Any:
        """Get timer."""
        data = await self.auth.get(
            f"{self.url}/bs/departuretimer/v1/{BRAND}/{self.country}/vehicles/{self.vin}/timer"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_capabilities(self) -> VehicleDataResponse:
        """Get capabilities."""
        url = "https://emea.bff.cariad.digital"
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.get(
            f"{url}/vehicle/v1/vehicles/{self.vin}/capabilities", headers=headers
        )
        data = data if data else ExtendedDict()
        return VehicleDataResponse(data, self.spin is not None)

    async def async_get_honkflash(self) -> Any:
        """Get Honk & Flash status."""
        data = await self.auth.get(
            f"{self.url}/bs/rhf/v1/{BRAND}/{self.country}/configuration"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_personal_data(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self.auth.profil_url}/customers/{self.auth.user_id}"
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.get(f"{url}/personalData", headers=headers)
        data = data if data else ExtendedDict()
        return data

    async def async_get_real_car_data(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self.auth.profil_url}/customers/{self.auth.user_id}"
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.get(f"{url}/realCarData", headers=headers)
        data = data if data else ExtendedDict()
        return data

    async def async_get_mbb_status(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self.auth.profil_url}/customers/{self.auth.user_id}"
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.get(f"{url}/mbbStatusData", headers=headers)
        data = data if data else ExtendedDict()
        return data

    async def async_get_identity_data(self) -> Any:
        """Get Honk & Flash status."""
        url = f"{self.auth.profil_url}/customers/{self.auth.user_id}"
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.get(f"{url}/identityData", headers=headers)
        data = data if data else ExtendedDict()
        return data

    async def async_get_users(self) -> Any:
        """Get users."""
        url = "https://userinformationservice.apps.emea.vwapps.io/iaa"
        headers = await self.auth.async_get_headers(token_type="idk")
        data = await self.auth.get(
            f"{url}/uic/v1/vin/{self.vin}/users", headers=headers
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_fences(self) -> Any:
        """Get fences."""
        data = await self.auth.get(
            f"{self.url}/bs/geofencing/v1/{BRAND}/{self.country}/vehicles/{self.vin}/geofencingAlerts"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_fences_config(self) -> Any:
        """Get fences configuration."""
        data = await self.auth.get(
            f"{self.url}/bs/geofencing/v1/{BRAND}/{self.country}/vehicles/{self.vin}/geofencingConfiguration"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_speed_alert(self) -> Any:
        """Get speed alert."""
        data = await self.auth.get(
            f"{self.url}/bs/speedalert/v1/{BRAND}/{self.country}/vehicles/{self.vin}/speedAlerts"
        )
        data = data if data else ExtendedDict()
        return data

    async def async_get_speed_config(self) -> Any:
        """Get speed alert configuration."""
        data = await self.auth.get(
            f"{self.url}/bs/speedalert/v1/{BRAND}/{self.country}/vehicles/{self.vin}/speedAlertConfiguration"
        )
        data = data if data else ExtendedDict()
        return data
