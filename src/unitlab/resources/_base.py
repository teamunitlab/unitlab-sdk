from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient


class Namespace:
    def __init__(self, client: UnitlabClient):
        self._client = client

    @property
    def _api(self):
        return self._client._api

    def _all_pages(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        payload = self._api.get(endpoint, params=params)
        if isinstance(payload, list):
            return payload
        rows = list(payload.get("results", []))
        next_url = payload.get("next")
        while next_url:
            parsed = urlsplit(next_url)
            page = self._api.get(
                f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
            )
            rows.extend(page.get("results", []))
            next_url = page.get("next")
        return rows


def identifier(value: Any) -> str:
    candidate = getattr(value, "id", value)
    return str(candidate)
