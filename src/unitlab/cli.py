from .utils import ENDPOINTS, send_request


def get_headers(api_key):
    return {"Authorization": f"Api-Key {api_key}"}


def tasks(api_key):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_tasks"],
        }
    )
    print(response.json())


def task(api_key, task_id):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_task"].format(task_id),
        }
    )
    print(response.json())


def task_data(api_key, task_id):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_task_datasources"].format(task_id),
        }
    )
    print(response.json())


def task_members(api_key, task_id):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_task_members"].format(task_id),
        }
    )
    print(response.json())


def task_statistics(api_key, task_id):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_task_statistics"].format(task_id),
        }
    )
    print(response.json())


def datasets(api_key):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_datasets"],
        }
    )
    print(response.json())
