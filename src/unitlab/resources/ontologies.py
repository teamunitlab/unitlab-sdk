from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..ontology import OntologyStructure
from ..types import _data_type_name
from ._base import Namespace

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient


def _write_data_type(value: str) -> str:
    # The UI stores universal workspace Ontologies with the image compatibility
    # value; authoring and runtime routing are resolved independently.
    value = str(value).lower()
    return "image" if value == "multimodal" else value


class OntologiesNamespace(Namespace):
    def list(self, **filters) -> list[Ontology]:
        """List reusable workspace Ontologies.

        Args:
            **filters: Supported keys are ``title_eq``, ``title_like``,
                ``desc_eq``, ``desc_like``, ``created_before``, ``created_after``,
                ``edited_before``, and ``edited_after``. Date filters accept
                ISO-8601 dates or timestamps.

        Returns:
            Matching current, non-archived workspace Ontologies.
        """
        params = {key: value for key, value in filters.items() if value is not None}
        rows = self._all_pages("/api/sdk/ontologies/", params=params)
        return [Ontology._from_raw(self._client, row) for row in rows]

    def get(self, ontology_hash: str) -> Ontology:
        raw = self._api.get(f"/api/sdk/ontologies/{ontology_hash}/")
        return Ontology._from_raw(self._client, raw)

    def create(
        self,
        title: str,
        *,
        description: str = "",
        structure=None,
        data_type: str = "image",
    ) -> Ontology:
        """Create a reusable workspace Ontology immediately.

        Args:
            title: User-facing Ontology name.
            description: Optional purpose or usage notes.
            structure: ``OntologyStructure`` or compatible mapping.
            data_type: Compatibility family for the Ontology. ``multimodal``
                uses the UI's universal ``image`` default and does not restrict
                which entities the structure can contain.

        Returns:
            The created workspace Ontology.

        Note:
            There is no separate publish step. Creating the Ontology makes it
            available for Project creation.
        """
        structure = OntologyStructure() if structure is None else structure
        raw = self._api.post(
            "/api/sdk/ontologies/",
            json={
                "title": title,
                "description": description,
                "structure": (
                    structure.to_dict()
                    if hasattr(structure, "to_dict")
                    else dict(structure)
                ),
                "data_type": _write_data_type(data_type),
            },
        )
        return Ontology._from_raw(self._client, raw)


@dataclass
class Ontology:
    id: str
    title: str
    description: str
    structure: OntologyStructure
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    created_at: str = ""
    last_edited_at: str = ""
    data_type: str = "image"
    project_id: str | None = None

    @classmethod
    def _from_raw(cls, client: UnitlabClient, raw: dict[str, Any]) -> Ontology:
        return cls(
            id=str(raw["ontology_hash"]),
            title=str(raw.get("title", "")),
            description=str(raw.get("description", "")),
            structure=OntologyStructure.from_dict(raw.get("structure") or {}),
            raw=raw,
            _client=client,
            created_at=str(raw.get("created_at", "")),
            last_edited_at=str(raw.get("last_edited_at", "")),
            data_type=_data_type_name(raw.get("data_type")),
            project_id=(str(raw["project_id"]) if raw.get("project_id") else None),
        )

    def save(self) -> None:
        """Persist all mutable Ontology fields and create a revision.

        Raises:
            ValidationError: If the Ontology is immutable or the structure is
                invalid.
        """
        raw = self._client._api.request(
            "PUT",
            f"/api/sdk/ontologies/{self.id}/",
            json={
                "title": self.title,
                "description": self.description,
                "structure": self.structure.to_dict(),
                "data_type": _write_data_type(self.data_type),
            },
        )
        vars(self).update(vars(Ontology._from_raw(self._client, raw)))
