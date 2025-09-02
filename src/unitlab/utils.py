import logging
from configparser import ConfigParser
from pathlib import Path
import logging
import requests

import requests

from . import exceptions

logger = logging.getLogger(__name__)

CONFIG_FILE_PATH = Path.home() / ".unitlab" / "credentials"


def handle_exceptions(f):
    def throw_exception(*args, **kwargs):
        try:
            r = f(*args, **kwargs)
            if r.status_code == 401:
                raise exceptions.AuthenticationError("Authentication failed")
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            raise exceptions.NetworkError(str(e))

    return throw_exception


def write_config(api_key: str, api_url: str):
    config = ConfigParser()
    config.add_section("default")
    config.set("default", "api_key", api_key)
    config.set("default", "api_url", api_url)

    CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE_PATH, "w") as configfile:
        config.write(configfile)
    logger.info(f"Credentials saved to {CONFIG_FILE_PATH}")


def read_config():
    if not CONFIG_FILE_PATH.exists():
        raise exceptions.ConfigurationError(
            f"No configuration file found at {CONFIG_FILE_PATH}. Please run `unitlab configure --help` for more information."
        )
    config = ConfigParser()
    config.read(CONFIG_FILE_PATH)
    return config


def get_api_key() -> str:
    config = read_config()
    try:
        return config.get("default", "api_key")
    except Exception:
        raise exceptions.ConfigurationError(
            f"Key `api_key` not found in {CONFIG_FILE_PATH}. Please run `unitlab configure` or provide the api-key using the --api-key option."
        )


def get_api_url() -> str:
    config = read_config()
    try:
        return config.get("default", "api_url")
    except Exception:
        return "https://api.unitlab.ai"

