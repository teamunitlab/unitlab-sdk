from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import _downloader
from .._waiter import wait_for_status
from ..exceptions import UnitlabError
from ..types import ProcessingStatus, _data_type_name
from ._base import Namespace, identifier

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient


class ReleasesNamespace(Namespace):
    def list(self) -> list[Release]:
        rows = self._api.get("/api/sdk/releases/")
        return [Release._from_raw(self._client, row) for row in rows]

    def get(self, release_id: str) -> Release:
        raw = self._api.get(f"/api/sdk/releases/{release_id}/")
        return Release._from_raw(self._client, raw)

    def create(
        self,
        project,
        *,
        export_type: str = "UUEF",
        split_ratios: dict[str, int] | None = None,
        include_download_tokens: bool = False,
        upload_sessions=None,
        data_types=None,
        bundle_formats: dict[str, str] | None = None,
        license_id: str | None = None,
        wait: bool = True,
        timeout: float = 7200,
    ) -> Release:
        """Create an annotation Release from a Project snapshot.

        The backend prepares a Release in the background and answers at once
        with a pending one. Waiting is the default so scripts that create and
        then download keep working unchanged; pass ``wait=False`` to get the
        pending Release back and call ``release.wait()`` later.

        A second create while one is still being prepared raises
        ``ConflictError`` (code ``release_in_progress``). It is deliberately not
        attached to the in-flight Release, whose format or splits may differ.

        Args:
            project: Project handle or ID.
            export_type: Primary annotation export format.
            split_ratios: Percentage assigned to each output split.
            include_download_tokens: Include persistent Unitlab item download tokens.
                The Unitlab token URL remains valid; a customer-cloud signed
                target URL returned by it is temporary.
            upload_sessions: Optional Batch Queue handles or IDs to include.
            data_types: Optional public data types to include. ``multimodal``
                includes every available concrete type.
            bundle_formats: Per-concrete-data-type formats for multimodal bundles.
            license_id: Optional Dataset license ID.
            wait: Block until the Release is ready or has failed.
            timeout: Seconds to wait for preparation when ``wait`` is true.

        Returns:
            The created Release; ready when ``wait`` is true.
        """
        payload: dict[str, Any] = {
            "export_type": export_type,
            "split_ratios": split_ratios or {"train": 100},
            "include_download_tokens": include_download_tokens,
        }
        if upload_sessions is not None:
            payload["upload_sessions"] = [
                identifier(value) for value in upload_sessions
            ]
        if data_types is not None:
            normalized_types = [str(value).lower() for value in data_types]
            if "multimodal" not in normalized_types:
                payload["generic_types"] = [
                    "img" if value == "image" else value for value in normalized_types
                ]
        if bundle_formats is not None:
            if any(str(value).lower() == "multimodal" for value in bundle_formats):
                raise ValueError(
                    "bundle_formats must use concrete data types such as image, "
                    "medical, or text."
                )
            payload["bundle_formats"] = {
                (
                    "img"
                    if str(data_type).lower() == "image"
                    else str(data_type).lower()
                ): export_format
                for data_type, export_format in bundle_formats.items()
            }
        if license_id is not None:
            payload["license"] = identifier(license_id)
        # The long request timeout stays: a backend that predates background
        # preparation still builds the whole Release inside this POST.
        raw = self._api.post(
            f"/api/sdk/projects/{identifier(project)}/releases/",
            json=payload,
            timeout=600.0,
        )
        release = Release._from_raw(self._client, raw)
        return release.wait(timeout=timeout) if wait else release


@dataclass
class Release:
    id: str
    name: str
    version: str
    data_item_count: int
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    data_type: str = ""
    is_public: bool = False
    # "pending" | "exporting" | "ready" | "failed". None means the backend
    # predates background preparation, where every returned Release is ready.
    status: str | None = None
    progress: int | None = None
    status_error: str | None = None

    @classmethod
    def _from_raw(cls, client: UnitlabClient, raw: dict[str, Any]) -> Release:
        return cls(
            id=str(raw["pk"]),
            name=str(raw.get("name", "")),
            version=str(raw.get("version", "")),
            # number_of_data is null until the Release has been frozen.
            data_item_count=int(raw.get("number_of_data") or 0),
            raw=raw,
            _client=client,
            data_type=_data_type_name(raw.get("generic_type")),
            is_public=bool(raw.get("is_public", False)),
            status=raw.get("status"),
            progress=raw.get("progress"),
            status_error=raw.get("status_error"),
        )

    def refresh(self) -> Release:
        """Re-read this Release from the API and update it in place."""
        # Copying every field keeps handles the caller already holds current,
        # including data_item_count, which is only known once frozen.
        vars(self).update(vars(self._client.releases.get(self.id)))
        return self

    def wait(
        self,
        *,
        timeout: float = 7200,
        on_progress: Callable[[ProcessingStatus], None] | None = None,
        show_progress: bool = True,
    ) -> Release:
        """Block until this Release is ready.

        Raises:
            UnitlabError: With code ``release_failed`` when preparation failed.
            ProcessingTimeoutError: When it is still running after ``timeout``.
        """
        # Only poll a Release the backend reported as unfinished: a backend
        # without background preparation sends no status and has no /status/
        # route, so polling it would turn a finished Release into a 404.
        if self.status in ("pending", "exporting"):
            wait_for_status(
                self._client._api,
                f"/api/sdk/releases/{self.id}/status/",
                resource_name=f"Release {self.id}",
                timeout=timeout,
                on_progress=on_progress,
                show_progress=show_progress,
            )
            self.refresh()
        # wait_for_status returns on failure too, so failure is judged here.
        if self.status == "failed":
            raise UnitlabError(
                f"Release {self.id} failed: {self.status_error or 'unknown error'}",
                code="release_failed",
            )
        return self

    def download(
        self,
        split: str | None = None,
        *,
        dest: str | Path | None = None,
    ) -> str:
        """Download annotations for one split or the combined Release.

        Args:
            split: Optional split name such as ``train`` or ``test``.
            dest: Destination directory; defaults to the current directory.

        Returns:
            Absolute path to the downloaded archive.
        """
        return _downloader.download_annotation(
            self._client._api,
            self.id,
            split,
            dest,
        )

    def download_files(self, dest: str | Path | None = None) -> str:
        """Download the source files represented by this Release.

        Args:
            dest: Destination directory; defaults to the Release ID.

        Returns:
            Path to the populated directory.
        """
        return _downloader.download_files(self._client._api, self.id, dest)
