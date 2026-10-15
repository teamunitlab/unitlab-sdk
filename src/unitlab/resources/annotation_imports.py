from __future__ import annotations

import json
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ..exceptions import AnnotationImportError, ValidationError
from ._base import Namespace, identifier

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient

MAX_FILE_BYTES = 80 * 1024 * 1024
# Preview and commit re-check every row and item on the server; live runs on
# large files took over a minute, past the client's 60 s default.
SERVER_WORK_TIMEOUT = 300


class AnnotationImports(Namespace):
    """Preview and commit labels for media already linked to a Project."""

    def __init__(self, client: UnitlabClient, project_id: str):
        super().__init__(client)
        self.project_id = project_id

    @property
    def _endpoint(self) -> str:
        return f"/api/sdk/projects/{self.project_id}/annotation-imports/"

    def sources(self) -> list[dict[str, Any]]:
        return self._api.get(f"{self._endpoint}sources/")["sources"]

    def media(self, search: str = "") -> list[dict[str, Any]]:
        """Find up to 50 candidates for explicit media mappings."""
        return self._api.get(f"{self._endpoint}media/", params={"search": search})[
            "media"
        ]

    def create(
        self,
        annotation_file: str | Path | None = None,
        *,
        source_name: str | None = None,
        source_id: str | None = None,
        frame_mapping_file: str | Path | None = None,
        cloud_storage=None,
        annotation_key: str | None = None,
        frame_mapping_key: str | None = None,
        track_profile: Literal["none", "attributes.track_id"] = "none",
        options: dict[str, Any] | None = None,
    ) -> AnnotationImport:
        """Upload COCO, Unitlab export or native JSON and return a label preview.

        Supply a local ``annotation_file`` or a saved ``cloud_storage`` handle/ID
        and ``annotation_key``. JSON files are limited to 80 MiB each. Media must
        already belong to this project; use ``UploadBatch.wait()`` after upload.

        Exactly one prediction namespace, ``source_name`` or ``source_id``, is
        required. Reuse it for subsequent predictions from the same model.
        ``options`` accepts media/class/object/review mappings and ``stable_ids``
        (false by default). Enable stable IDs only if the exporter preserves them.
        COCO video requires an explicit frame mapping file or storage key.
        """
        local = annotation_file is not None
        cloud = cloud_storage is not None and bool(annotation_key)
        if local == cloud or (
            not cloud
            and any(
                value is not None
                for value in (cloud_storage, annotation_key, frame_mapping_key)
            )
        ):
            raise ValueError(
                "Supply a local JSON file or a cloud storage and JSON key."
            )
        if bool(source_name) == bool(source_id):
            raise ValueError("Supply exactly one of source_name or source_id.")
        if frame_mapping_file is not None and frame_mapping_key is not None:
            raise ValueError("Supply one frame mapping file or storage key.")
        if track_profile not in ("none", "attributes.track_id"):
            raise ValueError("Unknown track_profile.")

        import_options = deepcopy(options or {})
        data: dict[str, Any] = {
            "track_profile": track_profile,
            "options": import_options,
        }
        if source_id:
            data["source_id"] = identifier(source_id)
        else:
            data["source_name"] = source_name
        if cloud:
            data.update(
                cloud_storage_id=identifier(cloud_storage),
                annotation_key=annotation_key,
            )
        if frame_mapping_key is not None:
            data["frame_mapping_key"] = frame_mapping_key

        with ExitStack() as stack:
            files = {}
            for name, value in (
                ("annotation_file", annotation_file),
                ("frame_mapping_file", frame_mapping_file),
            ):
                if value is None:
                    continue
                path = Path(value)
                # GeoJSON exports keep their own extension; frame maps are .json.
                suffixes = (
                    (".json", ".geojson") if name == "annotation_file" else (".json",)
                )
                if not path.is_file() or path.suffix.lower() not in suffixes:
                    raise ValueError(f"{name} must be a JSON file: {path}")
                stream = stack.enter_context(path.open("rb"))
                stream.seek(0, 2)
                if stream.tell() > MAX_FILE_BYTES:
                    limit = MAX_FILE_BYTES // (1024 * 1024)
                    raise ValueError(f"{name} must be {limit} MiB or smaller.")
                stream.seek(0)
                files[name] = (path.name, stream, "application/json")
            if files:
                data["options"] = json.dumps(import_options, allow_nan=False)
                raw = self._api.post(
                    self._endpoint,
                    data=data,
                    files=files,
                    timeout=SERVER_WORK_TIMEOUT,
                )
            else:
                raw = self._api.post(
                    self._endpoint, json=data, timeout=SERVER_WORK_TIMEOUT
                )

        return AnnotationImport(
            id=str(raw["batch_id"]),
            project_id=self.project_id,
            source_id=str(raw["source_id"]),
            preview=raw,
            _client=self._client,
            _options=import_options,
        )


@dataclass
class AnnotationImport:
    id: str
    project_id: str
    source_id: str
    preview: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    _options: dict[str, Any] = field(repr=False)

    @property
    def _endpoint(self) -> str:
        return f"/api/sdk/projects/{self.project_id}/annotation-imports/{self.id}/"

    def refresh(self, *, options: dict[str, Any] | None = None) -> AnnotationImport:
        """Re-preview after media processing or mapping changes.

        Omit ``options`` to preserve them; supply a dict to replace them entirely.
        Examine the new preview before committing it. Committed batches cannot
        be refreshed; create another batch with the same source for reimports.
        """
        value = deepcopy(self._options if options is None else options)
        preview = self._client._api.post(f"{self._endpoint}preview/", json=value)
        self.preview = preview
        self._options = value
        return self

    def commit(
        self,
        *,
        decisions: dict[str, Literal["keep", "incoming", "skip"]] | None = None,
        allow_partial: bool = False,
        timeout: float = SERVER_WORK_TIMEOUT,
    ) -> dict[str, Any]:
        """Save this preview as labels; approval remains a separate review step.

        Conflicts and human deletions default to ``keep``. Blocked records reject
        the entire commit unless ``allow_partial=True``. A stale preview raises
        ConflictError without refreshing or overwriting human work. Repeating a
        successful commit returns its original report without duplicating labels,
        so after a timeout or a dropped connection call ``commit`` again with
        the same arguments. ``timeout`` is in seconds (the server checks every
        item again first, which can take over a minute).

        Raises:
            AnnotationImportError: Blocked records or file issues and
                ``allow_partial=False``; ``rows`` and ``issues`` list them from
                this preview, and nothing was written.
        """
        try:
            return self._client._api.post(
                f"{self._endpoint}commit/",
                json={
                    "token": self.preview["token"],
                    "decisions": decisions or {},
                    "allow_partial": allow_partial,
                },
                timeout=timeout,
            )
        except ValidationError as exc:
            # The token matched, so the server judged exactly this preview:
            # name its blocked rows instead of the server's one-line refusal.
            rows = [
                row
                for row in self.preview.get("annotations") or []
                if row.get("status") == "blocked"
            ]
            issues = self.preview.get("issues") or []
            if not (rows or issues):
                raise
            raise AnnotationImportError(
                f"{exc.message} Pass allow_partial=True to skip them.",
                exc,
                rows=rows,
                issues=issues,
                batch_id=self.id,
            ) from exc
