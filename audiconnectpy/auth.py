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

import aiohttp
import async_timeout
from bs4 import BeautifulSoup

from .exceptions import (
    AudiException,
    AuthorizationError,
    HttpRequestError,
    ServiceNotFoundError,
    TimeoutExceededError,
)

TIMEOUT = 120
DELAY = 10
HDR_XAPP_VERSION = "4.24.2"
HDR_USER_AGENT = "Android/4.24.2 (Build 800240338.root project 'onetouch-android'.ext.buildTime) Android/11"
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
            async with async_timeout.timeout(TIMEOUT):
                _LOGGER.debug("REQUEST HEADERS: %s", kwargs.get("headers"))
                _LOGGER.debug("REQUEST: %s", url)
                _LOGGER.debug("REQUEST DATA:%s", kwargs.get("data"))
                response = await self._session.request(method, url, **kwargs)
        except (asyncio.CancelledError, asyncio.TimeoutError) as error:
            raise TimeoutExceededError(
                "Timeout occurred while connecting to Audi Connect."
            ) from error
        except (aiohttp.ClientError, socket.gaierror) as error:
            raise HttpRequestError(
                "Error occurred while communicating with Audi Connect."
            ) from error

        content_type = response.headers.get("Content-Type", "")
        contents = (await response.read()).decode("utf8")

        _LOGGER.debug("RESPONSE HEADERS: %s", response.headers)
        _LOGGER.debug("RESPONSE: %s ,return_code '%s'", contents, response.status)

        if response.status // 100 in [4, 5]:
            response.close()
            if "application/json" in content_type:
                raise ServiceNotFoundError(response.status, json.loads(contents))
            raise ServiceNotFoundError(response.status, contents)

        if raw_reply and raw_rsp is False:
            return response

        if "application/json" in content_type:
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

        if raw_reply and raw_rsp:
            return response, rsp
        return rsp

    async def async_connect(
        self, username: str, password: str, uris: dict[str, str], tries: int = 3
    ) -> None:
        """Connect to API."""
        try:
            self.uris = uris
            await self._async_login(username, password)
        except HttpRequestError as error:
            if tries > 1:
                _LOGGER.warning(
                    "Login to Audi service failed, trying again in %s seconds [ERROR:%s]",
                    DELAY,
                    str(error),
                )
                await asyncio.sleep(DELAY)
                return await self.async_connect(username, password, uris, tries - 1)

            raise AuthorizationError("Login to Audi service failed: %s ", error)

    async def _async_login(self, user: str, password: str) -> None:
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
        submit_data = self._get_hidden_html_input_form_data(idk_rsptxt, {"email": user})
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
            id_token=self._idk_token["access_token"]
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

    async def async_refresh_tokens(self) -> None:
        """Refresh token if."""
        if self._mbb_token_expired and datetime.now() > self._mbb_token_expired:
            try:
                _LOGGER.debug("Refresh token if necessary")
                # MBB Token
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

                # IDK Token
                self._idk_token = await self._async_get_idk_token(
                    refresh_token=self._idk_token["refresh_token"]
                )

                # Audi token
                self._audi_token = await self._async_get_azs_token(
                    id_token=self._idk_token["access_token"]
                )

                # Here token
                self._here_token = await self._async_get_here_token(
                    id_token=self._idk_token["id_token"]
                )

            except AudiException as error:  # pylint: disable=broad-except
                _LOGGER.error("Refresh token failed: %s", str(error))

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
