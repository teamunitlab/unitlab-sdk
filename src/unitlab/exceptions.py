class UnitlabError(Exception):
    """Base class for exceptions."""

    def __init__(
        self,
        message: str,
        detail: Exception | None = None,
        code: str = "",
    ):
        super().__init__(message, detail)
        self.message = message
        self.detail = detail
        self.code = code

    def __str__(self) -> str:
        return self.message


class AuthenticationError(UnitlabError):
    """Raised when an API key fails authentication."""


class NetworkError(UnitlabError):
    """Raised when an HTTP error occurs."""


class ValidationError(NetworkError):
    """Raised when the API rejects input with a 400 response."""


class NotFoundError(NetworkError):
    """Raised when the requested resource is not found."""


class SubscriptionError(NetworkError):
    """Raised when a subscription error occurs."""


class PermissionDeniedError(NetworkError):
    """Raised when the authenticated API key cannot perform an action."""


class TimeoutError(UnitlabError):
    """Raised when a request times out."""


RequestTimeoutError = TimeoutError


class ProcessingTimeoutError(TimeoutError):
    """Raised when a Batch Queue is still processing at the deadline."""

    def __init__(self, message: str, status=None, detail: Exception | None = None):
        super().__init__(message, detail)
        self.status = status
