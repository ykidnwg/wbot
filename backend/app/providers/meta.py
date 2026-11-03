"""Meta OAuth and Pages API adapter boundary."""

from dataclasses import dataclass
from typing import Protocol, cast
from urllib.parse import urlencode

import httpx


@dataclass(frozen=True)
class MetaPage:
    external_id: str
    name: str
    access_token: str
    username: str | None
    profile_image_url: str | None
    metadata: dict[str, object]


@dataclass(frozen=True)
class MetaUser:
    external_id: str
    name: str


class MetaAdapter(Protocol):
    def authorization_url(self, state: str) -> str: ...

    async def exchange_code(self, code: str, redirect_uri: str) -> str: ...

    async def get_user(self, access_token: str) -> MetaUser: ...

    async def list_pages(self, access_token: str) -> list[MetaPage]: ...


@dataclass(frozen=True)
class MetaConfig:
    app_id: str
    app_secret: str
    graph_api_version: str
    redirect_uri: str


class MetaGraphAdapter:
    def __init__(self, config: MetaConfig) -> None:
        self.config = config
        self.base_url = f"https://graph.facebook.com/{config.graph_api_version}"

    def authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.config.app_id,
            "redirect_uri": self.config.redirect_uri,
            "state": state,
            "response_type": "code",
            "scope": (
                "pages_show_list,pages_manage_metadata,pages_manage_posts,"
                "pages_manage_read_engagement"
            ),
        }
        return f"https://www.facebook.com/{self.config.graph_api_version}/dialog/oauth?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self.base_url}/oauth/access_token",
                params={
                    "client_id": self.config.app_id,
                    "client_secret": self.config.app_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
        if response.status_code >= 400:
            raise ValueError("Meta authorization code exchange failed")
        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise ValueError("Meta authorization response did not contain an access token")
        return token

    async def get_user(self, access_token: str) -> MetaUser:
        payload = await self._get("/me", access_token, fields="id,name")
        external_id = payload.get("id")
        name = payload.get("name")
        if not isinstance(external_id, str) or not isinstance(name, str):
            raise ValueError("Meta user response is invalid")
        return MetaUser(external_id=external_id, name=name)

    async def list_pages(self, access_token: str) -> list[MetaPage]:
        payload = await self._get(
            "/me/accounts",
            access_token,
            fields="id,name,access_token,username,picture",
        )
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise ValueError("Meta pages response is invalid")
        pages: list[MetaPage] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            page_id_value = row.get("id")
            name_value = row.get("name")
            page_token_value = row.get("access_token")
            if not all(
                isinstance(value, str) and value
                for value in (page_id_value, name_value, page_token_value)
            ):
                continue
            page_id = cast(str, page_id_value)
            name = cast(str, name_value)
            page_token = cast(str, page_token_value)
            picture = row.get("picture")
            picture_data = picture.get("data") if isinstance(picture, dict) else None
            image_url = picture_data.get("url") if isinstance(picture_data, dict) else None
            pages.append(
                MetaPage(
                    external_id=page_id,
                    name=name,
                    access_token=page_token,
                    username=row.get("username") if isinstance(row.get("username"), str) else None,
                    profile_image_url=image_url if isinstance(image_url, str) else None,
                    metadata={key: value for key, value in row.items() if key != "access_token"},
                )
            )
        return pages

    async def _get(self, path: str, access_token: str, **params: str) -> dict[str, object]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self.base_url}{path}", params={"access_token": access_token, **params}
            )
        if response.status_code >= 400:
            raise ValueError("Meta API request failed")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Meta API response is invalid")
        return payload
