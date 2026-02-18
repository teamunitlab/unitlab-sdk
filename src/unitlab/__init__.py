from importlib.metadata import version

from .client import UnitlabClient

__version__ = version("unitlab")

__all__ = ["UnitlabClient", "__version__"]
