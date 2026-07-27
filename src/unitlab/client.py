from __future__ import annotations

import os

from ._config import get_api_key, get_api_url
from ._http import HttpApi
from .exceptions import AuthenticationError
from .resources._base import identifier
from .resources.assets import AssetsNamespace
from .resources.cloud import CloudNamespace
from .resources.datasets import DatasetsNamespace
from .resources.embeddings import EmbeddingSpacesNamespace
from .resources.ontologies import OntologiesNamespace
from .resources.projects import DataUnit, Project, ProjectsNamespace
from .resources.releases import ReleasesNamespace
from .resources.workflow import WorkflowTask
from .types import AttachResult


class UnitlabClient:
    """Developer-friendly Python client for Unitlab's multimodal platform."""

    def __init__(self, api_key: str | None = None, api_url: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("UNITLAB_API_KEY") or get_api_key()
        if not self.api_key:
            raise AuthenticationError(
                "No API key provided. Pass api_key, set UNITLAB_API_KEY, "
                "or run `unitlab configure`."
            )
        self.api_url = api_url or os.environ.get("UNITLAB_API_URL") or get_api_url()
        self._api = HttpApi(self.api_key, self.api_url)
        self.projects = ProjectsNamespace(self)
        self.assets = AssetsNamespace(self)
        self.datasets = DatasetsNamespace(self)
        self.embedding_spaces = EmbeddingSpacesNamespace(self)
        self.ontologies = OntologiesNamespace(self)
        self.releases = ReleasesNamespace(self)
        self.cloud_storages = CloudNamespace(self)

    def close(self) -> None:
        self._api.close()

    def get_workflow_task(self, task_id: str) -> WorkflowTask:
        return WorkflowTask._fetch(self, task_id)

    def get_data_unit(self, project_id: str, unit_id: str) -> DataUnit:
        raw = self._api.get(
            f"/api/sdk/projects/{project_id}/data-units/{identifier(unit_id)}/"
        )
        return DataUnit._from_raw(self, str(project_id), raw)

    def attach_dataset(
        self,
        project,
        dataset,
        *,
        version: str | int = "latest",
        fps: float | None = None,
    ) -> AttachResult:
        """Attach a published Dataset snapshot to a Project.

        Args:
            project: Project handle or ID.
            dataset: Dataset handle or ID.
            version: Published version number, or ``"latest"``.
            fps: Frame rate required when the attached data contains video.

        Returns:
            The attachment counts, IDs, and optional Batch Queue ID.

        Note:
            This method does not wait for server-side processing. When
            ``batch_queue_id`` is present, wait through the Project's Batch Queue.
        """
        project_handle = (
            project if isinstance(project, Project) else self.projects.get(project)
        )
        dataset_id = identifier(dataset)
        if version == "latest":
            result = project_handle.attach(dataset_ids=[dataset_id], fps=fps)
        else:
            result = project_handle.attach(
                dataset_versions=[
                    {
                        "dataset_id": dataset_id,
                        "version_number": int(version),
                    }
                ],
                fps=fps,
            )
        return result
