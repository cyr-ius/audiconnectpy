"""Audi connect."""

from __future__ import annotations

import logging
from typing import Any, Tuple

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
from .exceptions import AudiException
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
        self._audi_vehicles: list[Vehicle] = []
        self.auth = Auth(session)
        self.country = country.upper()
        self._password = password
        self._username = username
        self._spin = spin
        self.is_connected: bool = False
        self.vehicles: dict[str, Vehicle] = {}
        self.uris: dict[str, str] = {}

    async def async_login(self) -> bool:
        """Login and retrieve tokens."""
        if not self.is_connected:
            self.is_connected = await self.auth.async_connect(
                self._username, self._password, self.uris
            )
        return self.is_connected

    async def async_connect(self, vinlist: list[str] | None = None) -> bool:
        """Update data."""
        # Retrieve urls
        await self._async_retrieve_url_service()

        # Login
        if not await self.async_login():
            return False

        # Update the state of all vehicles.
        try:
            if len(self._audi_vehicles) == 0:
                vehicles_response = await self.async_get_information_vehicles()
                obj_vehicles = Vehicles.from_dict(vehicles_response.get("data", []))
                self._audi_vehicles = obj_vehicles.user_vehicles
                for vehicle in self._audi_vehicles:
                    (url, url_setter) = await self._async_fill_url(vehicle.vin)
                    self.uris.update({"url": url, "url_setter": url_setter})
                    vehicle.uris = self.uris
                    vehicle.auth = self.auth
                    vehicle.spin = self._spin
                    await self._async_add_or_update_vehicle(vehicle, vinlist)
            return True
        except OSError as exception:
            # Force a re-login in case of failure/exception
            self.is_connected = False
            _LOGGER.exception(exception)
            return False

    async def _async_add_or_update_vehicle(
        self, vehicle: Vehicle, vinlist: list[str] | None
    ) -> None:
        """Add or Update vehicle."""
        if vehicle.vin is not None:
            if vinlist is None or vehicle.vin.upper() in vinlist:
                vupd = [
                    x for vin, x in self.vehicles.items() if vin == vehicle.vin.upper()
                ]
                if len(vupd) > 0:
                    if await vupd[0].async_update() is False:
                        self.is_connected = False
                else:
                    try:
                        if await vehicle.async_update() is False:
                            self.is_connected = False
                        self.vehicles.update({vehicle.vin: vehicle})
                    except AudiException:  # pylint: disable=broad-except
                        pass

    async def _async_fill_url(self, vin: str) -> Tuple[str, str]:
        """Fill region."""
        url = URL_HOME_REGION
        url_setter = URL_HOME_REGION_SETTER
        try:
            rsp = await self.auth.get(
                f"{url_setter}/cs/vds/v1/vehicles/{vin}/homeRegion"
            )
            rsp = rsp if rsp else ExtendedDict()
            uri = rsp.getr("homeRegion.baseUri.content")
            if uri and uri != url_setter:
                url = uri.replace("mal-", "fal-").replace("/api", "/fs-car")
                url_setter = uri
        except Exception:  # pylint: disable=broad-except
            pass

        return url, url_setter

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
        resp = await self.auth.post(
            url, data=data, headers=headers, allow_redirects=False
        )
        if "data" not in resp:
            raise AudiException("Invalid json in vehicle information")
        return resp

    async def _async_retrieve_url_service(self) -> None:
        """Get urls for request."""
        # Get markets to get language
        global URL_SERVICES
        country = self.country.upper()
        markets_json = await self.auth.request("GET", f"{MARKET_URL}/markets", None)

        country_spec = markets_json.getr("countries.countrySpecifications")
        if country not in country_spec:
            raise AudiException("Country not found")

        language = country_spec[country].get("defaultLanguage")

        # Get market config to get client_id , Authorization base url and mbbOAuth base url
        services = await self.auth.request(
            "GET", f"{MARKET_URL}/market/{country}/{language}", None
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

        _LOGGER.debug("Client id: %s", client_id)
        _LOGGER.debug("Audi Base Url: %s", audi_baseurl)
        _LOGGER.debug("Profil Base Url: %s", profil_url)
        _LOGGER.debug("MBB Base Url: %s", mbb_baseurl)
        _LOGGER.debug("ConnectedVehicle Base Url: %s", cvvsb_base_url)

        # Get openId config to get authorizationEndpoint, tokenEndpoint, RevocationEndpoint
        openid_url = services.get("idkLoginServiceConfigurationURLProduction")
        _LOGGER.debug("IDK Base Url: %s", openid_url)
        openid_json = await self.auth.request("GET", openid_url, None)

        authorization_endpoint_url = openid_json.get("authorization_endpoint", "")
        token_endpoint_url = openid_json.get("token_endpoint", "")
        revocation_endpoint_url = openid_json.get("revocation_endpoint", "")

        _LOGGER.debug("AuthEndpoint: %s", authorization_endpoint_url)
        _LOGGER.debug("TokenEndpoint: %s", token_endpoint_url)
        _LOGGER.debug("RevocationEndpoint: %s", revocation_endpoint_url)

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
            "language": language,
            "country": country,
        }
