import os

import requests

from .exceptions import AuthenticationError

ENDPOINTS = {
    "check": "/api/check/",
    "projects": "/api/sdk/projects/",
    "project": "/api/sdk/projects/{}/",
    "project_members": "/api/sdk/projects/{}/members/",
    "upload_data": "/api/sdk/upload-data/",
    "cli_projects": "/api/cli/projects/",
    "cli_project": "/api/cli/projects/{}/",
    "cli_project_members": "/api/cli/projects/{}/members/",
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
        if response.status_code == 401:
            raise AuthenticationError("Invalid API key")
        elif response.status_code == 400:
            raise Exception(response.json())
        response.raise_for_status()
        return response
    else:
        request["url"] = "https://api.unitlab.ai" + endpoint
        response = (
            session.request(**request) if session else requests.request(**request)
        )
        if response.ok:
            os.environ["UNITLAB_BASE_URL"] = "https://api.unitlab.ai"
            return response

        if response.status_code == 401:
            raise AuthenticationError("Invalid API key")
        elif response.status_code == 400:
            raise Exception(response.json())
        response.raise_for_status()
        return response
