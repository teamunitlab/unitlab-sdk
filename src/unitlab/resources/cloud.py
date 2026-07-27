from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..types import CloudEntry
from ._base import Namespace, identifier

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient


class CloudNamespace(Namespace):
    def list(self) -> list[CloudStorage]:
        rows = self._all_pages("/api/sdk/cloud-storages/")
        return [CloudStorage._from_raw(self._client, row) for row in rows]

    def get(self, storage_id: str) -> CloudStorage:
        for storage in self.list():
            if storage.id == str(storage_id):
                return storage
        from ..exceptions import NotFoundError

        raise NotFoundError(f"Cloud storage {storage_id} was not found.")


@dataclass
class CloudStorage:
    id: str
    name: str
    provider: str
    resource: str
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    created: str = ""

    @classmethod
    def _from_raw(cls, client: UnitlabClient, raw: dict[str, Any]) -> CloudStorage:
        return cls(
            id=str(raw["pk"]),
            name=str(raw.get("display_name", "")),
            provider=str(raw.get("provider_type", "")),
            resource=str(raw.get("resource", "")),
            raw=raw,
            _client=client,
            created=str(raw.get("created", "")),
        )

    def browse(
        self,
        prefix: str = "",
        *,
        project=None,
        page_size: int = 500,
    ) -> Iterator[CloudEntry]:
        """Iterate through cloud objects across all response pages.

        Args:
            prefix: Provider path prefix to browse.
            project: Optional Project handle or ID for project-specific validation.
            page_size: Maximum entries requested per API page.

        Yields:
            Files and folders returned by the cloud provider.
        """
        next_token = None
        while True:
            params: dict[str, Any] = {
                "prefix": prefix,
                "page_size": page_size,
            }
            if project is not None:
                params["project"] = identifier(project)
            if next_token:
                params["next_token"] = next_token
            raw = self._client._api.get(
                f"/api/sdk/cloud-storages/{self.id}/browse/",
                params=params,
            )
            yield from (CloudEntry._from_raw(item) for item in raw.get("content", []))
            next_token = raw.get("next")
            if not next_token:
                return
