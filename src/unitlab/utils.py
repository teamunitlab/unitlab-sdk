import os

import requests

from .exceptions import AuthenticationError

ENDPOINTS = {
    "check": "/api/check/",
    "tasks": "/api/sdk/tasks/",
    "task": "/api/sdk/tasks/{}/",
    "task_datasources": "/api/sdk/tasks/{}/datasources/",
    "task_members": "/api/sdk/tasks/{}/members/",
    "task_statistics": "/api/sdk/tasks/{}/statistics/",
    "upload_data": "/api/sdk/upload-data/",
    "download_data": "/api/sdk/tasks/{}/download-data/",
    "datasets": "/api/sdk/datasets/",
    "dataset": "/api/sdk/datasets/{}/",
    "cli_tasks": "/api/cli/tasks/",
    "cli_task": "/api/cli/tasks/{}/",
    "cli_task_datasources": "/api/cli/tasks/{}/datasources/",
    "cli_task_members": "/api/cli/tasks/{}/members/",
    "cli_task_statistics": "/api/cli/tasks/{}/statistics/",
    "cli_datasets": "/api/cli/datasets/",
}


def send_request(request, session=None):
    endpoint = request.pop("endpoint")
    if os.environ.get("UNITLAB_BASE_URL"):
        request["url"] = os.environ.get("UNITLAB_BASE_URL") + endpoint
        response = (
            session.request(**request) if session else requests.request(**request)
        )
        if response.ok:
            return response

    request["url"] = "https://api.unitlab.ai" + endpoint
    response = session.request(**request) if session else requests.request(**request)
    if response.ok:
        os.environ["UNITLAB_BASE_URL"] = "https://api.unitlab.ai"
        return response

    if response.status_code == 401:
        request["url"] = "https://api-enterprise.unitlab.ai" + endpoint
        response = (
            session.request(**request) if session else requests.request(**request)
        )
        if response.ok:
            os.environ["UNITLAB_BASE_URL"] = "https://api-enterprise.unitlab.ai"
            return response

    if response.status_code == 401:
        raise AuthenticationError("Invalid API key")

    response.raise_for_status()
    return response
