"""Tests analytics."""

from __future__ import annotations

import logging
from unittest.mock import patch

from aiohttp import ClientSession
from multidict import CIMultiDict

from audiconnectpy import AudiConnect

from . import mock_response

USR = "x.y@z.zz"
PWD = "password"
COUNTRY = "FR"
SPIN = 1234

_LOGGER = logging.getLogger(__name__)


@patch("audiconnectpy.api.AudiConnect.async_fetch_data")
async def test_connect(fetch_date) -> None:
    """Test connection."""
    api = AudiConnect(
        session=ClientSession(), username=USR, password=PWD, country=COUNTRY, spin=SPIN
    )

    markets_json = mock_response(
        resp_data={
            "countries": {
                "countrySpecifications": {
                    "FR": {"name": "France", "defaultLanguage": "fr", "federate": None}
                }
            }
        }
    )
    market = mock_response(
        resp_data={"vehicleDomainGraphQLServiceURLLive": "https://app-api.live-my"}
    )
    services = mock_response(
        resp_data={
            "idkClientIDAndroidLive": "https://idk_client",
            "myAudiAuthorizationServerProxyServiceURLProduction": "https://myaudis",
            "idkCustomerProfileMicroserviceBaseURLLive": "https://idk_ms",
            "mbbOAuthBaseURLLive": "https://mbb_oauth",
            "connectedVehicleVehicleServiceBaseURLProduction": "https://connected_vehicle",
            "idkLoginServiceConfigurationURLProduction": "https://idk_login",
            "mobileDeviceKeyBaseURLProduction": "https://mdk",
        }
    )
    openid_json = mock_response(
        resp_data={
            "authorization_endpoint": "https://authorization_endpoint",
            "token_endpoint": "https://token_endpoint",
            "revocation_endpoint": "https://revocation_endpoint",
        }
    )

    idk_response = mock_response("idk_rsp", "idk_rsptxt")
    email = mock_response(USR)
    pw_rsp = mock_response()
    pw_rsp.return_value.headers = CIMultiDict(
        {
            ("Content-Type", "application/json"),
            ("Location", "http://xxxx?userId=myUser"),
        }
    )

    fwd = mock_response()

    codeauth = mock_response()
    codeauth.return_value.headers = CIMultiDict(
        {("Content-Type", "application/json"), ("Location", "http://xxxxcode=12345")}
    )

    azs = mock_response({"id_token": "azs", "refresh_token": "r_azs"})
    mbb = mock_response({"id_token": "mbb", "refresh_token": "r_mbb", "expires_in": 60})
    idk = mock_response({"id_token": "idk", "refresh_token": "r_idk"})
    here = mock_response({"id_token": "here", "refresh_token": "r_here"})
    client_register = mock_response({"client_id": "CLIEND_ID_REGISTER"})

    with (
        patch(
            "aiohttp.ClientSession.request",
            side_effect=[
                markets_json(),
                market(),
                services(),
                openid_json(),
                idk_response(),
                email(),
                pw_rsp(),
                fwd(),
                fwd(),
                codeauth(),
                idk(),
                azs(),
                client_register(),
                mbb(),
                mbb(),
                here(),
            ],
        ),
        patch("audiconnectpy.auth.Auth._get_post_url", return_value=USR),
    ):
        await api.async_login()

        assert api.auth.binded is True
        assert api.is_connected is True


@patch("audiconnectpy.auth.Auth.async_connect")
@patch("audiconnectpy.api.AudiConnect._async_fill_url")
@patch("audiconnectpy.vehicle.Vehicle.async_update")
async def test_fetch_data(connect, fill_url, update, vehicles) -> None:
    """Test fetch data information."""
    api = AudiConnect(
        session=ClientSession(), username=USR, password=PWD, country=COUNTRY, spin=SPIN
    )
    with patch(
        "audiconnectpy.api.AudiConnect.async_get_vehicles",
        return_value=vehicles,
    ):
        await api.async_login()
        assert api.vehicles is not None


@patch("audiconnectpy.auth.Auth.async_connect")
@patch("audiconnectpy.vehicle.Vehicle.async_update")
async def test_get_vehicles(connect, update, vehicles, uris) -> None:
    """Test fetch data information."""
    api = AudiConnect(
        session=ClientSession(), username=USR, password=PWD, country=COUNTRY, spin=SPIN
    )
    with (
        patch(
            "aiohttp.ClientSession.request",
            side_effect=[
                mock_response(vehicles)(),
                mock_response({"homeRegion": {"baseUri": {"content": "mal-xxx"}}})(),
            ],
        ),
    ):
        api.auth.uris = uris
        await api.async_login()
        assert api.vehicles is not None
        assert api.vehicles[0].fill_region.url == "fal-xxx"
        assert api.vehicles[0].fill_region.url_setter == "mal-xxx"
