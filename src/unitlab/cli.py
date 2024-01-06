from .utils import ENDPOINTS, send_request


def get_headers(api_key):
    return {"Authorization": f"Api-Key {api_key}"}


def projects(api_key):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_projects"],
        }
    )
    print(response.json())


def project(api_key, project_id):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_project"].format(project_id),
        }
    )
    print(response.json())


def project_members(api_key, project_id):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_project_members"].format(project_id),
        }
    )
    print(response.json())
