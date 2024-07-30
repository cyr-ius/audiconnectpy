"""Audi connect."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta
from hashlib import sha256
import json
import logging
import os
import re
import socket
from typing import Any, Literal
from urllib.parse import parse_qs, urlencode, urlparse
import uuid

from aiohttp import ClientError, ClientResponseError, ClientSession
from bs4 import BeautifulSoup

from .const import (
    CLIENT_IDS,
    DELAY,
    HDR_USER_AGENT,
    HDR_XAPP_VERSION,
    MARKET_URL,
    MBB_URL,
    TIMEOUT,
    URL_HERE_COM,
    URL_INFO_USER,
)
from .exceptions import (
    AudiException,
    AuthorizationError,
    HttpRequestError,
    ServiceNotFoundError,
    TimeoutExceededError,
)
from .helpers import ExtendedDict, retry

_LOGGER = logging.getLogger(__name__)


class Auth:
    """Authentication."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        country: str,
        model: Literal["standard", "e-tron"],
        *,
        proxy: str | None = None,
    ) -> None:
        """Initialize."""
        self._session = session
        self._username = username
        self._password = password
        self.country = country
        self.model = model
        self.__proxy: dict[str, str] | None = (
            {"http": proxy, "https": proxy} if proxy else None
        )

        self._x_client_id: str | None = None
        self.user_id = ""
        self._mbb_token: dict[str, Any] = {}
        self._here_token: dict[str, Any] = {}
        self._mbb_token_expired: datetime | None = None
        self._idk_token: dict[str, str] = {}
        self._audi_token: dict[str, str] = {}
        self.uris: dict[str, str] = {}
        self.binded: bool = False

    async def request(
        self,
        method: str,
        url: str,
        raw_reply: bool = False,
        raw_rsp: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Request url with method."""
        try:
            async with asyncio.timeout(TIMEOUT):
                _LOGGER.debug("Request - Header: %s", kwargs.get("headers"))
                _LOGGER.debug("Request: %s (%s) - %s", url, method, kwargs.get("data"))
                response = await self._session.request(method, url, **kwargs)
                contents = await response.read()
                response.raise_for_status()
        except (asyncio.CancelledError, asyncio.TimeoutError) as error:
            raise TimeoutExceededError(
                "Timeout occurred while connecting to Audi Connect."
            ) from error
        except ClientResponseError as error:
            message = contents.decode("utf8")
            if "application/json" in response.headers.get("Content-Type", ""):
                message = json.loads(message)
                if msg := message.get("error", {}).get("message"):
                    message = msg
            raise ServiceNotFoundError(
                f"Service not found: {url} - {message} ({response.status})"
            ) from error
        except (ClientError, socket.gaierror) as error:
            raise HttpRequestError(
                "Error occurred while communicating with Audi Connect."
            ) from error

        _LOGGER.debug("Response - Headers: %s", response.headers)
        _LOGGER.debug("Response: %s (%s)", contents, response.status)
        _LOGGER.debug("---------------------------------------------------------")

        if raw_reply and raw_rsp is False:
            return response

        if "application/json" in response.headers.get("Content-Type", ""):
            rsp = await response.json()
        elif (
            (headers := kwargs.get("headers"))
            and "application/json" in headers.get("Accept", "")
            and contents == ""
        ):
            _LOGGER.debug("JSON FIX: Accept is JSON but Response is None")
            rsp = {}
        else:
            rsp = await response.text()

        return (response, rsp) if raw_reply and raw_rsp else rsp

    async def async_connect(self, tries: int = 3) -> None:
        """Connect to API."""
        try:
            await self._async_retrieve_url_service()
        except HttpRequestError as error:
            self.binded = False
            raise AudiException(f"Failed retrieve urls service ({error})") from error

        try:
            await self._async_login()
            self.binded = True
        except AudiException as error:
            self.binded = False
            raise AuthorizationError("Login to Audi service failed") from error

    @retry(exceptions=HttpRequestError, tries=3, delay=DELAY, logger=_LOGGER)
    async def _async_login(self) -> None:
        """Request login."""

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
        headers = await self.async_get_headers()
        idk_data = {
            "response_type": "code",
            "client_id": self.uris["client_id"],
            "redirect_uri": "myaudi:///",
            "scope": "address badge birthdate birthplace email gallery mbb name nationalIdentifier nationality nickname phone picture profession profile vin openid",
            "state": str(uuid.uuid4()),
            "nonce": str(uuid.uuid4()),
            "prompt": "login",
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "ui_locales": f"{self.uris['language']}-{self.uris['language']} {self.uris['language']}",
        }
        idk_rsp, idk_rsptxt = await self.request(
            "GET",
            self.uris["authorization_endpoint"],
            headers=headers,
            params=idk_data,
            raw_reply=True,
            raw_rsp=True,
        )

        # form_data with email
        submit_data = self._get_hidden_html_input_form_data(
            idk_rsptxt, {"email": self._username}
        )
        submit_url = self._get_post_url(idk_rsptxt, self.uris["authorization_endpoint"])
        # send email
        email_rsptxt = await self.request(
            "POST",
            submit_url,
            data=submit_data,
            headers=headers,
            cookies=idk_rsp.cookies,
            allow_redirects=True,
        )

        # form_data with password
        # 2022-01-29: new HTML response uses a js two build the html form data + button.
        # Therefore it's not possible to extract hmac and other form data.
        # --> extract hmac from embedded js snippet.
        regex_res = re.findall(r'"hmac"\s*:\s*"[0-9a-fA-F]+"', email_rsptxt)
        if regex_res:
            submit_url = submit_url.replace("identifier", "authenticate")
            submit_data["hmac"] = regex_res[0].split(":")[1].strip('"')
            submit_data["password"] = self._password
        else:
            submit_data = self._get_hidden_html_input_form_data(
                email_rsptxt, {"password": self._password}
            )
            submit_url = self._get_post_url(email_rsptxt, submit_url)

        # send password
        pw_rsp = await self.request(
            "POST",
            submit_url,
            data=submit_data,
            headers=headers,
            cookies=idk_rsp.cookies,
            allow_redirects=False,
            raw_reply=True,
        )

        pw_strings = parse_qs(urlparse(pw_rsp.headers.get("Location", {}))[4]).get(
            "userId", []
        )
        self.user_id = pw_strings[0] if pw_strings else ""

        # forward1 after pwd
        fwd1_rsp = await self.request(
            "GET",
            pw_rsp.headers.get("Location", {}),
            headers=headers,
            cookies=idk_rsp.cookies,
            allow_redirects=False,
            raw_reply=True,
        )

        # forward2 after pwd
        fwd2_rsp = await self.request(
            "GET",
            fwd1_rsp.headers.get("Location", {}),
            headers=headers,
            cookies=idk_rsp.cookies,
            allow_redirects=False,
            raw_reply=True,
        )

        # get tokens
        codeauth_rsp = await self.request(
            "GET",
            fwd2_rsp.headers.get("Location", {}),
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
            code=authcode_strings["code"][0], code_verifier=code_verifier
        )

        # Audi token
        self._audi_token = await self._async_get_azs_token(
            id_token=self._idk_token["id_token"]
        )

        # mbboauth client register
        self._x_client_id = await self._async_register_idk()

        # MBB token
        self._mbb_token = await self._async_get_mbb_token(
            id_token=self._idk_token["id_token"]
        )

        # mbboauth refresh (app immediately refreshes the token)
        refresh_token = self._mbb_token["refresh_token"]
        self._mbb_token = await self._async_get_mbb_token(
            refresh_token=self._mbb_token["refresh_token"]
        )

        self._mbb_token["refresh_token"] = refresh_token
        self._mbb_token_expired = datetime.now() + timedelta(
            seconds=self._mbb_token["expires_in"]
        )

        # Here token
        self._here_token = await self._async_get_here_token(
            id_token=self._idk_token["id_token"]
        )
        if "refresh_token" in self._here_token:
            self._mbb_token["refresh_token"] = self._here_token["refresh_token"]

    async def async_refresh_tokens(self) -> None:
        """Refresh token if."""
        if self._mbb_token_expired and datetime.now() > self._mbb_token_expired:
            try:
                _LOGGER.debug("Refresh MBB token")
                refresh_token = self._mbb_token["refresh_token"]
                self._mbb_token = await self._async_get_mbb_token(
                    refresh_token=refresh_token
                )
                # TR/2022-02-10: If a new refresh_token is provided, save it for further refreshes
                if "refresh_token" not in self._mbb_token:
                    _LOGGER.debug("refresh token not provided")
                    self._mbb_token["refresh_token"] = refresh_token

                self._mbb_token_expired = datetime.now() + timedelta(
                    seconds=self._mbb_token["expires_in"]
                )

                _LOGGER.debug("Refresh IDK token")
                self._idk_token = await self._async_get_idk_token(
                    refresh_token=self._idk_token["refresh_token"]
                )

                _LOGGER.debug("Refresh Audi token")
                self._audi_token = await self._async_get_azs_token(
                    id_token=self._idk_token["id_token"]
                )

                _LOGGER.debug("Refresh Here token")
                self._here_token = await self._async_get_here_token(
                    id_token=self._idk_token["id_token"]
                )
                if "refresh_token" in self._here_token:
                    self._mbb_token["refresh_token"] = self._here_token["refresh_token"]

            except AudiException as error:
                _LOGGER.error("Refresh token failed: %s", error)
                self.binded = False

    async def async_get_action_headers(
        self, content_type: str, security_token: str | None, x_security: bool = False
    ) -> dict[str, str]:
        """Return header for vehicle action."""
        headers = {
            "Content-Type": content_type,
            "User-Agent": "okhttp/3.11.0",
        }

        if security_token and x_security is False:
            headers.update({"x-mbbSecToken": security_token})

        if security_token and x_security is True:
            headers.update({"X-securityToken": security_token})

        headers = await self.async_get_headers(token_type="mbb", headers=headers)

        return headers

    async def async_get_headers(
        self,
        token_type: Literal["idk", "mbb", "audi", "here"] | None = None,
        headers: dict[str, Any] | None = None,
        okhttp: bool = False,
        security_token: str | None = None,
    ) -> dict[str, str]:
        """Get simple headers."""
        defaults = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "User-Agent": HDR_USER_AGENT,
            "X-App-Name": "myAudi",
            "X-App-Version": HDR_XAPP_VERSION,
        }
        if security_token:
            defaults.update(
                {"User-Agent": "okhttp/3.11.0", "x-mbbSecToken": security_token}
            )
            token_type = "mbb"

        if token_type in ["mbb", "idk", "audi", "here"]:
            _LOGGER.debug("TOKEN TYPE: %s", token_type)
            await self.async_refresh_tokens()
            match token_type:
                case "idk":
                    token = self._idk_token.get("access_token")
                case "mbb":
                    token = self._mbb_token.get("access_token")
                case "audi":
                    token = self._audi_token.get("access_token")
                case "here":
                    token = self._here_token.get("access_token")
            defaults.update({"Authorization": f"Bearer {token}"})
        if self._x_client_id:
            defaults.update({"X-Client-ID": self._x_client_id})
        if okhttp:
            defaults.update({"User-Agent": "okhttp/3.11.0"})
        if headers:
            defaults.update(headers)

        return defaults

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

    async def _async_get_azs_token(self, **kwargs: Any) -> Any:
        """Get AZS Token."""
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "User-Agent": HDR_USER_AGENT,
            "X-App-Name": "myAudi",
            "X-App-Version": HDR_XAPP_VERSION,
            "Content-Type": "application/json",
        }
        asz_req_data = {
            "grant_type": "id_token",
            "token": kwargs.get("id_token"),
            "stage": "live",
            "config": "myaudi",
        }
        azs_token_json = await self.request(
            "POST",
            self.uris["audi_url"] + "/token",
            json=asz_req_data,
            headers=headers,
            allow_redirects=False,
        )
        _LOGGER.debug("AZS Token: %s", azs_token_json)
        return azs_token_json

    async def _async_get_idk_token(self, **kwargs: Any) -> Any:
        """Get IDK Token."""
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "User-Agent": HDR_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        # IDK token request data
        if "refresh_token" in kwargs:
            idk_data = {
                "client_id": self.uris["client_id"],
                "grant_type": "refresh_token",
                "refresh_token": kwargs.get("refresh_token"),
                "response_type": "token id_token",
            }
        else:
            idk_data = {
                "client_id": self.uris["client_id"],
                "grant_type": "authorization_code",
                "code": kwargs.get("code"),
                "redirect_uri": "myaudi:///",
                "response_type": "token id_token",
                "code_verifier": kwargs.get("code_verifier"),
            }

        # IDK token request
        encoded_idk_data = urlencode(idk_data, encoding="utf-8").replace("+", "%20")

        idk_token_json = await self.request(
            "POST",
            self.uris["token_endpoint"],
            data=encoded_idk_data,
            headers=headers,
            allow_redirects=False,
        )
        _LOGGER.debug("IDK Token: %s", idk_token_json)

        return idk_token_json

    async def _async_register_idk(self) -> str:
        """Register IDK.

        Return X-Client-ID
        """
        # mbboauth client register
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "User-Agent": HDR_USER_AGENT,
            "Content-Type": "application/json",
        }
        mbboauth_reg_data = {
            "client_name": "SM-A405FN",
            "platform": "google",
            "client_brand": "Audi",
            "appName": "myAudi",
            "appVersion": HDR_XAPP_VERSION,
            "appId": "de.myaudi.mobile.assistant",
        }
        mbboauth_client_reg_json = await self.request(
            "POST",
            self.uris["mbb_url"] + "/mobile/register/v1",
            json=mbboauth_reg_data,
            headers=headers,
            allow_redirects=False,
        )
        return str(mbboauth_client_reg_json.get("client_id", ""))

    async def _async_get_mbb_token(self, **kwargs: Any) -> Any:
        """Authentication to mbboauth-1d.prd.ece.vwg-connect.com."""
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "User-Agent": HDR_USER_AGENT,
            "X-App-Name": "myAudi",
            "X-App-Version": HDR_XAPP_VERSION,
            "X-Client-ID": self._x_client_id,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if "refresh_token" in kwargs:
            mbboauth_data = {
                "grant_type": "refresh_token",
                "token": kwargs.get("refresh_token"),
                "scope": "sc2:fal",
                # "vin": vin,  #  << App uses a dedicated VIN here, but it works without, don't know
            }
        else:
            mbboauth_data = {
                "grant_type": "id_token",
                "token": kwargs.get("id_token"),
                "scope": "sc2:fal",
            }
        encoded_mbboauth_data = urlencode(mbboauth_data, encoding="utf-8").replace(
            "+", "%20"
        )
        mbboauth_json = await self.request(
            "POST",
            self.uris["mbb_url"] + "/mobile/oauth2/v1/token",
            data=encoded_mbboauth_data,
            headers=headers,
            allow_redirects=False,
        )
        _LOGGER.debug("MBB Token: %s", mbboauth_json)
        return mbboauth_json

    async def _async_get_here_token(self, **kwargs: Any) -> Any:
        """Authentication to Here.com."""
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "User-Agent": HDR_USER_AGENT,
            "X-Client-ID": self._x_client_id,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if "refresh_token" in kwargs:
            hereoauth_data = {
                "grant_type": "refresh_token",
                "token": kwargs.get("refresh_token"),
                "scope": "sc2:here_a_t21-s",
            }
        else:
            hereoauth_data = {
                "grant_type": "id_token",
                "token": kwargs.get("id_token"),
                "scope": "sc2:here_a_t21-s",
            }

        encoded_hereoauth_data = urlencode(hereoauth_data, encoding="utf-8").replace(
            "+", "%20"
        )
        hereoauth_json = await self.request(
            "POST",
            self.uris["mbb_url"] + "/mobile/oauth2/v1/token",
            data=encoded_hereoauth_data,
            headers=headers,
            allow_redirects=False,
        )
        _LOGGER.debug("Here Token: %s", hereoauth_json)
        return hereoauth_json

    async def _async_retrieve_url_service(self) -> None:
        """Get urls for request."""
        # Get markets to get language
        markets_json = await self.request("GET", f"{MARKET_URL}/markets")

        country_spec = ExtendedDict(markets_json).getr(
            "countries.countrySpecifications"
        )
        if self.country not in country_spec:
            raise AudiException("Country not found")

        language = country_spec[self.country].get("defaultLanguage")

        # Get market without locale
        market_json = await self.request("GET", f"{MARKET_URL}/market")
        vdgqs_url = market_json.get("vehicleDomainGraphQLServiceURLLive")

        # Get market with locale
        services = await self.request(
            "GET", f"{MARKET_URL}/market/{self.country}/{language}"
        )

        client_id = services.get("idkClientIDAndroidLive", CLIENT_IDS[self.model])
        audi_url = services.get("myAudiAuthorizationServerProxyServiceURLProduction")
        profil_url = services.get("idkCustomerProfileMicroserviceBaseURLLive")
        mbb_url = services.get("mbbOAuthBaseURLLive", MBB_URL)
        mdk_url = services.get("mobileDeviceKeyBaseURLProduction")
        cvvsb_url = services.get("connectedVehicleVehicleServiceBaseURLProduction")
        oidc_url = services.get("idkLoginServiceConfigurationURLProduction")

        # Get openId config
        _LOGGER.debug("IDK Base Url: %s", oidc_url)
        openid_json = await self.request("GET", oidc_url)

        authorization_endpoint_url = openid_json.get("authorization_endpoint", "")
        token_endpoint_url = openid_json.get("token_endpoint", "")
        revocation_endpoint_url = openid_json.get("revocation_endpoint", "")

        self.uris = {
            "client_id": client_id,
            "audi_url": audi_url,
            "profil_url": f"{profil_url}/v3",
            "mbb_url": mbb_url,
            "here_url": URL_HERE_COM,
            "mdk_url": mdk_url,
            "cv_url": cvvsb_url,
            "user_url": URL_INFO_USER,
            "vdgqs_url": vdgqs_url,
            "authorization_endpoint": authorization_endpoint_url,
            "token_endpoint": token_endpoint_url,
            "revocation_endpoint": revocation_endpoint_url,
            "language": language,
            "country": self.country,
        }

        _LOGGER.debug("Urls of service: %s", self.uris)
