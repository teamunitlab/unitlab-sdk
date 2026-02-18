import logging
import os
from configparser import ConfigParser, NoOptionError, NoSectionError
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_FILE_PATH = Path.home() / ".unitlab" / "credentials"


def write_config(
    api_key: str | None = None,
    api_url: str | None = None,
):
    config = ConfigParser()
    if CONFIG_FILE_PATH.exists():
        config.read(CONFIG_FILE_PATH)
    if not config.has_section("default"):
        config.add_section("default")

    if api_key is not None:
        config.set("default", "api_key", api_key)
    if api_url is not None:
        config.set("default", "api_url", api_url)

    CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE_PATH.parent.chmod(0o700)
    fd = os.open(CONFIG_FILE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as configfile:
        config.write(configfile)
    logger.info(f"Credentials saved to {CONFIG_FILE_PATH}")


def read_config() -> ConfigParser:
    config = ConfigParser()
    if CONFIG_FILE_PATH.exists():
        config.read(CONFIG_FILE_PATH)
    return config


def get_api_key() -> str:
    try:
        return read_config().get("default", "api_key")
    except (NoSectionError, NoOptionError):
        return ""


def get_api_url() -> str:
    try:
        return read_config().get("default", "api_url")
    except (NoSectionError, NoOptionError):
        return "https://api.unitlab.ai"
