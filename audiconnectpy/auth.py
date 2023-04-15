"""Audi connect."""
from __future__ import annotations

import asyncio
import base64
import hmac
import json
import logging
import os
import re
import socket
import uuid
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp
import async_timeout
from aiohttp.hdrs import METH_GET, METH_POST, METH_PUT
from bs4 import BeautifulSoup

from .exceptions import (
    AudiException,
    HttpRequestError,
    ServiceNotFoundError,
    TimeoutExceededError,
)
from .util import get_attr, jload, json_loads

TIMEOUT = 120
DELAY = 10
HDR_XAPP_VERSION = "4.13.0"
HDR_USER_AGENT = "myAudi-Android/4.13.0 (Build 800238275.2210271555) Android/11"
MARKET_URL = "https://content.app.my.audi.com/service/mobileapp/configurations"
CLIENT_ID = "09b6cbec-cd19-4589-82fd-363dfa8c24da@apps_vw-dilab_com"
MBB_URL = "https://mbboauth-1d.prd.ece.vwg-connect.com/mbbcoauth"

_LOGGER = logging.getLogger(__name__)


class Auth:
    """Authentication."""

    def __init__(
        self, session: aiohttp.ClientSession, proxy: str | None = None
    ) -> None:
        """Initialize."""
        self._session = session
        if proxy:
            self.__proxy: dict[  # pylint: disable=unused-private-member
                str, str
            ] | None = {
                "http": proxy,
                "https": proxy,
            }
        else:
            self.__proxy = None  # pylint: disable=unused-private-member

        self._audi_baseurl = ""
        self._mbb_baseurl = MBB_URL
        self._token_endpoint_url = ""
        self._authorization_endpoint_url = ""
        self._revocation_endpoint_url = ""

        self._client_id = CLIENT_ID
        self._x_client_id = ""
        self._language = ""
        self._country = ""
        self._mbb_token: dict[str, Any] = {}
        self._mbb_token_expired: datetime = datetime.now()
        self._idk_token: dict[str, str] = {}
        self._audi_token: dict[str, str] = {}

    async def request(
        self,
        method: str,
        url: str,
        data: Any | None,
        headers: dict[str, str] | None = None,
        raw_reply: bool = False,
        rsp_wtxt: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Request url with method."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                response = await self._session.request(
                    method, url, headers=headers, data=data, **kwargs
                )
        except (asyncio.CancelledError, asyncio.TimeoutError) as error:
            raise TimeoutExceededError(
                "Timeout occurred while connecting to Audi Connect."
            ) from error
        except (aiohttp.ClientError, socket.gaierror) as error:
            _LOGGER.debug(
                "HTTP Request error (%s) (%s): %s", str(url), str(data), str(error)
            )
            raise HttpRequestError(
                "Error occurred while communicating with Audit Connect."
            ) from error

        content_type = response.headers.get("Content-Type", "")
        if response.status // 100 in [4, 5]:
            contents = await response.read()
            response.close()
            _LOGGER.debug(
                "[%s] Service not found: %s", response.status, contents.decode("utf8")
            )
            if content_type == "application/json":
                raise ServiceNotFoundError(
                    response.status, json.loads(contents.decode("utf8"))
                )
            raise ServiceNotFoundError(
                response.status, {"message": contents.decode("utf8")}
            )

        if raw_reply:
            return response

        if "application/json" in content_type:
            return await response.json(loads=json_loads)

        text = await response.text()
        if rsp_wtxt:
            return response, text
        return text

    async def get(self, url: str, raw_reply: bool = False, **kwargs: Any) -> Any:
        """GET request."""
        full_headers = await self.async_get_headers()
        response = await self.request(
            METH_GET,
            url,
            data=None,
            headers=full_headers,
            raw_reply=raw_reply,
            **kwargs,
        )
        return response

    async def put(
        self,
        url: str,
        data: str | bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """PUT request."""
        full_headers = await self.async_get_headers()
        if headers is not None:
            full_headers.update(headers)
        response = await self.request(METH_PUT, url, headers=full_headers, data=data)
        return response

    async def post(
        self,
        url: str,
        data: str | bytes | None = None,
        headers: dict[str, str] | None = None,
        use_json: bool = True,
        raw_reply: bool = False,
        **kwargs: Any,
    ) -> Any:
        """POST request."""
        full_headers = await self.async_get_headers()
        if headers is not None:
            full_headers.update(headers)
        if use_json and data is not None:
            data = json.dumps(data)
        response = await self.request(
            METH_POST,
            url,
            headers=full_headers,
            data=data,
            raw_reply=raw_reply,
            **kwargs,
        )
        return response

    async def async_connect(
        self, username: str, password: str, country: str, ntries: int = 3
    ) -> bool:
        """Connect to API."""
        try:
            self._country = country
            await self._async_login(username, password)
        except HttpRequestError as error:  # pylint: disable=broad-except
            if ntries > 1:
                _LOGGER.error(
                    "Login to Audi service failed, trying again in %s seconds [ERROR:%s]",
                    DELAY,
                    str(error),
                )
                await asyncio.sleep(DELAY)
                return await self.async_connect(username, password, country, ntries - 1)
            _LOGGER.error("Login to Audi service failed: %s ", str(error))
            return False
        else:
            return True

    async def _async_login(self, user: str, password: str) -> None:
        """Request login."""
        await self._async_retrieve_url_service()

        # Generate code_challenge
        code_verifier = str(base64.urlsafe_b64encode(os.urandom(32)), "utf-8").strip(
            "="
        )
        code_challenge = str(
            base64.urlsafe_b64encode(
                sha256(code_verifier.encode("ascii", "ignore")).digest()
            ),
            "utf-8",
        ).strip("=")
        code_challenge_method = "S256"

        # login page
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "X-App-Version": HDR_XAPP_VERSION,
            "X-App-Name": "myAudi",
            "User-Agent": HDR_USER_AGENT,
        }

        idk_data = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": "myaudi:///",
            "scope": "address profile badge birthdate birthplace nationalIdentifier nationality profession email vin phone nickname name picture mbb gallery openid",
            "state": str(uuid.uuid4()),
            "nonce": str(uuid.uuid4()),
            "prompt": "login",
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "ui_locales": f"{self._language}-{self._language} {self._language}",
        }
        idk_rsp, idk_rsptxt = await self.request(
            "GET",
            self._authorization_endpoint_url,
            None,
            headers=headers,
            params=idk_data,
            rsp_wtxt=True,
        )

        # form_data with email
        submit_data = self._get_hidden_html_input_form_data(idk_rsptxt, {"email": user})
        submit_url = self._get_post_url(idk_rsptxt, self._authorization_endpoint_url)
        # send email
        email_rsptxt = await self.request(
            "POST",
            submit_url,
            submit_data,
            headers=headers,
            cookies=idk_rsp.cookies,
            allow_redirects=True,
        )

        # form_data with password
        # 2022-01-29: new HTML response uses a js two build the html form data + button.
        # Therefore it's not possible to extract hmac and other form data.
        # --> extract hmac from embedded js snippet.
        regex_res = re.findall(
            '"hmac"\s*:\s*"[0-9a-fA-F]+"',  # noqa: W605 pylint: disable=anomalous-backslash-in-string
            email_rsptxt,
        )
        if regex_res:
            submit_url = submit_url.replace("identifier", "authenticate")
            submit_data["hmac"] = regex_res[0].split(":")[1].strip('"')
            submit_data["password"] = password
        else:
            submit_data = self._get_hidden_html_input_form_data(
                email_rsptxt, {"password": password}
            )
            submit_url = self._get_post_url(email_rsptxt, submit_url)

        # send password
        pw_rsp = await self.request(
            "POST",
            submit_url,
            submit_data,
            headers=headers,
            cookies=idk_rsp.cookies,
            allow_redirects=False,
            raw_reply=True,
        )

        # forward1 after pwd
        fwd1_rsp = await self.request(
            "GET",
            pw_rsp.headers.get("Location", {}),
            None,
            headers=headers,
            cookies=idk_rsp.cookies,
            allow_redirects=False,
            raw_reply=True,
        )

        # forward2 after pwd
        fwd2_rsp = await self.request(
            "GET",
            fwd1_rsp.headers.get("Location", {}),
            None,
            headers=headers,
            cookies=idk_rsp.cookies,
            allow_redirects=False,
            raw_reply=True,
        )

        # get tokens
        codeauth_rsp = await self.request(
            "GET",
            fwd2_rsp.headers.get("Location", {}),
            None,
            headers=headers,
            cookies=fwd2_rsp.cookies,
            allow_redirects=False,
            raw_reply=True,
        )

        authcode_parsed = urlparse(
            codeauth_rsp.headers.get("Location", {})[len("myaudi:///?") :]
        )
        authcode_strings = parse_qs(authcode_parsed.path)

        # IDK token
        self._idk_token = await self._async_get_idk_token(
            self._client_id,
            code=authcode_strings["code"][0],
            code_verifier=code_verifier,
        )

        # Audi token
        self._audi_token = await self._async_get_azs_token(
            self._idk_token["access_token"]
        )

        # mbboauth client register
        self._x_client_id = await self._async_register_idk()

        # MBB token
        self._mbb_token = await self._async_get_mbb_token(
            self._x_client_id, id_token=self._idk_token["id_token"]
        )

        # mbboauth refresh (app immediately refreshes the token)
        refresh_token = self._mbb_token["refresh_token"]
        self._mbb_token = await self._async_get_mbb_token(
            self._x_client_id, refresh_token=self._mbb_token["refresh_token"]
        )
        self._mbb_token["refresh_token"] = refresh_token
        self._mbb_token_expired = datetime.now() + timedelta(
            seconds=self._mbb_token["expires_in"]
        )

    async def async_refresh_tokens(self) -> None:
        """Refresh token if."""
        if datetime.now() > self._mbb_token_expired:
            try:
                _LOGGER.debug("Refresh token if necessary")
                # MBB Token
                refresh_token = self._mbb_token["refresh_token"]
                self._mbb_token = await self._async_get_mbb_token(
                    self._x_client_id, refresh_token=refresh_token
                )
                # TR/2022-02-10: If a new refresh_token is provided, save it for further refreshes
                if "refresh_token" not in self._mbb_token:
                    _LOGGER.debug("refresh token not provided")
                    self._mbb_token["refresh_token"] = refresh_token

                self._mbb_token_expired = datetime.now() + timedelta(
                    seconds=self._mbb_token["expires_in"]
                )

                # IDK Token
                self._idk_token = await self._async_get_idk_token(
                    self._client_id, refresh_token=self._idk_token["refresh_token"]
                )

                # Audi token
                self._audi_token = await self._async_get_azs_token(
                    self._idk_token["access_token"]
                )

            except AudiException as error:  # pylint: disable=broad-except
                _LOGGER.error("Refresh token failed: %s", str(error))

    async def _async_retrieve_url_service(self) -> None:
        """Get urls for request."""
        # Get markets to get language
        markets_json = await self.request("GET", f"{MARKET_URL}/markets", None)

        country_spec = get_attr(markets_json, "countries.countrySpecifications")
        if self._country.upper() not in country_spec:
            raise AudiException("Country not found")

        self._language = country_spec.get(self._country.upper(), {}).get(
            "defaultLanguage"
        )

        # Get market config to get client_id , Authorization base url and mbbOAuth base url
        market_json = await self.request(
            "GET", f"{MARKET_URL}/market/{self._country}/{self._language}", None
        )

        self._client_id = market_json.get("idkClientIDAndroidLive", CLIENT_ID)
        self._audi_baseurl = market_json.get(
            "myAudiAuthorizationServerProxyServiceURLProduction", ""
        )
        openid_url = market_json.get("idkLoginServiceConfigurationURLProduction", "")
        self._mbb_baseurl = market_json.get("mbbOAuthBaseURLLive", MBB_URL)

        _LOGGER.debug("Client id: %s", self._client_id)
        _LOGGER.debug("Audi Base Url: %s", self._audi_baseurl)
        _LOGGER.debug("MBB Base Url: %s", self._mbb_baseurl)
        _LOGGER.debug("IDK Base Url: %s", openid_url)

        # Get openId config to get authorizationEndpoint, tokenEndpoint, RevocationEndpoint
        openid_json = await self.request("GET", openid_url, None)

        self._authorization_endpoint_url = openid_json.get("authorization_endpoint", "")
        self._token_endpoint_url = openid_json.get("token_endpoint", "")
        self._revocation_endpoint_url = openid_json.get("revocation_endpoint", "")

        _LOGGER.debug("AuthEndpoint: %s", self._authorization_endpoint_url)
        _LOGGER.debug("TokenEndpoint: %s", self._token_endpoint_url)
        _LOGGER.debug("RevocationEndpoint: %s", self._revocation_endpoint_url)

    async def async_get_headers(self) -> dict[str, str]:
        """Prepare header."""
        await self.async_refresh_tokens()
        data = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "User-Agent": HDR_USER_AGENT,
            "X-App-Version": HDR_XAPP_VERSION,
            "X-App-Name": "myAudi",
        }
        if self._mbb_token:
            data["Authorization"] = f"Bearer {self._mbb_token['access_token']}"
        if self._x_client_id:
            data["X-Client-ID"] = self._x_client_id

        return data

    async def async_get_action_headers(
        self, content_type: str, security_token: str | None
    ) -> dict[str, str]:
        """Return header for vehicle action."""
        await self.async_refresh_tokens()
        headers = {
            "Accept": "application/json, application/vnd.vwg.mbb.ChargerAction_v1_0_0+xml,application/vnd.volkswagenag.com-error-v1+xml,application/vnd.vwg.mbb.genericError_v1_0_2+xml, application/vnd.vwg.mbb.RemoteStandheizung_v2_0_0+xml, application/vnd.vwg.mbb.genericError_v1_0_2+xml,application/vnd.vwg.mbb.RemoteLockUnlock_v1_0_0+xml,*/*",
            "Accept-charset": "UTF-8",
            "Authorization": f"Bearer {self._mbb_token['access_token']}",
            "Content-Type": content_type,
            "Host": "msg.volkswagen.de",
            "User-Agent": "okhttp/3.7.0",
            "X-App-Version": "3.14.0",
            "X-App-Name": "myAudi",
        }

        if security_token:
            headers["x-mbbSecToken"] = security_token

        return headers

    async def async_get_information_headers(self) -> dict[str, str]:
        """Return header for vehicle information."""
        await self.async_refresh_tokens()
        token = self._audi_token.get("access_token")
        return {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "Accept-Language": f"{self._language}-{self._country.upper()}",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": HDR_USER_AGENT,
            "X-App-Name": "myAudi",
            "X-App-Version": HDR_XAPP_VERSION,
            "X-User-Country": self._country.upper(),
        }

    async def async_get_trip_headers(self) -> dict[str, str]:
        """Return header for trip information."""
        await self.async_refresh_tokens()
        token = self._mbb_token.get("access_token")
        return {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "Authorization": f"Bearer {token}",
            "User-Agent": HDR_USER_AGENT,
            "X-App-Name": "myAudi",
            "X-App-Version": HDR_XAPP_VERSION,
            "X-Client-ID": self._x_client_id,
        }

    async def async_get_security_headers(self) -> dict[str, str]:
        """Return header for security token."""
        await self.async_refresh_tokens()
        token = self._mbb_token.get("access_token")
        return {
            "User-Agent": "okhttp/3.7.0",
            "X-App-Version": "3.14.0",
            "X-App-Name": "myAudi",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

    async def async_get_simple_headers(self) -> dict[str, str]:
        """Get simple headers."""
        await self.async_refresh_tokens()
        token = self._idk_token.get("access_token")
        return {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "Authorization": f"Bearer {token}",
            "User-Agent": HDR_USER_AGENT,
        }

    @staticmethod
    def _get_hidden_html_input_form_data(
        response: str | bytes, form_data: dict[str, str]
    ) -> dict[str, Any]:
        """Parse the html body and extract the target.

        url, csrf token and other required parameters
        """
        html = BeautifulSoup(response, "html.parser")
        form_inputs = html.find_all("input", attrs={"type": "hidden"})
        for form_input in form_inputs:
            name = form_input.get("name")
            form_data[name] = form_input.get("value")

        return form_data

    @staticmethod
    def _get_post_url(response: str | bytes, url: str) -> str:
        """Parse the html body and extract the target.

        url, csrf token and other required parameters
        """
        html = BeautifulSoup(response, "html.parser")
        form_tag = html.find("form")

        # Extract the target url
        action = form_tag.get("action")
        if action.startswith("http"):
            # Absolute url
            username_post_url: str = action
        elif action.startswith("/"):
            # Relative to domain
            url_parts = urlparse(url)
            username_post_url = url_parts.scheme + "://" + url_parts.netloc + action
        else:
            raise AudiException(f"Unknown form action: {action}")
        return username_post_url

    # TR/2022-06-15: New secrect for X_QMAuth
    @staticmethod
    def _calculate_x_qmauth() -> str:
        """Calculate X-QMAuth value."""
        gmtime_100sec = int(
            (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds() / 100
        )
        # xqmauth_secret = bytes(
        #     [
        #         256 - 28,
        #         120,
        #         102,
        #         55,
        #         256 - 114,
        #         256 - 16,
        #         101,
        #         256 - 116,
        #         256 - 25,
        #         93,
        #         113,
        #         0,
        #         122,
        #         256 - 128,
        #         256 - 97,
        #         52,
        #         97,
        #         107,
        #         256 - 106,
        #         53,
        #         256 - 30,
        #         256 - 20,
        #         34,
        #         256 - 126,
        #         69,
        #         120,
        #         76,
        #         31,
        #         99,
        #         256 - 24,
        #         256 - 115,
        #         6,
        #     ]
        # )
        xqmauth_secret = bytes(
            [
                26,
                256 - 74,
                256 - 103,
                37,
                256 - 84,
                23,
                256 - 102,
                256 - 86,
                78,
                256 - 125,
                256 - 85,
                256 - 26,
                113,
                256 - 87,
                71,
                109,
                23,
                100,
                24,
                256 - 72,
                91,
                256 - 41,
                6,
                256 - 15,
                67,
                108,
                256 - 95,
                91,
                256 - 26,
                71,
                256 - 104,
                256 - 100,
            ]
        )
        xqmauth_val = hmac.new(
            xqmauth_secret,
            str(gmtime_100sec).encode("ascii", "ignore"),
            digestmod="sha256",
        ).hexdigest()

        # return "v1:c95f4fd2:" + xqmauth_val
        return "v1:01da27b0:" + xqmauth_val

    async def _async_get_azs_token(self, access_token: str) -> Any:
        """Get AZS Token."""
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "X-App-Version": HDR_XAPP_VERSION,
            "X-App-Name": "myAudi",
            "User-Agent": HDR_USER_AGENT,
            "Content-Type": "application/json; charset=utf-8",
        }
        asz_req_data = {
            "token": access_token,
            "grant_type": "id_token",
            "stage": "live",
            "config": "myaudi",
        }
        azs_token_rsptxt = await self.request(
            "POST",
            self._audi_baseurl + "/token",
            json.dumps(asz_req_data),
            headers=headers,
            allow_redirects=False,
        )
        azs_token_json = jload(azs_token_rsptxt)
        _LOGGER.debug("AZS Token: %s", azs_token_json)

        return azs_token_json

    async def _async_get_idk_token(self, client_id: str, **kwargs: Any) -> Any:
        """Get IDK Token."""
        refresh_token = kwargs.get("refresh_token")
        code = kwargs.get("code")
        code_verifier = kwargs.get("code_verifier")
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "X-QMAuth": self._calculate_x_qmauth(),
            "User-Agent": HDR_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        # IDK token request data
        if refresh_token:
            idk_data = {
                "client_id": client_id,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "response_type": "token id_token",
            }
        else:
            idk_data = {
                "client_id": client_id,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "myaudi:///",
                "response_type": "token id_token",
                "code_verifier": code_verifier,
            }

        # IDK token request
        encoded_idk_data = urlencode(idk_data, encoding="utf-8").replace("+", "%20")

        idk_token_rsptxt = await self.request(
            "POST",
            self._token_endpoint_url,
            encoded_idk_data,
            headers=headers,
            allow_redirects=False,
        )
        idk_token_json = jload(idk_token_rsptxt)
        _LOGGER.debug("IDK Token: %s", idk_token_json)

        return idk_token_json

    async def _async_register_idk(self) -> Any:
        """Register IDK."""
        # mbboauth client register
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "User-Agent": HDR_USER_AGENT,
            "Content-Type": "application/json; charset=utf-8",
        }
        mbboauth_reg_data = {
            "client_name": "SM-A405FN",
            "platform": "google",
            "client_brand": "Audi",
            "appName": "myAudi",
            "appVersion": HDR_XAPP_VERSION,
            "appId": "de.myaudi.mobile.assistant",
        }
        mbboauth_client_reg_rsptxt = await self.request(
            "POST",
            self._mbb_baseurl + "/mobile/register/v1",
            json.dumps(mbboauth_reg_data),
            headers=headers,
            allow_redirects=False,
        )
        mbboauth_client_reg_json = jload(mbboauth_client_reg_rsptxt)
        return mbboauth_client_reg_json.get("client_id")

    async def _async_get_mbb_token(self, x_client_id: str, **kwargs: Any) -> Any:
        """Authentification to IDK."""
        refresh_token = kwargs.get("refresh_token")
        id_token = kwargs.get("id_token")
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "User-Agent": HDR_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Client-ID": x_client_id,
        }
        if refresh_token:
            mbboauth_data = {
                "grant_type": "refresh_token",
                "token": refresh_token,
                "scope": "sc2:fal",
                # "vin": vin,  << App uses a dedicated VIN here, but it works without, don't know
            }
        else:
            mbboauth_data = {
                "grant_type": "id_token",
                "token": id_token,
                "scope": "sc2:fal",
            }
        encoded_mbboauth_data = urlencode(mbboauth_data, encoding="utf-8").replace(
            "+", "%20"
        )
        mbboauth_rsptxt = await self.request(
            "POST",
            self._mbb_baseurl + "/mobile/oauth2/v1/token",
            encoded_mbboauth_data,
            headers=headers,
            allow_redirects=False,
        )
        mbboauth_json = jload(mbboauth_rsptxt)
        _LOGGER.debug("MBB Token: %s", mbboauth_json)

        return mbboauth_json
