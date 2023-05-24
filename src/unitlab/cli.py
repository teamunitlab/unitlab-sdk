import requests

from .client import BASE_URL

CLI_URL = BASE_URL + "/api/cli/"

CLI_ENPOINTS = {
    "ai_models": CLI_URL + "ai-models/",
    "ai_model": CLI_URL + "ai-model/{}/",
    "tasks": CLI_URL + "tasks/",
    "task": CLI_URL + "tasks/{}/",
    "task_datasources": CLI_URL + "tasks/{}/datasources/",
    "task_workers": CLI_URL + "tasks/{}/workers/",
    "task_statistics": CLI_URL + "tasks/{}/statistics/",
    "datasets": CLI_URL + "datasets/",
}


def get_headers(api_key):
    return {"Authorization": f"Api-Key {api_key}"}


def tasks(api_key):
    response = requests.get(CLI_ENPOINTS["tasks"], headers=get_headers(api_key))
    response.raise_for_status()
    print(response.json())


def task(api_key, task_id):
    response = requests.get(
        CLI_ENPOINTS["task"].format(task_id), headers=get_headers(api_key)
    )
    response.raise_for_status()
    print(response.json())


def task_data(api_key, task_id):
    response = requests.get(
        CLI_ENPOINTS["task_datasources"].format(task_id), headers=get_headers(api_key)
    )
    response.raise_for_status()
    print(response.json())


def task_workers(api_key, task_id):
    response = requests.get(
        CLI_ENPOINTS["task_workers"].format(task_id), headers=get_headers(api_key)
    )
    response.raise_for_status()
    print(response.json())


def task_statistics(api_key, task_id):
    response = requests.get(
        CLI_ENPOINTS["task_statistics"].format(task_id), headers=get_headers(api_key)
    )
    response.raise_for_status()
    print(response.json())


def ai_models(api_key):
    response = requests.get(CLI_ENPOINTS["ai_models"], headers=get_headers(api_key))
    response.raise_for_status()
    print(response.json())


def ai_model(api_key, pk):
    response = requests.get(
        CLI_ENPOINTS["ai_model"].format(pk), headers=get_headers(api_key)
    )
    response.raise_for_status()
    print(response.json())


def datasets(api_key):
    response = requests.get(CLI_ENPOINTS["datasets"], headers=get_headers(api_key))
    response.raise_for_status()
    print(response.json())
