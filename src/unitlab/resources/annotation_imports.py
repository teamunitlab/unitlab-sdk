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

# The server's cap (nbackend annotation_import_service.MAX_FILE_BYTES): a batch
# stores its parsed rows as one jsonb value, which PostgreSQL caps at ~256 MiB,
# and parsed rows take 2.2-2.8x the file. Checked here so a larger file fails
# before its upload instead of with the server's 400 after it.
MAX_FILE_BYTES = 80 * 1024 * 1024
# Preview and commit re-check every row and item on the server; live runs on
# large files took over a minute, past the client's 60 s default.
SERVER_WORK_TIMEOUT = 300


def _check_benchmark_preview(
    options: dict[str, Any], preview: dict[str, Any], batch_id: str
) -> None:
    """Refuse a benchmark import the server previewed as an ordinary one.

    A server without benchmark imports ignores the unknown ``benchmark``
    option and would commit the labels onto the items themselves. A server
    that has them always answers with a top-level ``benchmark`` block, so its
    absence means the option was dropped. The preview writes nothing, so
    refusing here (and again before ``commit``) leaves nothing behind.
    """
    if options.get("benchmark") and "benchmark" not in preview:
        raise AnnotationImportError(
            "This Unitlab server does not support benchmark imports yet; "
            "nothing was imported.",
            code="benchmark_unsupported",
            batch_id=batch_id,
        )


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
        benchmark: bool = False,
        approve_keys: bool = False,
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

        ``benchmark=True`` writes the labels into each matched item's hidden
        benchmark answer key instead of the item: the item and its own labels
        are untouched, an existing key is replaced, and Data Group panels fill
        the group's key. ``approve_keys=True`` (only with ``benchmark=True``)
        approves each non-empty key when the import commits; a key the server
        refuses stays a draft and is listed in the report. Media must already be
        in the project: upload, then ``UploadBatch.wait()``. Both are sent as
        ``options`` keys; a ``True`` keyword overrides the same key in
        ``options``, and ``refresh(options=...)`` keeps them. A server
        without benchmark imports raises ``AnnotationImportError``
        (``code="benchmark_unsupported"``) here, before anything is written.
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
        # Only True is written, so imports without the flags send the same
        # options as before and a default False never clears a caller's key.
        if benchmark:
            import_options["benchmark"] = True
        if approve_keys:
            import_options["approve_keys"] = True
        # The server answers 400 for this; refuse before uploading the file.
        if import_options.get("approve_keys") and not import_options.get("benchmark"):
            raise ValueError("approve_keys requires benchmark=True.")
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
                    raise ValueError(f"{name} must be 80 MiB or smaller.")
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

        _check_benchmark_preview(import_options, raw, str(raw["batch_id"]))
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
        A benchmark batch keeps ``benchmark`` and, unless ``options`` names it,
        ``approve_keys``; ``"benchmark": False`` raises ``ValueError``. A
        benchmark preview without its ``benchmark`` block raises
        ``AnnotationImportError`` and ``commit()`` refuses the batch.
        """
        value = deepcopy(self._options if options is None else options)
        # Replacing options must not turn a benchmark batch into an ordinary
        # one: its commit would write the labels onto the live items.
        if self._options.get("benchmark"):
            if "benchmark" in value and not value["benchmark"]:
                raise ValueError(
                    "A benchmark import stays a benchmark import; "
                    "start a new one instead."
                )
            value["benchmark"] = True
            if "approve_keys" not in value and self._options.get("approve_keys"):
                value["approve_keys"] = True
        preview = self._client._api.post(f"{self._endpoint}preview/", json=value)
        self.preview = preview
        self._options = value
        # After storing it, so commit() refuses this batch too.
        _check_benchmark_preview(value, preview, self.id)
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
        item again first, which can take over a minute). A benchmark import's
        report also has ``benchmarks``: ``created``, ``replaced`` and
        ``approved`` counts, ``not_approved`` (``name``, ``reason``) and
        ``items`` (``reference``, ``gold_label_id``, ``datasource_id``,
        ``group_id``).

        Raises:
            AnnotationImportError: Blocked records or file issues and
                ``allow_partial=False``; ``rows`` and ``issues`` list them from
                this preview, and nothing was written. Also raised, with
                ``code="benchmark_unsupported"``, when ``benchmark`` was
                requested and the server previewed an ordinary import.
        """
        _check_benchmark_preview(self._options, self.preview, self.id)
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
