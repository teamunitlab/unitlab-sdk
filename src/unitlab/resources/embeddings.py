from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ._base import Namespace, identifier

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient


class EmbeddingSpacesNamespace(Namespace):
    def list(self) -> list[EmbeddingSpace]:
        rows = self._all_pages("/api/sdk/embedding-spaces/")
        return [EmbeddingSpace._from_raw(self._client, row) for row in rows]

    def create(
        self,
        name: str,
        *,
        dimensions: int,
        model_name: str | None = None,
    ) -> EmbeddingSpace:
        payload: dict[str, Any] = {"name": name, "dimensions": dimensions}
        if model_name is not None:
            payload["model_name"] = model_name
        raw = self._api.post("/api/sdk/embedding-spaces/", json=payload)
        return EmbeddingSpace._from_raw(self._client, raw)

    def get(self, space_id: str) -> EmbeddingSpace:
        raw = self._api.get(f"/api/sdk/embedding-spaces/{identifier(space_id)}/")
        return EmbeddingSpace._from_raw(self._client, raw)


@dataclass
class EmbeddingSpace:
    id: str
    name: str
    dimensions: int
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    model_name: str | None = None
    ann_index_status: str | None = None
    vector_search_supported: bool = True

    @classmethod
    def _from_raw(
        cls,
        client: UnitlabClient,
        raw: dict[str, Any],
    ) -> EmbeddingSpace:
        return cls(
            id=str(raw.get("id") or raw["pk"]),
            name=str(raw.get("name", "")),
            dimensions=int(raw["dimensions"]),
            model_name=(
                str(raw["model_name"]) if raw.get("model_name") is not None else None
            ),
            ann_index_status=(
                str(raw["ann_index_status"])
                if raw.get("ann_index_status") is not None
                else None
            ),
            vector_search_supported=bool(raw.get("vector_search_supported", True)),
            raw=raw,
            _client=client,
        )

    def delete(self) -> None:
        self._client._api.request(
            "DELETE",
            f"/api/sdk/embedding-spaces/{self.id}/",
        )

    def upsert(
        self,
        asset_id,
        vector: Sequence[float],
        *,
        frame_index: int | None = None,
    ) -> dict[str, Any]:
        item: dict[str, Any] = {
            "asset_id": identifier(asset_id),
            "vector": list(vector),
        }
        if frame_index is not None:
            item["frame_index"] = frame_index
        return self.upsert_many([item])

    def upsert_many(
        self,
        items: Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:
        prepared = []
        for item in items:
            row = {
                "asset_id": identifier(item["asset_id"]),
                "vector": list(item["vector"]),
            }
            if item.get("frame_index") is not None:
                row["frame_index"] = item["frame_index"]
            prepared.append(row)
        return self._client._api.post(
            f"/api/sdk/embedding-spaces/{self.id}/vectors/",
            json={"items": prepared},
        )

    def search(
        self,
        vector: Sequence[float],
        *,
        limit: int | None = None,
        project_id=None,
        level: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"vector": list(vector)}
        if limit is not None:
            payload["limit"] = limit
        if project_id is not None:
            payload["project_id"] = identifier(project_id)
        if level is not None:
            payload["level"] = level
        return self._client._api.post(
            f"/api/sdk/embedding-spaces/{self.id}/search/",
            json=payload,
        )
