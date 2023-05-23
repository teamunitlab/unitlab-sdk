from typing import Optional


class UnitlabError(Exception):
    """Base class for exceptions."""

    def __init__(self, message: str, detail: Optional[Exception] = None):
        """
        Args:
            message: An informative message about the exception.
            detail: The detail of the exception raised by Python or another library. Defaults to :obj:`None`.
        """

        super().__init__(message, detail)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        return self.message


class AuthenticationError(UnitlabError):
    """Raised when an API key fails authentication."""

    pass
