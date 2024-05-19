"""Audi connect."""

from __future__ import annotations

from collections import namedtuple
import logging
from typing import Any, NamedTuple

from aiohttp import ClientSession

from .auth import Auth
from .const import (
    CLIENT_ID,
    MARKET_URL,
    MBB_URL,
    URL_HERE_COM,
    URL_HOME_REGION,
    URL_HOME_REGION_SETTER,
    URL_INFO_USER,
    URL_INFO_VEHICLE,
    URL_INFO_VEHICLE_US,
)
from .exceptions import AudiException, AuthorizationError
from .helpers import ExtendedDict
from .vehicle import Globals, Vehicle, Vehicles

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
        unit_system: str = "metric",
    ) -> None:
        """Initialize."""
        Globals(unit_system)
        self.auth = Auth(session)
        self.country = country.upper()
        self._password = password
        self._username = username
        self._spin = spin
        self.is_connected: bool = False
        self.vehicles: list[Vehicle] = []
        self.uris: dict[str, str] = {}

    async def async_login(self, vinlist: list[str] | None = None) -> None:
        """Login and retrieve tokens."""

        # Retrieve urls
        try:
            await self._async_retrieve_url_service()
        except AudiException as error:
            raise AudiException("Error fetch home region urls (%s)", error)

        if not self.is_connected:
            try:
                await self.auth.async_connect(self._username, self._password, self.uris)
            except AudiException as error:
                raise AuthorizationError(error) from error
            else:
                self.is_connected = True

        # Update the state of all vehicles.
        if self.is_connected and len(self.vehicles) == 0:
            try:
                vehicles_response = await self.async_get_information_vehicles()
            except AudiException as error:
                raise AudiException(
                    "Error to get information vehicles ({error})"
                ) from error
            else:
                obj_vehicles = Vehicles.from_dict(vehicles_response.get("data", []))
                self.vehicles = obj_vehicles.user_vehicles
                for vehicle in self.vehicles:
                    fill_region = await self._async_fill_url(vehicle.vin)
                    self.uris.update(fill_region._asdict())
                    # Add attributes to vehicle
                    vehicle.uris = self.uris
                    vehicle.auth = self.auth
                    vehicle.spin = self._spin

                    if vinlist is None or vehicle.vin.upper() in vinlist:
                        try:
                            # Fetch data for a vehicle
                            await vehicle.async_update()
                        except AudiException as error:
                            _LOGGER.error(
                                "Error while updating - %s - (%s)", vehicle.vin, error
                            )

    async def async_get_information_vehicles(self) -> Any:
        """Get information vehicles."""
        headers = await self.auth.async_get_headers(
            token_type="audi",
            headers={
                "Accept-Language": f"{self.uris['language']}-{self.country}",
                "Content-Type": "application/json",
                "X-User-Country": self.country,
            },
        )
        data = {
            "query": "query vehicleList {\n userVehicles {\n vin\n mappingVin\n vehicle { core { modelYear\n }\n media { shortName\n longName }\n }\n csid\n commissionNumber\n type\n devicePlatform\n mbbConnect\n userRole {\n role\n }\n vehicle {\n classification {\n driveTrain\n }\n }\n nickname\n }\n}"
        }
        url = URL_INFO_VEHICLE if self.country != "US" else URL_INFO_VEHICLE_US

        response = await self.auth.request(
            "POST", url, json=data, headers=headers, allow_redirects=False
        )
        if "data" not in response:
            raise AudiException("Invalid json in vehicle information")

        return response

    async def _async_retrieve_url_service(self) -> None:
        """Get urls for request."""
        # Get markets to get language
        global URL_SERVICES
        country = self.country.upper()
        markets_json = await self.auth.request("GET", f"{MARKET_URL}/markets")

        country_spec = ExtendedDict(markets_json).getr(
            "countries.countrySpecifications"
        )
        if country not in country_spec:
            raise AudiException("Country not found")

        language = country_spec[country].get("defaultLanguage")

        # Get market config
        services = await self.auth.request(
            "GET", f"{MARKET_URL}/market/{country}/{language}"
        )

        client_id = services.get("idkClientIDAndroidLive", CLIENT_ID)
        audi_baseurl = services.get(
            "myAudiAuthorizationServerProxyServiceURLProduction"
        )
        profil_url = (
            services.get("idkCustomerProfileMicroserviceBaseURLLive", "") + "/v3"
        )
        mbb_baseurl = services.get("mbbOAuthBaseURLLive", MBB_URL)
        cvvsb_base_url = services.get("connectedVehicleVehicleServiceBaseURLProduction")

        # Get openId config
        openid_url = services.get("idkLoginServiceConfigurationURLProduction")
        _LOGGER.debug("IDK Base Url: %s", openid_url)
        openid_json = await self.auth.request("GET", openid_url)

        authorization_endpoint_url = openid_json.get("authorization_endpoint", "")
        token_endpoint_url = openid_json.get("token_endpoint", "")
        revocation_endpoint_url = openid_json.get("revocation_endpoint", "")

        self.uris = {
            "client_id": client_id,
            "audi_url": audi_baseurl,
            "profil_url": profil_url,
            "mbb_url": mbb_baseurl,
            "here_url": URL_HERE_COM,
            "cv_url": cvvsb_base_url,
            "user_url": URL_INFO_USER,
            "authorization_endpoint": authorization_endpoint_url,
            "token_endpoint": token_endpoint_url,
            "revocation_endpoint": revocation_endpoint_url,
            "language": language,
            "country": country,
        }

        _LOGGER.debug("Urls of service: %s", self.uris)

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
